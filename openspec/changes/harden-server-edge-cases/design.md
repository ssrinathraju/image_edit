# Design

## Context

See `proposal.md` for the motivation and `specs/` for the behaviour. The current code:

- **Submit.** `generation_service.submit` runs `_require_age_and_consent`, then `_validate_face_count`, then `_read_and_validate_faces` (`upload.read()` and image decode for each face), then `_resolve_prompt`, and then `_reserve`, which runs `quota.reserve` in a thread. `QuotaService.reserve` calls `daily_limit(user.plan, settings)` and `SqliteUserStore.reserve_generation`, which is atomic under the store lock.
- **Plans.** `core/plans.daily_limit` raises `ValueError` for an unknown plan. `QuotaService.summary` (for `/me`) also calls it.
- **Jobs.** `Job` has no finish time. `worker.py` sets `status=failed, error="pipeline_failed"` or `succeeded`. `retention_service.sweep` lists output PNGs older than the cutoff and deletes each job's record and image. Failed jobs have no PNG, so their records live until the process restarts.
- **Date of birth.** `RegisterRequest`, `GoogleSignInRequest`, `AppleSignInRequest` and `AgeRequest` declare `date_of_birth: str` with `max_length=32`. A non-string or a string over 32 characters gets pydantic's 422, without the value, thanks to the `api/errors.py` handler.
- **App.** `generation_status_screen.dart` `_FailureView` shows `job.error ?? 'Generation failed'`.
- **Size.** `repos/user_store.py` is 976 lines. It holds users, sessions, usage, referrals, email codes, pending registrations, identities, and age and consent.

## Goals / Non-Goals

**Goals:**
- Each fix is the smallest change that meets the spec, with a test that fails without it.
- The split moves code without changing it, and the whole existing suite passes unchanged as proof.

**Non-Goals:**
- Changing quota rules, retention periods or error codes.
- Making the job store persistent.

## Decisions

### 1. Failure text lives in the app
`features/generation_status/failure_messages.dart` maps codes to text:
- `pipeline_failed`: "We couldn't create your image this time. This one wasn't counted, so try again."
- anything else, or null: "Something went wrong and this one wasn't counted. Please try again."

`_FailureView` uses it. The server keeps sending codes.
- **Alternative rejected: a server-side message field.** That would put user-facing wording into the API, and translation later would need server releases.

### 2. Quota: read-only pre-check, then the existing atomic reserve
`QuotaService.has_remaining(user) -> bool` uses the existing `usage_snapshot` (`remaining > 0`). `submit` calls it, in a thread, right after the age and consent gate and before face validation. False raises the existing 429 `quota_exceeded`. Validation and `_reserve` then run unchanged.

A request racing for the last generation can pass the pre-check and still get 429 from `_reserve`. That's correct, because the reservation stays the only atomic step.
- **Alternative rejected: reserving first and releasing on a validation failure.** An invalid request would hold a slot for the time it takes to read and decode, which can give a valid concurrent request a false 429.
- **Limitation.** Starlette has already received the multipart body into its spooled temp files before the handler runs. This change saves the in-memory read and the image decode, not the network transfer. Capping body size at the proxy is a separate, deployment-level concern.

### 3. An unknown plan falls back to free in one place
`core/plans.py` gains `effective_plan(plan) -> str`, which returns `plan` if it is in `ALL_PLANS`, otherwise `FREE`. `daily_limit` uses `effective_plan` and never raises.

The warning is logged once per request in `QuotaService` (`unknown_plan user=<id>`, never the stored value), which `GET /me` reports through `effective_plan`. `/me` therefore always shows `free` for a corrupted value. The stored value is left untouched for the operator to inspect.

