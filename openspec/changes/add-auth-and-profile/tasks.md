# Tasks

Work on branch `feat/add-auth-and-profile`. Do not push to `main`; open a PR at the end (group 11). Server tasks use `server/` as the working directory and app tasks use `app/`.

## 1. Server: settings and password hashing

- [x] 1.1 Add `AUTH_DB_PATH: str = ""` (empty means `<STORAGE_ROOT>/app.db`), `SESSION_TTL_DAYS: int = 30`, `PASSWORD_MIN_CHARS: int = 8`, `PASSWORD_MAX_CHARS: int = 128`, `LOGIN_MAX_FAILURES: int = 5`, `LOGIN_LOCKOUT_MINUTES: int = 15` to `configs/settings.py`; verify `tests/configs/test_settings.py` asserts every default and one env override
- [x] 1.2 Add `core/passwords.py` with `hash_password` / `verify_password` per design Decision 2 (`hashlib.pbkdf2_hmac`, self-describing `pbkdf2_sha256$iterations$salt$hash`, `hmac.compare_digest`, malformed stored value returns `False`, no exception); verify `tests/core/test_passwords.py` covers round trip, wrong password, same password hashing differently, a hash string containing neither the plain password nor its base64, and a malformed stored string

## 2. Server: user and session storage

- [x] 2.1 Add `schemas/user.py` (`User` dataclass: `id`, `email`, `created_at`; request/response models `Credentials`, `AuthResponse`, `MeResponse`, `DeleteAccountRequest`), `core/user_store.py` (`UserStore` Protocol: `create_user`, `get_by_email`, `get_by_id`, `delete_user`, `create_session`, `get_user_by_session`, `delete_session`), and `repos/user_store.py` (`SqliteUserStore` per design Decision 1: `CREATE TABLE IF NOT EXISTS`, foreign keys on, one lock, ULID ids, tokens stored as sha256, UTC ISO timestamps, expiry compared against an injected clock). Verify `tests/repos/test_user_store.py` covers create/lookup, duplicate email raises a typed error, session lookup, expiry, session delete leaving other sessions, and user delete cascading to sessions

## 3. Server: auth service

