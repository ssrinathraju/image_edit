# Follow-ups

Items deferred from PR #1 review. None block the merge.

## Deferred

- [ ] **Android release pass** — polish, not a bug:
  - Recover lost data after the activity is killed (image picker / camera).
  - Camera "permission denied" path that offers to open Settings.
- [ ] **`resolveUrl` with absolute URLs** — only matters once results are served from a CDN. Revisit then.
- [ ] **Friendly text for failed jobs** — the status screen shows the server's raw code (e.g. `pipeline_failed`). Map known codes to user-facing messages. Predates PR #1.
- [ ] **Search text as prompt** — search text isn't capped when reused as the prompt. Cosmetic: the custom screen already shows the 500-character error.
- [ ] **`assert` stripped in release builds** — low value, the server already returns a clean 400. Replace with an explicit check if we touch that code.
- [ ] **Image format sniffing helper** (`app/lib/services/image_actions.dart`) — builds a list and `asMap()` per check. Simplify with a plain byte comparison.

## From PR #2 review (auth and profile)

- [ ] **Authenticated or signed image URLs** — `/images/<job_id>.png` is public to anyone holding the URL. Job ids are unguessable but time-ordered. Needed before any public deployment.
- [ ] **Deep links lost on the login redirect** — the router sends a signed-out user to `/login` and forgets the target. Polish for when the app has real deep links.

## From enforce-output-retention

- [ ] **Tell users when a result expires** — add `expires_at` to the status response and a note on the result screen. Results are deleted after the retention period (24 hours by default) with no warning today; Download and Share are the only way to keep one.

- [ ] **Failed jobs' records are never swept** — a failed job has no image, so the sweep never finds it and its (small) in-memory record lives until the process restarts. Give jobs a finish time and expire terminal records older than the retention period regardless of image; this needs a one-line spec addition. Accepted for now: growth is slow and bounded by restarts.
- [x] **`generation_service.submit` ignores the app's settings** — it takes its settings from a module-level `Settings()` default and the router never passes the app's own settings. With an app built from an explicit `Settings(...)`, reference-face uploads and the validation limits (`MAX_FACES`, `MAX_UPLOAD_BYTES`, prompt length, accepted types) come from the environment default instead, so uploads land in `./storage/inputs` while the worker deletes under the configured root. Dormant in a normal deployment because both read the same environment variables. Visible in tests: every test run leaves face folders in the real `server/storage/inputs`. Fix: provide the app's settings to the generations router through a dependency and use them in `submit`, with a test that an explicit storage root receives the upload.

## From archive

- [ ] **Manual device pass not recorded** — the full manual simulator checklist for trending templates (add-trending-templates 9.2) and auth/profile (add-auth-and-profile 11.2) was not recorded. Only registration and sign-in against the real server were confirmed. Both tasks are left unchecked in the archived `tasks.md`.
- [ ] **Plans/referrals manual device pass not recorded** — the manual simulator pass for add-plans-and-referrals (10.2) was not recorded, including upgrading a copy of a real data-bearing `app.db` and the full referral flow (register with a code, both accounts +5, generate with bonus, limit dialog, promote with `set_plan.py`). Left unchecked in the archived `tasks.md`.

## From PR #4 review (plans and referrals)

- [ ] **Referral farming (remaining risk)** — verification now gates the referral reward, but disposable email addresses still pass and there are no per-IP limits on registration. Add disposable-domain screening or per-IP limits before any public launch.
- [ ] **Hide the Upgrade entry in release builds** until billing exists (the screen is a "payments not available" placeholder).
- [ ] **Unknown plan returns 500** — `daily_limit` raises for a plan value outside `free`/`premium` (only reachable through a corrupted DB). Fall back to Free and log.
- [ ] **Uploads are read before the quota check** — an over-limit user still makes the server read up to 40 MB before the 429.
- [ ] **Duplicate `/me` fetch at startup** — session restore and `AccountNotifier` each call it.
- [ ] **Failed settle gives a free generation** — if settling fails after a success, the reservation is refunded at the next restart. Rare and logged; accepted.

## Decided, no change

- Multi-face removal: intentional. The spec's REMOVED requirement and the PR notes cover it.
- Per-email lockout can be abused and the throttle is per process: accepted trade-offs in the auth design (Decision 4).
- Stale state on a fresh sign-in: unreachable, the router redirects signed-in users away from `/login`.

## From PR review of add-email-verification-and-reset (round 2)

- [ ] **design.md drift** — `openspec/changes/add-email-verification-and-reset/design.md` no longer matches the code: Decision 1 says the log sender writes at INFO (shipped: WARNING); Decisions 4-6 give old signatures (`consume_code` and `reset_password` now take `max_attempts`; `register_user` dropped `bonus` and `max_rewards`; `deliver` takes `user_id` and `ttl_minutes`). Engineers may not edit openspec/; update at archive time.
- [ ] **FastAPI `BackgroundTasks` in `auth_service`** — pass a plain `schedule: Callable` to keep the services layer framework-free. Follows the existing `HTTPException` pattern, so deferred.
- [ ] **README warning for `SMTP_SECURITY=none` with a username** — the SMTP password is sent in clear text.
- [ ] **Server venv is Python 3.9.6** while CLAUDE.md says 3.11+ (pre-existing).
