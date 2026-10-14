# Design

## Context

See `proposal.md` for motivation and `specs/` for the behavior contract. This is change 1 of 3 (auth + profile shell, then plans/limits/referrals, then history). Decisions here should not paint the later changes into a corner, but must not build them either.

Current state that shapes the approach:

- Server: FastAPI, layered (`configs/ → schemas/ → core/ → repos/ → services/ → api/`). Jobs live in `InMemoryJobStore` behind the `JobStore` Protocol and are lost on restart. There is **no database**. Generated images are served by a `StaticFiles` mount at `/images`; uploads are deleted when a job finishes. `generation_service.submit` and `get_status` take no user.
- `GET /templates` and `/template-previews/*` are public today.
- App: Riverpod + go_router + dio. `appRouter` is a global `GoRouter` with four routes. `DioApiClient` is created by `apiClientProvider` with no auth. `lastRequestProvider` and `selectedPhotoProvider` hold the remembered photo and prompt.
- Python target is `>=3.9`; avoid adding dependencies when the stdlib is enough.

## Goals / Non-Goals

**Goals:**

- A server that can attribute every generation to a user and refuse everyone else.
- Credentials and sessions handled so that a leaked database does not leak passwords or usable tokens.
- Logout and account deletion that really revoke access and remove data.
- A session model the next two changes can build on without rework.

**Non-Goals:**

- Social sign-in, password reset, email verification, multi-factor auth.
- Persisting jobs (history is change 3). Authenticated image URLs (see Risks).
- Plans, limits and referral codes.

## Decisions

### 1. SQLite via the standard library for users and sessions

`repos/user_store.py` exposes a `UserStore` backed by `sqlite3`, with the Protocol in `core/user_store.py` (same pattern as `JobStore`). The file lives at `<STORAGE_ROOT>/app.db`, overridable with `AUTH_DB_PATH`. Two tables:

```sql
users(id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL)
sessions(token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
         created_at TEXT NOT NULL, expires_at TEXT NOT NULL)
```

The connection is opened with `check_same_thread=False` and guarded by one `threading.Lock`; foreign keys are enabled with `PRAGMA foreign_keys=ON`. Tests use `:memory:`.

- **Why:** a real constraint (`UNIQUE email`) and durability across restarts with no new dependency, and later changes (plans, referrals) will need relational data. Plain SQL is enough for two tables.
- **Alternatives:** SQLAlchemy/Alembic (a migration tool for two tables is premature); JSON file (no uniqueness guarantee, races); Postgres (needs a service to run in dev).
- Schema is created with `CREATE TABLE IF NOT EXISTS` at startup. When change 2 needs a column it adds a versioned step then; no migration framework now.

### 2. Passwords: `hashlib.scrypt`, stored self-describing

`core/passwords.py` provides `hash_password(plain) -> str` and `verify_password(plain, stored) -> bool`. It uses `hashlib.scrypt` with `n=2**14, r=8, p=1, dklen=32` and a 16-byte `secrets.token_bytes` salt. The stored string is `scrypt$<n>$<r>$<p>$<salt_b64>$<hash_b64>` so parameters can be raised later and old hashes still verify. Comparison uses `hmac.compare_digest`.

For an unknown email, login verifies the password against a module-level dummy hash so that both failure paths cost the same time (spec: indistinguishable).

- **Why scrypt from the stdlib:** memory-hard, no dependency, and available in the Python builds `uv` installs. **Alternative:** `argon2-cffi` is the current first choice for new systems but adds a compiled dependency; the self-describing format leaves room to migrate.
- Hashing is CPU-bound (tens of ms), so the auth endpoints are plain `def` handlers and FastAPI runs them in its thread pool instead of blocking the event loop.

### 3. Sessions are opaque random tokens, stored hashed

`secrets.token_urlsafe(32)` is returned once to the client; only `sha256(token)` is stored. A token authorizes a request when its row exists and `expires_at > now`. Logout deletes the row; deleting a user cascades. TTL is `SESSION_TTL_DAYS` (default 30), fixed from issue time, with no sliding renewal.

