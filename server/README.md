# image-edit server

FastAPI backend for the image_edit project. Accepts reference face images and a prompt, runs an async generation pipeline, and returns the generated image.

## Setup

```bash
uv sync
```

## Run

```bash
uv run uvicorn --factory image_edit_server.main:create_app --reload --port 8000
```

OpenAPI schema: http://localhost:8000/openapi.json

## Accounts and authentication

Generation endpoints require a session. Register (two steps, below) or log in to get a bearer
token, then send it as `Authorization: Bearer <token>`. `GET /templates` and the template previews
stay public.

Registration creates **no account** until the emailed code is confirmed, so an unverified account
never exists:

```bash
# Step 1: start a registration → 202 {}  (no account and no session yet; a 6-digit code is emailed)
# `date_of_birth` (YYYY-MM-DD) is required and must be 18+ (400 under_age, 400 invalid_date_of_birth);
# it is checked, never stored or logged. `referral_code` is optional; an unknown code is a 400 invalid_referral_code
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "ana@example.com", "password": "correct horse battery", "date_of_birth": "1990-01-31"}'

# Step 2: confirm with the emailed code and the same password → 201 {"token": "...", "id": "...", "email": "ana@example.com"}
# A password that differs from the pending registration's is a 409 registration_changed and discards it
curl -X POST http://localhost:8000/auth/register/confirm \
  -H "Content-Type: application/json" \
  -d '{"email": "ana@example.com", "code": "123456", "password": "correct horse battery"}'

# Log in → 200 with a new token; the same error for a wrong password and an unknown email
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "ana@example.com", "password": "correct horse battery"}'

TOKEN=<token from the response>

curl http://localhost:8000/me -H "Authorization: Bearer $TOKEN"
# → {"id": "...", "email": "ana@example.com", "created_at": "...", "plan": "free",
#    "usage": {"daily_limit": 3, "used_today": 0, "bonus_credits": 0, "remaining": 3,
#              "resets_at": "2026-10-17T00:00:00+00:00", "plan_limits": {"free": 3, "premium": 30}},
#    "referral": {"code": "K7M2QX9P", "rewards": 0, "max_rewards": 10, "bonus_per_referral": 5},
#    "providers": [], "has_password": true, "age_confirmed": true,
#    "consent": {"accepted_version": null, "accepted_at": null, "current_version": "1"}}

# Log out: revokes this token only → 204
curl -X POST http://localhost:8000/auth/logout -H "Authorization: Bearer $TOKEN"

# Delete the account, its sessions, jobs and generated images → 204 (403 on a wrong password)
curl -X DELETE http://localhost:8000/me \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"password": "correct horse battery"}'
```

Registering the same email again before confirming replaces the pending registration (and its
code), subject to the sending limits. A pending registration that is never confirmed is discarded
after 24 hours. Expired codes, send records older than an hour and stale pending registrations are
also pruned for every address on each registration, each code request and at server start.

Errors: `401 unauthorized` (missing, unknown, expired or revoked token), `409 email_taken`,
`400 invalid_credentials_format` (malformed email or a password outside 8-128 characters),
`401 invalid_credentials`, `429 too_many_attempts` (5 failed logins for one email locks it for
15 minutes; wrong passwords on account deletion count toward the same limit),
`403 invalid_password` (account deletion), `422` (email over 254 or password over 128 characters).
The email codes section below lists the verification and reset errors.

Notes:

- Users and sessions live in a SQLite file, `app.db` inside `IMAGE_EDIT_STORAGE_ROOT`
  (override with `IMAGE_EDIT_AUTH_DB_PATH`). Jobs are still in memory and are lost on restart.
- Passwords travel as plain JSON, so outside local development the API **must** be served over
  HTTPS.
- Generated images at `/images/<job_id>.png` are not authenticated; job ids are unguessable and
  only the owner can look them up, but treat the URLs as secrets.

## Plans, daily limit, and referrals

