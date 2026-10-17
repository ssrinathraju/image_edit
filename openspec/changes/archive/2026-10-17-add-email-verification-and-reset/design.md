# Design

## Context

See `proposal.md` for the motivation and `specs/` for the behaviour contract. This design records the current state of the code that the change builds on.

- **Accounts and sessions.** These live in SQLite through `repos/user_store.py` (`SqliteUserStore`, schema version 2).
  - Schema upgrades run in `_migrate()`, which checks columns with `PRAGMA table_info` and runs in one transaction.
  - Each store method takes `self._lock` and runs a single transaction.
  - Auth handlers are plain `def` functions that run in FastAPI's thread pool, because password hashing is CPU-bound.
- **Referral rewards.** These are paid inside `register_user` in the same transaction as the insert. `delete_user` clears `referred_by` on the accounts that a deleted user referred.
- **Login throttle.** `core/login_throttle.py` is an in-memory, per-process `LoginThrottle` that is already lock-protected.
- **Generation submit.** `generation_service.submit` validates the face count, reads and validates the uploads, then reserves a generation.
- **Email.** The server has no email capability and no mail dependency.
- **App routing.** `router.dart` redirects by session state: signed-out users may only visit `/login` and `/register`, and signed-in users on an auth page go to `/`.
- **App errors.** `core/api_errors.dart` extracts `detail.error` codes from failed responses.

## Goals / Non-Goals

**Goals:**
- One code mechanism, shared by verification and password reset, so that limits and storage are not built twice.
- No new dependencies, and no mail account needed for development or tests.
- The password reset endpoints must not reveal whether an email has an account, either through status codes, bodies or SMTP failures.

**Non-Goals:**
- Per-IP or global rate limiting.
- Email templating or localisation.
- Bounce handling.
- Measuring email delivery.
- Sweeping accounts that never verify.

## Decisions

### 1. Email sender: an interface with SMTP and log implementations
`core/email_sender.py` defines `EmailSender.send(to, subject, body)`. There are two implementations:
- `services/email/smtp_sender.py` uses the standard library `smtplib`. The `SMTP_SECURITY` setting selects `starttls`, `ssl` or `none`, and the connection timeout is 10 seconds.
- `services/email/log_sender.py` writes the message at WARNING level, because uvicorn's default logging hides application INFO logs.

`main.py` picks the SMTP sender when `IMAGE_EDIT_SMTP_HOST` is set and the log sender otherwise, and logs a startup warning when it picks the log sender. Both implementations exist from day one, so the interface meets the `CLAUDE.md` rule. This mirrors the `GenerationPipeline` layout (`core/` for the interface, `services/` for the implementations).

- **Alternative rejected: a provider HTTP API** (Resend, SendGrid). It ties the project to one vendor and needs a key even to try it. Every such provider also accepts SMTP.
- **Alternative rejected: `aiosmtplib`.** It is a new dependency, and the senders run in worker threads anyway (Decision 2).

New settings, with their defaults:

| Setting | Default |
|---|---|
| `SMTP_HOST` | `""` |
| `SMTP_PORT` | `587` |
| `SMTP_USERNAME` | `""` |
| `SMTP_PASSWORD` | `""` |
| `SMTP_FROM` | `""` |
| `SMTP_SECURITY` | `"starttls"` |
| `EMAIL_CODE_TTL_MINUTES` | `15` |
| `EMAIL_CODE_MAX_ATTEMPTS` | `5` |
| `EMAIL_RESEND_SECONDS` | `60` |
| `EMAIL_MAX_PER_HOUR` | `5` |

Settings validation refuses to start in these cases:
- `SMTP_HOST` is set but `SMTP_FROM` is empty.
- `SMTP_SECURITY` has an unknown value.
- Any of the four numeric email settings is below 1.

Validating at startup follows the `OUTPUT_RETENTION_HOURS` precedent.

### 2. Emails are sent after the response, in a background task
Endpoints that issue a code do the following:
1. Decide synchronously whether to send, by checking the limits and storing the new code.
2. Schedule the send with FastAPI `BackgroundTasks`. Because the endpoints are sync, this runs after the response in the thread pool.