- **Why not JWT:** logout and account deletion must take effect immediately, which JWT cannot do without a server-side denylist, at which point it is a session table anyway. We have one server and one database, so the lookup is cheap.
- **Why hash tokens:** a leaked `app.db` then does not hand out working sessions. SHA-256 is enough because tokens are high-entropy random values, not passwords.

### 4. Login throttle: in memory, per email

`core/login_throttle.py` keeps `{email: (failure_count, last_failure_at)}` behind a lock with an injectable clock. After `LOGIN_MAX_FAILURES` (5) failures it refuses attempts until `LOGIN_LOCKOUT_MINUTES` (15) after the last failure; success clears the entry. The throttle check happens **before** verifying the password, so an attacker cannot use the lockout response to learn whether a guess was right.

- **Trade-off:** per-email lockout lets someone deliberately lock a known email out for 15 minutes. A per-IP limit has its own problems behind proxies. Accepted for now; revisit with real rate limiting. State is lost on restart, which is acceptable for a single-process server.

### 5. API surface and errors

| Route | Auth | Body | Success |
|---|---|---|---|
| `POST /auth/register` | no | `{email, password}` | 201 `{token, id, email}` |
| `POST /auth/login` | no | `{email, password}` | 200 `{token, id, email}` |
| `POST /auth/logout` | yes | — | 204 |
| `GET /me` | yes | — | 200 `{id, email, created_at}` |
| `DELETE /me` | yes | `{password}` | 204 |

Errors use the existing shape: `HTTPException(status, {"error": <code>, "detail": <human text>})`, so the app's `describeError` already extracts the message. `api/deps.py` holds `get_current_user` (reads the `Authorization` header, hashes the token, looks up the session, returns a `User`) and an `AuthDep` alias. Wrong password on `DELETE /me` is **403**, not 401, because 401 means "your session is invalid" and the app signs out on it (Decision 8).

Email handling: trimmed, lowercased, max 254 characters, checked against `^[^@\s]+@[^@\s]+\.[^@\s]+$`. Registration reveals "email already taken" (409); that is accepted and normal, whereas login does not reveal which half was wrong.

### 6. Job ownership

`Job` gains `user_id: str`. `JobStore` gains `list_for_user(user_id)` and `delete(job_id)`. `generation_service.submit(...)` takes the `user_id` and stores it; `get_status(job_id, user_id, store)` returns `None` for a missing job **or** one owned by someone else, which the router maps to the existing 404. There is no 403 for jobs, so job ids cannot be probed.

`GET /templates` stays public: it carries no user data and the previews are static public assets. `/images/<job_id>.png` stays an unauthenticated static mount; ownership is not checked there (see Risks).

### 7. Account deletion cascade

`auth_service.delete_account(user, password)` verifies the password, then, in order: lists the user's jobs from the job store; for each, deletes its output file `outputs/<job_id>.png` and any `inputs/<job_id>/` directory, then removes the job; finally deletes the user row (sessions cascade).

A job may be `running` when its owner deletes the account, and the worker would then write an output file for a job that no longer exists. After the pipeline returns, the worker checks `store.get(job_id)`; if the job is gone it deletes the file it just wrote and does not record a result. This is a small change in `services/worker.py`.

### 8. App: session state, interceptor, router