Every account is on the `free` plan (3 generations per UTC day) or `premium` (30). A generation
is reserved when `POST /generations` is accepted and returned if the job ends `failed`; requests
that fail validation never use one. When the daily allowance and any bonus credits are gone the
server answers:

```
429 {"detail": {"error": "quota_exceeded", "detail": "the daily generation limit has been reached"}}
```

Bonus credits are one-time and are spent only after the daily allowance. Each account has a
referral code (`referral.code` in `/me`). Registering with someone's code does not pay anyone yet: both accounts receive
`REFERRAL_BONUS` credits when the registration is **confirmed** and the account is created, once.
If the referrer deleted their account in between, only the new account is paid. A referrer is
rewarded for at most `REFERRAL_MAX_REWARDS` friends. A registration that is never confirmed earns
nothing for either side.

```bash
# Start a registration with a friend's code (case and surrounding spaces are ignored); confirm as above
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "ben@example.com", "password": "correct horse battery", "date_of_birth": "1990-01-31", "referral_code": "k7m2qx9p"}'
```

There is no endpoint that changes a plan. Promote or demote an account from `server/` with the
operator script, which reads the same `IMAGE_EDIT_*` settings as the server (so run it with the
same `IMAGE_EDIT_STORAGE_ROOT` or `IMAGE_EDIT_AUTH_DB_PATH`). A running server picks the change up
on the next request:

```bash
uv run python scripts/set_plan.py --email ana@example.com --plan premium
```

`set_plan.py` prints the database it changed and refuses to run when that file does not exist, so
a run from the wrong directory fails loudly instead of creating an empty database.

Jobs are held in memory, so a restart loses any job that was queued or running. Their generations
are refunded automatically when the server starts again. This assumes a single server process: a
second instance on the same `app.db` would refund the first one's in-flight jobs.

The first start after upgrading migrates an existing `app.db` in place (schema version 5): users keep
their data, become `free` with no bonus credits, and receive referral codes. The migration is
idempotent. It also:

- adds the `age_confirmed_at`, `consent_version` and `consent_at` user columns, all NULL for existing
  accounts, so each existing account must confirm its age and give consent on next use (see
  "Age and face-photo consent"; the previous server ignores the extra columns);
- adds the provider and pending-registration tables and recreates the code tables keyed by email
  address (a code in flight during the upgrade has to be requested again);
- deletes pending registrations when upgrading from before the age check (a registration in flight
  during the upgrade has to be started again);
- marks every **unverified account verified**, because unverified accounts no longer exist. This is
  safe only for development data. If a real database ever holds accounts created between the
  email-verification release and this one, check them by hand first: anyone who registered an email
  they do not own would keep that account.

**Back up `app.db` before upgrading.** The migration cannot be run backwards: a rollback to the
previous server needs the backup, because the old code tables had a different shape.

## Email codes and password reset

Registration and password reset both use a 6-digit code emailed to the address. A code is valid for
15 minutes, is invalidated after 5 wrong tries, and is stored hashed. Codes and their limits are
**per email address**: at most one code email every 60 seconds and 5 per hour, counting
registration and reset codes together. A limited request sends nothing and keeps the earlier code
valid; `POST /auth/register` then answers `429 too_many_requests` with a `Retry-After` header.

```bash
# Forgot password: always 202 {}, whether or not the email has an account
curl -X POST http://localhost:8000/auth/password-reset/request \
  -H "Content-Type: application/json" -d '{"email": "ana@example.com"}'

# Set a new password with the code → 200, same body as login with a fresh token.
# Revokes every other session.
curl -X POST http://localhost:8000/auth/password-reset/confirm \
  -H "Content-Type: application/json" \
  -d '{"email": "ana@example.com", "code": "123456", "new_password": "a new long password"}'
```