A wrapper, `email_code_service.deliver(sender, user_id, to, purpose, code, ttl_minutes)`, catches every exception from the sender and logs the user id, the purpose and the exception type. It never logs the code. Nothing else depends on the send completing.

- **Alternative rejected: sending inline.** A slow SMTP server would block the request. More importantly, an SMTP failure would turn `password-reset/request` into a 5xx only for registered emails, which reveals whether an account exists. The cost of the background approach is that a crash between the response and the send loses the email. The user taps Resend.

### 3. Storage: one new users column, two tables, schema version 3
- **`users.email_verified INTEGER NOT NULL DEFAULT 0`.** `_migrate()` adds it when the column is missing and, in the same transaction, runs `UPDATE users SET email_verified = 1`. That update runs only when the column is first added, so existing accounts become verified and a re-run changes nothing.
- **`users.referral_bonus_pending INTEGER NOT NULL DEFAULT 0`.** Registration sets it to 1 when a valid referral code was used (Decision 5). It is added with the same migration. Existing rows keep 0 because they were already paid.
- **`email_codes`.** Columns are `user_id`, `purpose`, `code_hash`, `expires_at`, `attempts`, `created_at`, with `PRIMARY KEY (user_id, purpose)` and `ON DELETE CASCADE`. Upserting by the primary key gives "a new code replaces the old one" for free. An accepted code's row is deleted. An exhausted code's row stays with `attempts >= max` until it is replaced.
- **`email_sends`.** Columns are `id`, `user_id`, `purpose`, `sent_at`, with an index on `(user_id, sent_at)` and `ON DELETE CASCADE`. Each send inserts a row, and rows older than one hour for that user are deleted in the same transaction, so the table stays small.
- **`SCHEMA_VERSION`** becomes 3. As before, the column checks decide what runs, not the version number.

- **Alternative rejected: keeping codes in memory.** Codes would be lost on restart, and the 15-minute window plus the hourly cap would reset whenever the process restarts.

### 4. Code format and hashing
- **Generation.** A code is `f"{secrets.randbelow(10**6):06d}"`.
- **Hashing.** The stored value is `sha256(f"{user_id}:{purpose}:{code}")`, and comparison uses `hmac.compare_digest`.
- **What the hash protects.** It keeps codes out of casual reads of the database and out of backups. It does not stop someone holding the database from brute-forcing 10⁶ values. That person already has the account data, the codes expire in 15 minutes, and a slow hash would cost more than it protects.

**Checking a code** is one store method, `consume_code(user_id, purpose, code, now, max_attempts)`, which runs under the lock in one transaction. It returns `ok`, `wrong` or `expired`:
- **`expired`:** there is no row, `expires_at` has passed, or `attempts` has reached the maximum.
- **`wrong`:** the code does not match. This increments `attempts`.
- **`ok`:** the code matches. This deletes the row.

**Issuing a code** is `issue_code(user_id, purpose, code_hash, now, limits)`. In one transaction it checks the last-60-seconds and last-hour counts in `email_sends`. If both allow a send, it upserts the code and inserts a send row. It returns either `issued`, or `limited(retry_after_seconds)` with `retry_after` taken from whichever limit frees up later.

### 5. Referral reward on the first verification
`register_user(email, password_hash, referral_code)` no longer takes `bonus` or `max_rewards` and stops paying rewards. It stores `referred_by` as today, sets `referral_bonus_pending = 1`, and inserts `bonus_credits = 0`.

A new store method, `mark_email_verified(user_id, bonus, max_rewards)`, runs one transaction:
1. It sets `email_verified = 1` only if it was 0. If it was already 1, it stops: no rewards are paid.
2. If `referral_bonus_pending` is set, it clears the flag and adds the bonus to the account.
3. If `referred_by` is still set and the referrer is under the cap, it rewards the referrer as today.

Both verification paths call this method: `verify-email`, and `password-reset/confirm` through Decision 6. That gives "at most once" and "a reset pays the reward". Because the pending flag lives on the friend, the friend is still paid after the referrer has been deleted and `referred_by` cleared.

- **Alternative rejected: deciding the reward from `referred_by` alone.** It is cleared when the referrer is deleted, so the friend would lose their bonus.