### 4. Jobs record `finished_at`, and the sweep expires records by age
- `Job` gains `finished_at: Optional[datetime]`. The worker sets it, using the injected clock, when it sets `succeeded` or `failed`.
- `sweep` gets a second pass. For every job in `store.list_all()` (a new method on the protocol and the in-memory store) with a terminal status and `now - finished_at >= retention`, it deletes the record. The output image, if any, is deleted too.
- The existing image pass stays as it is, for images from earlier runs that have no record.
- Queued and running jobs are skipped, as today (`_LIVE`).
- The second pass catches and logs per-job errors like the first, so one bad record doesn't stop the sweep.

The in-memory store's lock covers `list_all`, which returns a snapshot list.

### 5. `date_of_birth` is typed loosely and checked by `check_date_of_birth`
- The four request models declare `date_of_birth` as `Any` (Optional where it's optional), with no length constraint.
- `core/age.check_date_of_birth` gains a guard: anything that isn't `str`, or a `str` longer than 32 characters, raises `InvalidDateOfBirth` before the pattern check. That gives 400 `invalid_date_of_birth` with a fixed message, so the value is never echoed.
- Request bodies are already bounded by the framework, so a long string costs only the length check.
- Where `date_of_birth` is optional (provider sign-in), an explicit `null` still means "not given".

### 6. Splitting `repos/user_store.py` (no behaviour change)
`SqliteUserStore` stays the single class with the single connection and lock that every caller already uses. Its methods move into mixin modules, keeping the same names, signatures and SQL:

| Module | Holds |
|---|---|
| `repos/user_store.py` | Schema, `_migrate`, the class itself composed from the mixins, users, sessions, and the shared helpers |
| `repos/user_store_usage.py` | Reservations, refunds, settles, snapshots |
| `repos/user_store_referrals.py` | Registration-time referrals, `redeem_referral` |
| `repos/user_store_codes.py` | `issue_code`, `consume_code`, pending registrations, pruning |
| `repos/user_store_identities.py` | `sign_in_with_identity`, the Apple token, `has_identity` |
| `repos/user_store_consent.py` | Age and consent updates |

Every resulting file stays under the 1000-line limit, and the main file ends below about 400 lines. The existing repo tests stay where they are and must pass without edits, which is the proof that behaviour didn't change.
- **Alternative rejected: separate store classes per area.** That means more call-site churn, and the shared connection and lock would have to be passed around, raising thread-safety questions for no gain.

## Risks / Trade-offs

- **[What data is stored, and for how long]** Only `Job.finished_at`, in memory, for as long as the record. It is removed with the record by the sweep or a restart. Nothing new is persisted.
- **[Who can read it]** Nobody new. `finished_at` isn't added to any response.
- **[What is logged]** `unknown_plan user=<id>` at WARNING, never the plan value. Sweep counts as today, plus the number of job records removed. Date-of-birth values are still never logged or echoed.
- **[Existing data and migration]** No database change. Existing in-memory jobs from before a deploy disappear on restart anyway. A corrupted plan stays stored but is read as free.
- **[Failure and retry]** A per-record sweep error is logged and the sweep continues. A pre-check failure (a database error) surfaces like a reserve failure does today, as a 500 that is logged.
- **[Background tasks when a call raises]** The sweep's second pass sits inside the existing retention loop, which already logs and continues on errors. The new pass catches per job, so it can't end the loop.
- **[Thread-safety of shared state]**
  - The pre-check reads usage with the store lock, through `usage_snapshot`.
  - The reservation remains the only writer and stays atomic.
  - `list_all` takes the job-store lock and returns a copy, so the sweep can't race the worker's updates. A job that becomes terminal during the sweep is simply picked up on the next one.
- **[The split]** Moving code risks dropped imports or a method lost from the composed class. The full unchanged suite, plus a test asserting that every public method name exists on `SqliteUserStore`, guards against this.
- **[Multipart body still received]** See Decision 2. → Accepted, and noted for the deployment checklist.

## Migration Plan

Deploy the server and app normally. No data migration is needed, and rollback is redeploying the previous version.