Errors: `400 invalid_code` (wrong code; on reset also an unknown email or an expired code, all with
the same message), `400 code_expired` (registration code expired, used, invalidated or never
issued), `409 email_taken` (also when the email got an account, say through Google, after the
registration started), `429 too_many_requests` (registration only; see `Retry-After`), and
`400 invalid_credentials_format` as before. `POST /auth/verify-email` and
`/auth/verify-email/resend`, the `email_verified` response fields and the `403 email_not_verified`
generation gate no longer exist.

**Sending email.** Set `IMAGE_EDIT_SMTP_HOST` and `IMAGE_EDIT_SMTP_FROM` (plus username and
password if the server needs them) to send plain-text email over SMTP. `IMAGE_EDIT_SMTP_SECURITY` is
`starttls` (port 587, the default), `ssl` (port 465) or `none`. The server refuses to start with a
host but no `FROM` address. A delivery failure is logged (without the code) and never changes the
response of the request that asked for the email; the user taps Resend.

**Log mode.** With no `IMAGE_EDIT_SMTP_HOST` the server delivers nothing: it logs a startup warning
and writes each email, code included, to the log at WARNING level (so uvicorn shows it), so development needs no mail
account. To find a code, look for the line `Email not delivered, logged instead. To: <address>`
in the server output. **Never use log mode for a deployment with real users:** anyone who can read
the logs can take over any account.

## Sign in with Google and Apple

`POST /auth/oauth/google` and `POST /auth/oauth/apple` take a token the app got from the provider.
The server checks it itself (signature against the provider's published keys, issuer, audience,
expiry, and for Apple the nonce); the app's word is never trusted. A provider that is not
configured answers `503 provider_not_configured`.

- A linked identity signs in to its account (the account email never changes).
- Otherwise, an account with the same email (any letter case) is linked and signed in. Every
  account's email was proven by a confirmed registration code or a provider, so this joins two
  parties who proved control of the same address.
- Otherwise a new account is created: verified, **no password**, with a referral code. Password
  login on it fails exactly like a wrong password until the owner completes a password reset.
- An unlinked identity needs a provider-verified email (`email_verified` true, as a boolean or the
  string `"true"`), for Google and Apple alike; otherwise `400 provider_email_unverified`. An Apple
  token with no email for an unlinked identity is `400 provider_email_missing`.
- An account has at most one identity per provider.

```bash
# → 200 {"token": "...", "id": "...", "email": "...", "created": true}
# A request that would create an account needs `date_of_birth` (YYYY-MM-DD, 18+): without it the
# answer is 400 age_required (resend the same token with the date), under 18 is 400 under_age; neither
# creates an account or exchanges an Apple code. Linked and existing accounts are never asked.
curl -X POST http://localhost:8000/auth/oauth/google \
  -H "Content-Type: application/json" -d '{"id_token": "<GOOGLE_ID_TOKEN>", "date_of_birth": "1990-01-31"}'

# `nonce` is the raw value the app generated; the token carries its SHA-256 hex digest.
# `authorization_code` is exchanged for the refresh token that is revoked on deletion.
curl -X POST http://localhost:8000/auth/oauth/apple \
  -H "Content-Type: application/json" \
  -d '{"identity_token": "<APPLE_IDENTITY_TOKEN>", "nonce": "<RAW_NONCE>", "authorization_code": "<APPLE_CODE>", "date_of_birth": "1990-01-31"}'

# New provider accounts can redeem one referral code, within 24 hours of creation → 200 {}
curl -X POST http://localhost:8000/me/referral \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"code": "K7M2QX9P"}'

# Delete a provider-only account: confirm with a provider token issued in the last 5 minutes → 204
curl -X DELETE http://localhost:8000/me \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"provider": "google", "token": "<FRESH_GOOGLE_ID_TOKEN>"}'
# For Apple add the raw nonce: {"provider": "apple", "token": "<FRESH_APPLE_IDENTITY_TOKEN>", "nonce": "<RAW_NONCE>"}
```

`DELETE /me` takes exactly one form, either `{"password": ...}` or `{"provider": "google"|"apple",
"token": ..., "nonce": ...}`; anything else is `422`. A wrong password or a provider token that is
rejected, older than 5 minutes, or for another identity is `403` (`invalid_password` or
`invalid_provider_token`).