### 6. Password reset confirmation is one transaction
`auth_service.confirm_reset` runs these steps in order:
1. Normalise the email and validate the new password's length. A bad length gives 400 `invalid_credentials_format`, and no attempt is consumed.
2. Hash the new password, outside the store lock.
3. Look up the user. If the email is unknown, return `invalid_code`.
4. Call the store method `reset_password(user_id, code, new_hash, now, max_attempts, bonus, max_rewards)`. In one transaction it does the following:
   - Runs the `consume_code` logic.
   - On `ok`, updates `password_hash` and deletes all of the user's sessions.
   - Performs the `mark_email_verified` logic from Decision 5.
5. Call `throttle.reset(email)`.
6. Create a new session and return it.

Every failure (unknown email, `wrong` or `expired`) maps to the same 400 `invalid_code` with the message "code is incorrect or has expired".

Within one transaction, the code cannot be used twice and an old session cannot outlive the password change.

### 7. Password reset request never reveals whether an account exists
The endpoint does the following:
1. Validate the email format, with the same rules as registration.
2. Look the user up.
3. If the user exists, call `issue_code` and, on `issued`, schedule the send.
4. Always return 202 with an empty JSON object `{}`.

Being limited is silent on this endpoint. On `verify-email/resend`, which is authenticated, being limited is reported as 429 with `Retry-After`.

### 8. Verification gate in the generation service
The `User` dataclass gains `email_verified`, loaded by every query that builds a `User`. The first statement of `generation_service.submit` raises 403 `{"error": "email_not_verified", ...}` when the user is not verified. That happens before face-count validation, before the uploads are read, and before reserving quota, which gives "checked before input validation" and "no generation counted".

- **Alternative rejected: a `VerifiedUserDep` dependency.** It would give the same result in more places. Generation is the only gated endpoint.

### 9. API surface and responses
- **`AuthResponse`** (register, login, password-reset confirm) and **`MeResponse`** gain `email_verified: bool`.
- **New request models:** `VerifyEmailRequest{code: str, max 16}`, `ResetRequest{email}` and `ResetConfirm{email, code, new_password}`.
- **New handlers** in `api/auth.py` are plain `def`, following the existing convention.
- **`email_code_service.py`** composes the subject and body for each purpose, for example "Your image_edit verification code is 123456. It expires in 15 minutes."

### 10. App: routes, redirect and screens
- **New routes:** `/verify-email`, `/forgot-password` and `/reset-password`. The reset route carries the email in the query parameter `email`.
- **Redirect rules:**
  - A signed-out user may visit `/login`, `/register`, `/forgot-password` and `/reset-password`.
  - A signed-in user on one of those pages goes to `/verify-email` when the session was just created by registration, and to `/` otherwise.
  - `SessionNotifier` exposes `justRegistered`, which is set by `register()` and cleared when the Verify screen opens.
  - Deciding this in the redirect avoids a race between the session-change redirect and a `go()` call in the register screen.
- **Schemas:** `Session` and `UserProfile` gain `emailVerified`, defaulting to `true` when the field is absent so that an older server does not show a banner. The home banner reads it from `accountProvider`.
- **API client methods:** `verifyEmail(code)`, `resendVerification()`, `requestPasswordReset(email)` and `confirmPasswordReset(email, code, newPassword)`.
- **`api_errors.dart`** adds these codes: `email_not_verified`, `invalid_code`, `code_expired`, `already_verified` and `too_many_requests`.
- **`submit_flow.dart`** handles `email_not_verified` by pushing `/verify-email`. The form state is kept because the form screen stays on the stack, with the same mechanism as the limit dialog.
- **Resend countdown:** a local 60-second timer, started when the screen opens after registration and after each successful resend. On a 429, the app shows the message and restarts the timer from `Retry-After` when it is present.

Screen states:

