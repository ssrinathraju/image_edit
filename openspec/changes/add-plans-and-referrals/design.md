# Design

## Context

See `proposal.md` for motivation and `specs/` for the behavior contract. This is change 2 of 3 and builds only on the accounts from change 1.

Current state that shapes the approach:

- Server: users and sessions are in SQLite (`SqliteUserStore`, one connection, one `threading.Lock`, schema created with `CREATE TABLE IF NOT EXISTS`). Jobs are in memory (`InMemoryJobStore`) and are lost on restart. `generation_service.submit` validates, creates a queued job, then writes uploads. The worker marks jobs `succeeded` or `failed`. `GET /me` returns `id`, `email`, `created_at`.
- The auth change left `app.db` files in the wild with the old schema, so this change must upgrade a database in place.
- App: `SessionNotifier` holds `Session {token, userId, email}`; `fetchMe` returns a two-field `UserProfile`. `submitAndOpenStatus` is the single place submissions are made and errors shown. The profile screen has a header, link tiles, Log out and Delete account.
- There is no email verification and no payment integration.

## Goals / Non-Goals

**Goals:**

- A limit that cannot be bypassed by restarting the server, by racing requests, or by sending invalid requests.
- Users are never charged for server-side failures.
- Plan limits and reward values live in one place (server settings) and the app reads them instead of hardcoding.
- Existing accounts keep working after the upgrade.

**Non-Goals:**

- Payments, plan expiry, per-template or per-minute limits, usage history views.
- Moving jobs to SQLite (change 3).
- Defending against mass fake-account farming (see Risks).

## Decisions

### 1. Everything lives in the existing SQLite file

New columns on `users`:

| column | type | default | meaning |
|---|---|---|---|
| `plan` | TEXT | `'free'` | `free` or `premium` |
| `bonus_credits` | INTEGER | `0` | one-time credits, never reset |
| `referral_code` | TEXT | backfilled | unique, 8 characters |
| `referred_by` | TEXT | `NULL` | referrer's user id; `ON DELETE SET NULL` is not expressible in `ALTER`, so it is a plain column and is cleared in code when a referrer is deleted |
| `referral_rewards` | INTEGER | `0` | rewards this account has earned; never decremented |

New table:

```sql
generation_usage(
  reservation_id TEXT PRIMARY KEY,
  user_id        TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  day            TEXT NOT NULL,        -- UTC date, YYYY-MM-DD
  source         TEXT NOT NULL,        -- 'daily' | 'bonus'
  refunded       INTEGER NOT NULL DEFAULT 0,
  created_at     TEXT NOT NULL
)
CREATE INDEX idx_usage_user_day ON generation_usage(user_id, day)
```

- **Why a ledger, not a counter:** refunds must be idempotent and must go back to the same source they were taken from. A row per reservation makes both trivial and keeps an audit trail that change 3 or billing can reuse.
- **Why not count in-memory jobs:** jobs vanish on restart, which would hand everyone a fresh allowance. The ledger is durable.
- **Alternatives:** a `(user_id, day) -> count` table (cannot refund to the right source without extra state); Redis (a new service for one counter).

### 2. Upgrading an existing database

`SqliteUserStore.__init__` runs `_migrate()` after `CREATE TABLE IF NOT EXISTS`. It reads `PRAGMA table_info(users)` and issues `ALTER TABLE users ADD COLUMN ...` only for missing columns, creates `generation_usage` and its index with `IF NOT EXISTS`, creates `CREATE UNIQUE INDEX IF NOT EXISTS idx_users_referral_code`, then backfills a code for every row where `referral_code IS NULL`. All steps run in one transaction and are safe to repeat. `PRAGMA user_version` is set to 2 for future migrations, but the column checks, not the version, decide what runs, so a half-migrated file also heals. SQLite cannot add a `UNIQUE` column with `ALTER`, which is why uniqueness is a separate index.

### 3. Reserving a generation