`GET /me` also returns `providers` (for example `["google"]`, sorted) and `has_password`.

New error codes: `401 invalid_provider_token` (sign-in), `403 invalid_provider_token` (deletion),
`400 provider_email_unverified`, `400 provider_email_missing`, `409 provider_already_linked`,
`409 referral_not_allowed`, `503 provider_not_configured`, `503 provider_unavailable` (the
provider's keys could not be fetched).

**Settings.** `IMAGE_EDIT_GOOGLE_CLIENT_IDS` is comma-separated and holds every audience the server
accepts:

- the **iOS** OAuth client ID: iOS tokens carry it as the audience;
- the **web/server** OAuth client ID: Android tokens carry it as the audience when the app passes it
  as `serverClientId`. The app's `GOOGLE_SERVER_CLIENT_ID` must be this same value;
- the Android client ID is registered in the Google Cloud console (package name and SHA-1) but does
  not appear in tokens, so it is not listed here.

`IMAGE_EDIT_APPLE_BUNDLE_ID` is enough to accept Apple sign-in. Setting `APPLE_TEAM_ID`,
`APPLE_KEY_ID` and `APPLE_PRIVATE_KEY_PATH` (the `.p8` file) as well turns on the authorization-code
exchange and revocation. The server refuses to start if only some of the three key settings are
set, if they are set without a bundle ID, or if the key file cannot be read or is not a PEM private
key.

**Apple revocation warning.** App Store rules require revoking Apple's authorization when an account
is deleted. Without the three key settings the server logs a startup warning, sign-in still works,
and deletion cannot revoke anything. Revocation runs after the response and a failure is only
logged. The Apple refresh token is stored in plain text in `app.db` (encrypting it is in `todo.md`).

Provider tokens, authorization codes and refresh tokens are never logged or returned, and a `422`
validation error describes which field failed without echoing the values that were sent.

**Provider key fetching.** The provider's published keys are cached by PyJWT. A token with an
unknown key ID forces at most one refetch every 30 seconds. An unreachable key endpoint, a body
that is not JSON, or a key set with no keys answers `503 provider_unavailable`.

**Console setup checklist.**

Google Cloud:
- [ ] Create a project and configure the OAuth consent screen.
- [ ] Create an **iOS** OAuth client with the app's bundle ID; its reversed client ID goes in the
      app's `GoogleSignIn.xcconfig`.
- [ ] Create an **Android** OAuth client with the package name and the signing SHA-1 (debug and release).
- [ ] Create a **Web** OAuth client; its ID is the app's `GOOGLE_SERVER_CLIENT_ID`.
- [ ] Put the iOS and web client IDs in `IMAGE_EDIT_GOOGLE_CLIENT_IDS`.

Apple Developer:
- [ ] Enroll in the Apple Developer Program and create the App ID with the Sign in with Apple capability.
- [ ] Create a Sign in with Apple key, download the `.p8` once, and note the Key ID and Team ID.
- [ ] Set `IMAGE_EDIT_APPLE_BUNDLE_ID`, `APPLE_TEAM_ID`, `APPLE_KEY_ID`, `APPLE_PRIVATE_KEY_PATH`.
- [ ] Set `APPLE_SIGN_IN=true` in the app's `.env`.

**Running the iOS app on a physical device before the Apple Developer Program membership exists.**
The Runner target carries the Sign in with Apple entitlement
(`app/ios/Runner/Runner.entitlements`, set as `CODE_SIGN_ENTITLEMENTS` for Debug, Release and
Profile). A free Personal Team cannot sign that capability, so a signed device build fails to
provision. The simulator and `flutter build ios --no-codesign` are unaffected. Until the membership
exists, either use the simulator or clear `CODE_SIGN_ENTITLEMENTS` for the Debug configuration in
Xcode for device runs (and restore it afterwards: do not commit the change).

## Age and face-photo consent

Only adults may use the service, and each account must agree to how face photos are handled
before generating. The date of birth is checked and thrown away: it is never stored, logged or
returned. Only `age_confirmed_at` is kept. The rule is 18 or older by the UTC date, and a
29 February birth counts from 1 March in other years.

```bash
# Existing accounts confirm their age → 200 {}; under 18 is 403 under_age; confirmed already is 409 age_already_confirmed
curl -X POST http://localhost:8000/me/age \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"date_of_birth": "1990-01-31"}'

# Accept the current consent version (GET /me shows it as consent.current_version) → 200 {}
# Any other version is 400 consent_version_mismatch
curl -X POST http://localhost:8000/me/consent \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"version": "1"}'

# Withdraw consent → 204, whether or not it was given
curl -X DELETE http://localhost:8000/me/consent -H "Authorization: Bearer $TOKEN"
```

`GET /me` reports `age_confirmed` and `consent` (`accepted_version`, `accepted_at`,
`current_version`). `POST /generations` answers `403 age_not_confirmed` or `403 consent_required`
before validating or counting anything. Raising `IMAGE_EDIT_CONSENT_VERSION` asks everyone to
accept again.

Error codes: `400 invalid_date_of_birth`, `400 under_age` (registration and provider sign-up),
`403 under_age` (`/me/age`), `400 age_required`, `409 age_already_confirmed`,
`400 consent_version_mismatch`, `403 age_not_confirmed`, `403 consent_required`.

## Submit a generation job

```bash
curl -X POST http://localhost:8000/generations \
  -H "Authorization: Bearer $TOKEN" \
  -F "prompt=a family hiking in the Alps at sunset" \
  -F "faces=@/path/to/face1.jpg" \
  -F "faces=@/path/to/face2.jpg"
# → {"job_id": "01HE..."}
```

## Submit from a template

Browse the catalog (add `?q=` to search titles and tags), then submit with a `template_id`
instead of a `prompt` (send exactly one of the two):

```bash
curl "http://localhost:8000/templates?q=beach"
# → [{"id": "golden-hour-beach", "title": "Golden Hour Beach", "tags": [...],
#     "preview_url": "/template-previews/golden-hour-beach.webp"}]

curl -X POST http://localhost:8000/generations \
  -H "Authorization: Bearer $TOKEN" \
  -F "template_id=golden-hour-beach" \
  -F "faces=@/path/to/face.jpg"
# → {"job_id": "01HE..."}
```

Template prompts stay on the server. Sending both `prompt` and `template_id`, or an unknown
`template_id`, returns 400 with error code `invalid_template`.

## Poll for status

```bash
curl http://localhost:8000/generations/<job_id> -H "Authorization: Bearer $TOKEN"
# → {"job_id": "...", "status": "queued"|"running"|"succeeded"|"failed",
#    "result_url": "/images/<job_id>.png"}
```

## Download the result

```bash
curl http://localhost:8000/images/<job_id>.png -o result.png
```

## Config (environment variables)

| Variable | Default | Description |
|---|---|---|
| `IMAGE_EDIT_STORAGE_ROOT` | `./storage` | Root directory for inputs and outputs |
| `IMAGE_EDIT_MAX_FACES` | `4` | Maximum number of reference faces per request |
| `IMAGE_EDIT_MIN_FACES` | `1` | Minimum number of reference faces per request |
| `IMAGE_EDIT_MAX_PROMPT_CHARS` | `500` | Maximum prompt length in characters |
| `IMAGE_EDIT_MAX_UPLOAD_BYTES` | `10485760` | Maximum size per face upload (bytes) |
| `IMAGE_EDIT_JOB_CONCURRENCY` | `1` | Number of parallel worker coroutines |
| `IMAGE_EDIT_OUTPUT_RETENTION_HOURS` | `24` | How long generated images are kept, in hours (minimum 1) |
| `IMAGE_EDIT_RETENTION_SWEEP_MINUTES` | `10` | How often expired images are removed, in minutes (minimum 1) |
| `IMAGE_EDIT_ACCEPTED_IMAGE_TYPES` | `image/jpeg,image/png,image/webp` | Accepted MIME types for face uploads |
| `IMAGE_EDIT_MODEL_BACKEND` | `stub` | Pipeline backend: `stub` or `sana` |
| `IMAGE_EDIT_SANA_MODEL_ID` | `Efficient-Large-Model/Sana_1600M_1024px_diffusers` | HuggingFace model id for Sana |
| `IMAGE_EDIT_SANA_DEVICE` | `cpu` | Inference device: `cpu`, `cuda`, `mps` |
| `IMAGE_EDIT_SANA_TORCH_DTYPE` | `float32` | Torch dtype: `float32`, `float16`, `bfloat16` |
| `IMAGE_EDIT_SANA_NUM_INFERENCE_STEPS` | `20` | Denoising steps |
| `IMAGE_EDIT_SANA_OUTPUT_WIDTH` | `1024` | Output image width in pixels |
| `IMAGE_EDIT_SANA_OUTPUT_HEIGHT` | `1024` | Output image height in pixels |
| `IMAGE_EDIT_TEMPLATES_DIR` | `./seed/templates` | Folder holding `catalog.json` and `previews/` |
| `IMAGE_EDIT_AUTH_DB_PATH` | _(empty)_ | SQLite file for users and sessions; empty means `<STORAGE_ROOT>/app.db` |
| `IMAGE_EDIT_SESSION_TTL_DAYS` | `30` | Session lifetime, fixed from login |
| `IMAGE_EDIT_PASSWORD_MIN_CHARS` | `8` | Minimum password length |
| `IMAGE_EDIT_PASSWORD_MAX_CHARS` | `128` | Maximum password length |
| `IMAGE_EDIT_LOGIN_MAX_FAILURES` | `5` | Consecutive failed logins per email before lockout |
| `IMAGE_EDIT_LOGIN_LOCKOUT_MINUTES` | `15` | Lockout length, counted from the latest failure |
| `IMAGE_EDIT_FREE_DAILY_LIMIT` | `3` | Generations per UTC day on the `free` plan |
| `IMAGE_EDIT_PREMIUM_DAILY_LIMIT` | `30` | Generations per UTC day on the `premium` plan |
| `IMAGE_EDIT_REFERRAL_BONUS` | `5` | Bonus credits given to each side of a referral |
| `IMAGE_EDIT_REFERRAL_MAX_REWARDS` | `10` | Friends a single account is rewarded for |
| `IMAGE_EDIT_SMTP_HOST` | _(empty)_ | SMTP server; empty means emails are logged, not delivered |
| `IMAGE_EDIT_SMTP_PORT` | `587` | SMTP port |
| `IMAGE_EDIT_SMTP_USERNAME` | _(empty)_ | SMTP login; no login when empty |
| `IMAGE_EDIT_SMTP_PASSWORD` | _(empty)_ | SMTP password |
| `IMAGE_EDIT_SMTP_FROM` | _(empty)_ | Sender address; required when `SMTP_HOST` is set |
| `IMAGE_EDIT_SMTP_SECURITY` | `starttls` | `starttls`, `ssl` or `none` |
| `IMAGE_EDIT_EMAIL_CODE_TTL_MINUTES` | `15` | How long an emailed code is valid (minimum 1) |
| `IMAGE_EDIT_EMAIL_CODE_MAX_ATTEMPTS` | `5` | Wrong tries before a code is invalidated (minimum 1) |
| `IMAGE_EDIT_EMAIL_RESEND_SECONDS` | `60` | Minimum gap between code emails to one email address (minimum 1) |
| `IMAGE_EDIT_EMAIL_MAX_PER_HOUR` | `5` | Code emails per email address per hour (minimum 1) |
| `IMAGE_EDIT_CONSENT_VERSION` | `1` | Current face-photo consent version; must not be empty. Change it when the consent text changes |
| `IMAGE_EDIT_GOOGLE_CLIENT_IDS` | _(empty)_ | Comma-separated Google client IDs accepted as the token audience; empty disables Google sign-in |
| `IMAGE_EDIT_APPLE_BUNDLE_ID` | _(empty)_ | App bundle ID, the Apple token audience; empty disables Apple sign-in |
| `IMAGE_EDIT_APPLE_TEAM_ID` | _(empty)_ | Apple team ID; set with the next two or none |
| `IMAGE_EDIT_APPLE_KEY_ID` | _(empty)_ | Key ID of the Sign in with Apple key |
| `IMAGE_EDIT_APPLE_PRIVATE_KEY_PATH` | _(empty)_ | Path to the `.p8` key file; enables code exchange and revocation |

## Retention

Generated images are kept for `IMAGE_EDIT_OUTPUT_RETENTION_HOURS` (default 24) and then deleted
together with the job that made them, so `GET /generations/{id}` and the image URL answer 404.

- **What is swept:** regular `*.png` files directly in `outputs/`, and the reference-face folders
  in `inputs/` whose job no longer exists. Nothing else is touched: other files in `outputs/`,
  symlinks, templates, previews and `app.db` are left alone. Faces of queued or running jobs are
  never removed.
- **Age** is the file's modification time, which is when the result was written. Restoring or
  copying the folder resets it, so such images live one more full period.
- **When:** once at startup, before any request is served, and then every
  `IMAGE_EDIT_RETENTION_SWEEP_MINUTES` (default 10). A failing pass is logged and retried.
- **Reference faces** left behind by a restart during a job are removed at startup, so uploaded
  photos never outlive the server run that received them.
- **Invalid values** (retention under 1 hour, sweep interval under 1 minute) stop the server from
  starting, and the error names the setting.
- Like the rest of the server this assumes a single process: a second instance on the same
  `IMAGE_EDIT_STORAGE_ROOT` would delete the first one's in-flight reference faces.

> **Warning: the first start after upgrading deletes every generated image already older than the
> retention period, including images from earlier runs that no job refers to. This cannot be
> undone.** To keep old images, copy `storage/outputs/` somewhere first, or raise
> `IMAGE_EDIT_OUTPUT_RETENTION_HOURS` for that first start.

## Running with Sana

Install ML dependencies (skip for stub/test runs):

```bash
uv sync --group ml
```

For CUDA inference, replace the torch wheel with the appropriate CUDA build:

```bash
uv pip install torch --index-url https://download.pytorch.org/whl/cu124
```

Pre-download the model (one-time, ~6 GB):

```bash
uv run python -c "from diffusers import SanaPipeline; SanaPipeline.from_pretrained('Efficient-Large-Model/Sana_1600M_1024px_diffusers')"
```

Start the server with Sana on CPU (slow, useful for smoke testing):

```bash
IMAGE_EDIT_MODEL_BACKEND=sana IMAGE_EDIT_SANA_DEVICE=cpu \
  uv run uvicorn --factory image_edit_server.main:create_app --reload --port 8000
```

For GPU (recommended):

```bash
IMAGE_EDIT_MODEL_BACKEND=sana IMAGE_EDIT_SANA_DEVICE=cuda IMAGE_EDIT_SANA_TORCH_DTYPE=float16 \
  uv run uvicorn --factory image_edit_server.main:create_app --port 8000
```

## Tests

```bash
uv run pytest
```

## Template previews

Home-screen previews live in `seed/templates/previews/` (512x512 WebP). Regenerate them from `server/`:

```bash
# Pillow only: solid-color placeholders for any template missing a preview
uv run python scripts/generate_template_previews.py --placeholder

# Real previews through Sana (needs the ml group; ~3-5 min per image on CPU)
IMAGE_EDIT_SANA_NUM_INFERENCE_STEPS=4 \
  uv run --group ml python scripts/generate_template_previews.py

# Options: --force (overwrite existing), --only <template-id>, --templates-dir <path>
```