| Screen | Loading | Empty / initial | Error | Success |
|---|---|---|---|---|
| Verify email | Submit and Resend show a spinner and are disabled while in flight | Code field empty, submit disabled, countdown running after registration | `invalid_code`: "Code is incorrect". `code_expired`: "Code has expired, tap Resend". 429: "Too many codes requested, try later". Network error: generic message. `already_verified`: refresh the account and go home | Refresh the account, go to `/`, banner gone |
| Home banner | Hidden while the account is loading | Hidden for verified accounts | Hidden if the account failed to load (the existing account error handling applies) | Shown when `emailVerified == false`. Tap opens `/verify-email` |
| Forgot password | Submit spinner and disabled | Email prefilled from the sign-in field, or empty with submit disabled | Malformed email: "Email address is not valid". Network error: generic message | Go to `/reset-password?email=…` |
| Reset password | Submit spinner and disabled | Code and password empty, submit disabled, inline message for a short password | `invalid_code`: "Code is incorrect or has expired". 429 on resend: message. Values kept | Store the session; the redirect lands on `/` |

## Risks / Trade-offs

- **[What data is stored, and for how long]**
  - `email_verified` and `referral_bonus_pending` live as long as the account.
  - Each code hash lives at most until it is used, replaced or the account is deleted. An expired or exhausted row lingers until replaced, at most one row per account per purpose.
  - Send timestamps are kept for one hour, pruned on the next send for that user, and removed with the account.
  - All rows cascade on account deletion, which matches the existing "delete removes everything" requirement.
- **[Who can read it]** Only the server process. No endpoint returns a code, a code hash or send history. `GET /me` returns only `email_verified`.
- **[What is logged]**
  - In SMTP mode, the logs contain the user id, the purpose and send failures (the exception type), and never the code or the email body.
  - In log-sender mode the code is logged by design, and a startup warning says emails are not delivered. → Mitigation: the README states that log mode must not be used in any deployment that has real users.
- **[Existing data and migration]**
  - The first start adds two columns and two tables and marks every existing account verified, in one transaction, idempotently. A half-migrated file heals because the column checks decide what runs.
  - Already-paid referral bonuses stay, because existing rows get `referral_bonus_pending = 0`.
  - Rollback: the older server ignores the extra columns and tables, so a downgrade keeps working. Accounts registered in between would be treated as normal accounts again.
- **[Failure and retry]**
  - An SMTP failure is logged and the user taps Resend.
  - The send row is recorded when the code is issued, not when delivery succeeds. A failing SMTP server can therefore use up a user's 5 sends per hour without delivering any of them. → Accepted: the operator sees the logged failures, and the alternative (counting only delivered sends) lets a broken SMTP server be hammered without limit.
  - A process crash after the response but before the send loses that one email.
- **[Background tasks when a call raises]** `deliver` wraps the whole send in `try/except Exception`, logs, and returns. No exception escapes into Starlette's background runner, and no loop depends on it.
- **[Thread-safety of shared state]**
  - Every new store method runs under `SqliteUserStore._lock` in a single transaction. That covers code consumption (attempt counting cannot be lost between concurrent submits), issuing against the limits, the verify-and-reward step and the reset step.
  - `LoginThrottle` is already lock-protected.
  - The sender instances hold no mutable state. Each SMTP send opens its own connection.
- **[Account enumeration through timing]**
  - `password-reset/request` does one or two more database writes for a registered email than for an unknown one. This is a sub-millisecond difference against network jitter. → Accepted.
  - `password-reset/confirm` always hashes the new password before looking up the user, so the expensive step is the same on both paths.
- **[Email bombing]** Anyone can make the server email a known address up to 5 times an hour, which is bounded by the per-account cap. → Accepted. Per-IP limits are a non-goal.
- **[Brute-forcing codes]** An attacker gets 5 tries per code and 5 codes per hour, which is about 25 guesses in 10⁶ per hour per account. → Acceptable.
- **[Existing tests]** Many server tests register through the API and then generate, so they would now get 403. → Task 6.1 adds a test helper that verifies an account through the store and updates those tests. The behaviour under test does not change.
- **[Grandfathered accounts were never actually verified]** → Only development data exists today (`CLAUDE.md`: no users yet). Accepted.

## Migration Plan

1. Deploy the server. The first start migrates `app.db` to schema version 3 automatically.
2. Configure SMTP (`IMAGE_EDIT_SMTP_*`) before real users sign up. Until then, codes appear in the server log.
3. Ship the app update. An older app against the new server can still sign in, but its users cannot generate until verified, and it has no Verify screen. Because there are no users yet, the server and app ship together.
4. Rollback: redeploy the previous server. The extra columns and tables are ignored.