- [x] 3.1 Add `core/login_throttle.py` (`LoginThrottle` with injectable clock, per design Decision 4) and verify `tests/core/test_login_throttle.py` covers 5 failures locking, unlock after 15 minutes, success resetting, and independent emails
- [x] 3.2 Add `services/auth_service.py` with `register`, `login`, `logout`, `delete_account` (password check and throttle check before verification; dummy-hash verification for unknown emails; email normalization and format and length validation; password length bounds; typed errors mapped to the spec's error codes). Account deletion calls a `purge_user_jobs(user_id)` callable that is injected, so group 6 plugs in. Verify `tests/services/test_auth_service.py` covers each spec scenario for registration (valid, duplicate in other case, short password, malformed email), login (success, wrong password and unknown email giving the same error, 429 on the sixth attempt, reset on success), logout (other sessions survive), and delete (wrong password deletes nothing; right password removes user and sessions)

## 4. Server: auth API

- [x] 4.1 Add `api/deps.py` (`get_user_store`, `get_current_user` reading `Authorization: Bearer`, returning `401 {"error": "unauthorized"}` for missing, unknown, expired or revoked tokens, and `AuthDep`) and `api/auth.py` with `POST /auth/register` (201), `POST /auth/login` (200), `POST /auth/logout` (204), `GET /me`, `DELETE /me` (204, 403 on wrong password), using plain `def` handlers per design Decision 2. Verify `tests/api/test_auth.py` covers every scenario in `specs/user-auth/spec.md` through the HTTP client, including that no response body contains `password`
- [x] 4.2 Wire into `main.py` `create_app`: build the `SqliteUserStore` at `AUTH_DB_PATH` (default `<STORAGE_ROOT>/app.db`, creating the parent directory), a `LoginThrottle`, override `get_user_store`, include the auth router, and close the connection on shutdown; verify a test starts the app on a temp `STORAGE_ROOT`, registers, restarts a second app on the same directory, and the first token still works on `GET /me`

## 5. Server: protect and scope generations

- [x] 5.1 Add `user_id: str = ""` to `schemas/job.py`; add `list_for_user` and `delete` to the `JobStore` Protocol and `InMemoryJobStore`; verify `tests/repos/test_in_memory_job_store.py` covers both
- [x] 5.2 Require `AuthDep` on `POST /generations` and `GET /generations/{job_id}`; pass `user.id` into `generation_service.submit` and make `get_status` return `None` for jobs owned by another user (router keeps 404). Update `tests/conftest.py` so `client` is authenticated (registers a user and sets default `Authorization`) and add `anon_client` and a `second_user_headers` helper. Verify the existing submit/status/integration tests pass unchanged apart from the fixture, plus new cases: 401 without a token on both endpoints with no job created, owner reads own job, second user gets 404 for it, and `GET /templates` still works anonymously

## 6. Server: account deletion removes data

- [x] 6.1 Add `services/account_cleanup.py` (`purge_user_jobs(user_id, store, storage_root)`: delete each job's output file and `inputs/<id>/`, then the job) and inject it into `auth_service.delete_account` from `create_app`; verify `tests/services/test_account_cleanup.py` covers outputs removed, other users' files untouched, and a missing file not raising
- [x] 6.2 In `services/worker.py`, after the pipeline returns, delete the written output and skip recording a result when `store.get(job_id)` is `None`; verify `tests/services/test_worker.py` gains a case where the job is deleted mid-run and no output file remains
- [x] 6.3 Verify with an integration test in `tests/integration/test_account_flow.py`: register, submit, wait for success, fetch the image, `DELETE /me`, then the token returns 401, the email cannot log in, and `/images/<id>.png` returns 404

## 7. Server: documentation

- [x] 7.1 Update `server/README.md`: auth endpoints with curl examples (register, login, using the token on `/generations`, logout, delete), the new settings table rows, the note that outside local dev the API must be served over HTTPS, and that `app.db` lives in `STORAGE_ROOT`; verify each curl example by running it against a local server

## 8. App: session plumbing

- [x] 8.1 Run `flutter pub add flutter_secure_storage url_launcher package_info_plus` in `app/`; add `PRIVACY_URL=`, `TERMS_URL=`, `SUPPORT_EMAIL=` to `app/.env.example` and `app/.env`, and `privacyUrl`, `termsUrl`, `supportEmail` getters (blank returns `null`) to `configs/app_config.dart`; verify `flutter pub get` and `flutter analyze` pass and `test/configs/app_config_test.dart` covers blank and set values
- [x] 8.2 Add `schemas/session.dart` (`Session {token, userId, email}`), `core/session_storage.dart` (`SessionStorage` interface and `SecureSessionStorage` implementation), and extend `GenerationApiClient`/`DioApiClient` with `register`, `login`, `logout`, `fetchMe`, `deleteAccount(password)` plus a token provider callback and the 401 interceptor from design Decision 8 (401 on `/auth/login` and `/auth/register` excluded). Verify `test/core/api_client_test.dart` covers the bearer header, the 401 callback firing for `/generations` but not for `/auth/login`, and request bodies for the five new calls
- [x] 8.3 Add `features/auth/session_notifier.dart` (`SessionNotifier` with restore-on-build, `signIn`, `register`, `signOut` (local state cleared even when the server call fails), `deleteAccount`, `expire`; restore keeps the token on network failure and surfaces a Retry state) and wire the interceptor's callback to `expire`; verify `test/features/auth/session_notifier_test.dart` covers restore success, restore with a 401 clearing storage, restore offline keeping the token, sign-in storing the token, sign-out offline, and `expire` clearing `lastRequestProvider`

## 9. App: sign-in, registration, router

- [x] 9.1 Add `features/auth/login_screen.dart` and `features/auth/register_screen.dart` (email and password fields, submit disabled while blank or in flight, inline "at least 8 characters" message on register, server message on failure, link between the two screens); verify widget tests under `test/features/auth/` cover successful sign-in, wrong password message, throttled message, registration success, short password blocking, and taken email
- [x] 9.2 Replace the global `appRouter` with `routerProvider` (redirect rules, `/splash`, `/login`, `/register`, `/profile`, refresh on session change per design Decision 8) and update `main.dart`; verify `test/router_test.dart` covers signed-out launch landing on login, restored session landing on home, an `expire` while on a signed-in screen returning to login, and signed-in users being redirected away from `/login`

## 10. App: profile screen

- [x] 10.1 Add `features/profile/profile_screen.dart` (header with initial avatar and email, configured-only Help/Privacy/Terms entries opened via `url_launcher` with a snackbar on failure, app version from `package_info_plus`, back to home) and an account icon in the home app bar; inject a `LinkLauncher` and a version provider so tests can fake them. Verify `test/features/profile/profile_screen_test.dart` covers the header, hidden entries when unconfigured, tapping Privacy calling the launcher with the URL, and the home icon opening the profile
- [x] 10.2 Add Log out (confirmation dialog, `signOut`) and Delete account (confirmation dialog stating what is removed, password field, destructive button disabled while empty, `deleteAccount`, a wrong-password message from the 403 keeping the user on the profile) to the profile screen; verify widget tests cover log out returning to sign-in, cancel doing nothing, delete success returning to sign-in, and delete with a wrong password staying with a message

## 11. Integration and PR

- [x] 11.1 Run `uv run pytest` in `server/` and `flutter analyze && flutter test` in `app/`; verify everything passes with zero analyzer warnings, then run `openspec validate add-auth-and-profile --strict`
- [ ] 11.2 Manual run on the iOS simulator against a local server: launch signed out → register → home → open profile → log out → sign in again → template flow to a finished result → log out and in as a second account and confirm the first account's job id is 404 via `curl` → delete the second account and confirm sign-in fails. Record the outcome in the PR description and leave this box unchecked if any step could not be run
- [x] 11.3 Push the branch and open a PR to `main` with a summary, the test plan, and which steps of 11.2 were or were not exercised