`quota_service.reserve(user)` calls one store method, `reserve_generation(user_id, daily_limit, now)`, which holds the store lock and runs a single transaction:

1. `today = now (UTC).date()`; `used = COUNT(*) WHERE user_id=? AND day=today AND source='daily' AND refunded=0`.
2. If `used < daily_limit`: insert a `daily` row.
3. Else if `bonus_credits > 0`: decrement it and insert a `bonus` row.
4. Else raise `QuotaExceeded`.

It returns the new `reservation_id` (a ULID). The lock plus the transaction make it atomic within the process, which satisfies the concurrency scenario. The server runs as one process (already assumed by the throttle and the in-memory job store).

`reserve` is called **after** all validation in `generation_service.submit` and **before** the job is created, so rejected requests cost nothing and a refused request never produces a queued job the worker could pick up. The reservation id is stored on the job (`Job.reservation_id`). If anything raises between reserving and enqueueing (for example writing an upload), the service calls `release(reservation_id)`, which is the same operation as a refund.

The call is wrapped in `asyncio.to_thread` because `submit` is `async` and SQLite is blocking.

### 4. Refunds

`refund_generation(reservation_id)` runs `UPDATE generation_usage SET refunded=1 WHERE reservation_id=? AND refunded=0`; when exactly one row changed and its source was `bonus`, it also increments `users.bonus_credits`. A daily refund needs no other bookkeeping because the daily count excludes refunded rows. Running it twice is harmless. The worker calls it from its `except` branch when a job becomes `failed`. Jobs dropped because their owner was deleted are not refunded (the ledger rows cascade away with the user).

A refund for a job from a previous UTC day marks it refunded but does not change today's count, which is correct: that day's allowance is gone.

### 5. Plans and limits

`core/plans.py` defines `FREE = "free"`, `PREMIUM = "premium"`, `ALL_PLANS`, and `daily_limit(plan, settings)`. New settings: `FREE_DAILY_LIMIT=3`, `PREMIUM_DAILY_LIMIT=30`, `REFERRAL_BONUS=5`, `REFERRAL_MAX_REWARDS=10`. The plan lives only in the database; no endpoint writes it. `scripts/set_plan.py --email <e> --plan free|premium` opens the same database and updates the row. The server reads the plan on every request, so a change applies immediately without a restart. Unknown plans are rejected by the script. The database path logic moves out of `main.py` into a shared `auth_db_path(settings)` helper in `repos/user_store.py` so the script and the server cannot disagree.

### 6. Referral codes and rewards

- **Codes:** 8 characters from `ABCDEFGHJKLMNPQRSTUVWXYZ23456789` (no `0/O`, `1/I`), drawn with `secrets.choice` (40 bits). A unique-index collision on insert is retried up to 5 times.
- **Matching:** `code.strip().upper()`.
- **Registration is one transaction.** `register_user(email, password_hash, referral_code, bonus, max_rewards)`: look up the referrer by code (unknown → `InvalidReferralCode`, nothing written); insert the user with a fresh code, `referred_by`, and `bonus_credits = bonus`; then, if the referrer's `referral_rewards < max_rewards`, add `bonus` to the referrer's `bonus_credits` and increment `referral_rewards`. The friend is always rewarded; only the referrer is capped. A duplicate email still raises `EmailTakenError` and rolls everything back.
- **`referral_rewards` is a counter on the referrer, never derived from rows.** Counting live referees would let someone delete friends and be rewarded again.
- **Unknown code rejects registration** rather than being ignored, so a typo does not silently cost the user their bonus. The app keeps the form filled so they can correct or clear it.
- **Account deletion** (change 1) also clears `referred_by` on accounts that pointed at the deleted user.

### 7. `GET /me` shape

```json
{
  "id": "...", "email": "...", "created_at": "...",
  "plan": "free",
  "usage": {
    "daily_limit": 3, "used_today": 2, "bonus_credits": 5, "remaining": 6,
    "resets_at": "2026-10-17T00:00:00+00:00",
    "plan_limits": {"free": 3, "premium": 30}
  },
  "referral": {"code": "K7M2QX9P", "rewards": 3, "max_rewards": 10, "bonus_per_referral": 5}
}
```