- **Token storage:** `flutter_secure_storage` (Keychain on iOS, Keystore-backed on Android). A small `SessionStorage` interface (`read/write/clear`) is injected so tests use an in-memory fake.
- **`SessionNotifier`** (`AsyncNotifier<Session?>`, `Session = {token, userId, email}`): on `build` it reads the stored token and calls `GET /me`; a 401 clears storage and yields `null`, a network failure keeps the token and surfaces an error state with a Retry (so a flaky connection does not log the user out). `signIn`, `register`, `signOut` and `deleteAccount` live here.
- **Dio interceptor:** adds `Authorization: Bearer` from the notifier's current token. On a `401` response from any path **other than** `/auth/login` and `/auth/register` (where 401 means "wrong password") it calls `sessionNotifier.expire()`, which clears storage and state.
- **Router:** `appRouter` becomes `routerProvider`. The `GoRouter` gets a `redirect` that reads the session state: loading → `/splash`; signed out → `/login` (allowing `/register`); signed in on `/login` or `/register` or `/splash` → `/`. A `refreshListenable` driven by `ref.listen(sessionProvider)` re-runs redirects when the session changes. New routes: `/splash`, `/login`, `/register`, `/profile`.
- **Clearing user data on sign-out:** `signOut` and `expire` invalidate `lastRequestProvider` and `homeNotifierProvider`; `selectedPhotoProvider` is auto-dispose and goes away with its screen.
- **Web:** `flutter_secure_storage` falls back to WebCrypto-encrypted `localStorage`, which is weaker than the mobile keystores; fine for dev, and mobile is the release target.

### 9. Profile screen

`features/profile/profile_screen.dart`, reached from an account icon in the home app bar. Sections from top: header (initial avatar, email), Help and feedback / Privacy policy / Terms (each only when configured), Log out, Delete account, app version. Layout leaves an obvious slot for the plan card and Invite friends that change 2 adds.

- **Links:** `AppConfig.privacyUrl`, `termsUrl`, `supportEmail` read optional `PRIVACY_URL`, `TERMS_URL`, `SUPPORT_EMAIL` from `.env`; blank means hidden. Opened with `url_launcher` (`LaunchMode.externalApplication`), with `mailto:` for support. Failure to launch shows a snackbar. We call `launchUrl` directly instead of `canLaunchUrl`, which avoids the iOS `LSApplicationQueriesSchemes` and Android `<queries>` entries.
- **Version:** `package_info_plus`, shown as `version (build)`.
- **Delete account:** a confirmation dialog stating the deletion is permanent and listing what is removed, with a password field; the destructive button stays disabled while the field is empty.
- **Log out:** a confirmation dialog; the local session is cleared even if the server call fails.

### 10. Test seams

- Server: a fixture builds the app against `UserStore(":memory:")`, an injected clock for the throttle and session expiry, and a helper that registers a user and returns auth headers. Existing generation tests move from the anonymous `client` to the authenticated client; a separate `anon_client` covers the 401 cases.
- App: fake `SessionStorage`, the existing `FakeApiClient` extended with auth methods, and the router built from `routerProvider` with overrides.

## Risks / Trade-offs

- [Generated images are fetchable by anyone who has the URL] → Job ids are 128-bit ULIDs and not enumerable, and the status endpoint is owner-only, so URLs are only known to the owner; documented. Signed or authenticated image URLs are a follow-up before any public deployment.
- [No email verification] → Anyone can register any address. Harmless now; it matters for referral rewards (change 2), which should not pay out on unverified accounts. Flagged there.
- [Per-email lockout can be abused to lock a known user out for 15 minutes] → Accepted; bounded duration (Decision 4).
- [Jobs are still in memory, sessions are not] → After a server restart users stay signed in but their old job ids 404. Already true of jobs today; fixed by persistence in change 3.
- [SQLite file in `storage/`] → Single-writer, single-process only. Fine for one server; a move to Postgres is a `UserStore` implementation swap.
- [Passwords sent as plain JSON] → Only acceptable over HTTPS; the README states that `API_BASE_URL` must be https outside local dev.
- [Existing local clients break] → Intended (BREAKING). Dev instructions in the README.

## Migration Plan

No data migration: `app.db` is created on first start. Deploy server and app together; the old app gets 401 on generations and must be updated. Rollback is reverting the PR; the leftover `app.db` is inert.

## Open Questions

- Real values for `PRIVACY_URL`, `TERMS_URL` and `SUPPORT_EMAIL` are needed before a store submission; the app hides the entries until they exist. Does not change specs or tasks.
