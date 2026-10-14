# Proposal

## Why

The backend currently accepts every request anonymously, and the `photo-generation` spec records that as transitional: authentication MUST land before the API is reachable outside a trusted network. It is also the prerequisite for everything else on the roadmap — per-user plans and limits, referrals, and generation history all need to know who a request belongs to. This is change 1 of 3; plans/limits/referrals and history follow as separate changes.

## What Changes

- **Accounts**: email + password registration and login on the server. Passwords are stored only as salted hashes; sessions are opaque bearer tokens that can be revoked.
- **Endpoints**: `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /me`, `DELETE /me` (requires the password again).
- **Protected generation**: `POST /generations` and `GET /generations/{id}` require a valid session. Jobs belong to the user who created them; another user's job id returns 404.
- **Brute-force guard**: repeated failed logins for one email are temporarily rejected with HTTP 429.
- **Account deletion**: removes the user, their sessions, their jobs, and their generated images.
- **App**: login and registration screens; the app opens on login when there is no session and restores a saved session on launch; any 401 returns the user to login.
- **Profile screen** (new, reached from the home screen): account header (email, initial avatar), Help and feedback, Privacy policy and Terms links, Log out, Delete account, app version. Upgrade and Invite friends are **not** part of this change — they arrive with plans and referrals.
- **BREAKING**: unauthenticated `POST /generations` and `GET /generations/{id}` now return 401. Existing local dev clients must log in. No external clients exist yet.
- `GET /templates` and template preview images stay public.

Out of scope: social sign-in (Google/Apple), password reset and email verification, Premium plans and limits, referrals, generation history, signed image URLs, and rate limiting beyond the login guard.

## Capabilities

### New Capabilities

- `user-auth`: Account registration, login, logout, current-user lookup, session lifetime, brute-force guard, and account deletion, enforced by the server.
- `account-ui`: The app's sign-in and registration screens, session restore, automatic return to login on an invalid session, and the profile screen.

### Modified Capabilities

- `photo-generation`: Replaces the transitional "no authentication" requirement with required authentication on the generation endpoints and adds per-user job ownership.

## Impact

- **Server**: new `schemas/user.py`, `core/passwords.py`, `repos/user_store.py` (SQLite), `services/auth_service.py`, `api/auth.py`, `api/deps.py` (current-user dependency); changes to `api/generations.py`, `services/generation_service.py`, `schemas/job.py`, `core/job_store.py`, `repos/in_memory_job_store.py`, `main.py`, and `configs/settings.py`. No new Python dependencies (stdlib `sqlite3`, `hashlib.pbkdf2_hmac`, `secrets`).
- **Data**: a SQLite file at `<STORAGE_ROOT>/app.db` (gitignored via `server/storage/`). Jobs remain in memory, so they are still lost on restart.
- **App**: new `features/auth/` and `features/profile/`; new `services/auth_service.dart` and a token-injecting dio interceptor; router gains a login redirect; `.env` gains optional `PRIVACY_URL`, `TERMS_URL`, `SUPPORT_EMAIL`.
- **App dependencies**: `flutter_secure_storage` (token storage), `url_launcher` (links), `package_info_plus` (version).
- **APIs**: additive `/auth/*` and `/me`; `/generations` becomes authenticated.
- **Specs**: this change depends on `add-trending-templates` being archived first only for hygiene; the requirements it touches do not overlap.