`remaining = max(0, daily_limit - used_today) + bonus_credits`. `plan_limits` lets the Upgrade screen show real numbers. `quota_service.summary(user)` builds `usage`; `referral_service.summary(user)` builds `referral`. The quota error is `429 {"error": "quota_exceeded", "detail": "..."}`; the app refreshes `/me` to get the numbers rather than parsing extras out of the error.

### 8. App: one account provider, refreshed on events

- `UserProfile` grows `plan`, `usage`, and `referral` value objects (`schemas/account.dart`). `SessionNotifier` keeps its job; a new `AccountNotifier` (`AsyncNotifier<Account>`) loads `/me`, depends on the session so it resets on sign-out, and exposes `refresh()`.
- **Refresh points:** after any submit attempt, after a status poll reaches `failed` (the refund), when the profile opens, and after the limit dialog. The home chip and profile card read the same provider.
- **`submitAndOpenStatus`** catches a `DioException` with status 429 and `error == 'quota_exceeded'`, calls `refresh()`, and opens `LimitReachedDialog` (reset time from `usage.resets_at`, with Upgrade and Invite friends buttons). Photo and prompt are untouched because they live in providers owned by the screen.
- **Why not block Generate locally when remaining is 0:** the server is the authority, the cache can be stale (another device, a refund), and a blocked button hides the reason. The dialog is the explanation.
- **Register:** `register({email, password, referralCode})`; the field is optional, trimmed, and omitted when blank. `describeError` already surfaces the server's `invalid_referral_code` message.
- **Invite message:** `Join me on image edit! Use my code {CODE} when you sign up.` followed by `AppConfig.inviteUrl` when `INVITE_URL` is set in `.env`. There is no store listing yet, so the URL is optional.
- **Upgrade screen:** static comparison built from `usage.plan_limits`, with a "Payments are not available yet" notice and no purchase control.

### 9. Test seams

Server: the store takes an injected clock (already does), so UTC rollover is tested by moving the clock. A helper creates users with a given plan and bonus. Concurrency is tested with two threads against one low limit. App: the `FakeApiClient` gains `fetchMe` data and a settable 429; the profile and home tests override `accountProvider`.

## Risks / Trade-offs

- [Referral farming: there is no email verification, so anyone can mint accounts and chain codes for free credits] → The referrer cap (10 per account) and the one-time friend bonus bound each account's gain, but a tree of throwaway accounts still produces credits at GPU cost. This is the biggest risk in the change. Follow-ups, cheapest first: pay the referrer only after the friend's first successful generation; then email verification. Not built here because the chosen scheme rewards at sign-up.
- [The Upgrade screen is a "payments not available" placeholder] → Acceptable for development, but an app-store reviewer can reject non-functional purchase UI. Billing is its own later change; hide the Upgrade entry in release builds until then.
- [Limit is per process] → Fine for one server; a second server instance would need the lock replaced by a database-level constraint. Noted for deployment.
- [`referred_by` has no foreign key] → Dangling ids are possible if code forgets to clear them; covered by the deletion step and a test.
- [UTC reset is odd for users far from UTC] → The app shows the local time of the reset. A rolling window was rejected as harder to explain.
- [Refund after day rollover] → Intentionally not credited to the new day; documented in Decision 4.

## Migration Plan

Deploy the server first: startup migrates `app.db` in place and is idempotent, so a rollback leaves extra columns that the old code ignores. Existing users become `free` with 0 bonus credits and receive referral codes. The new app against the old server would lack the extra `/me` fields, so the app tolerates a missing `usage` or `referral` object by hiding those widgets. Use `set_plan.py` to promote test accounts.

## Open Questions

- Which accounts should be Premium during testing is the operator's call and needs no spec change.
