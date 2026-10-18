# Design

## Context

See `proposal.md` for the motivation and `specs/` for the behaviour contract. The current state that matters here:

- **Accounts.** These live in SQLite through `repos/user_store.py` (`SqliteUserStore`, schema version 3).
  - `users.password_hash` is `TEXT NOT NULL`.
  - `_migrate()` adds missing columns by checking `PRAGMA table_info`, in one transaction.
  - Every store method runs under `self._lock` in a single transaction.
- **Verification and referrals.** Registration today creates an unverified account with a session. `POST /auth/verify-email` and `/resend` verify it, `generation_service.submit` refuses unverified accounts with 403, and the app shows a Verify email screen and a home banner. `mark_email_verified` pays a pending referral on the first 0→1 transition (the `add-email-verification-and-reset` design, Decision 5).
- **Email codes.** `email_codes` and `email_sends` are keyed by `user_id`, so a code can only be issued to an existing account.
- **Why this change also reworks registration.** Round-1 review found that linking a provider to an unverified account handed the account to whoever had registered that email first. With the user, the fix chosen is to make unverified accounts impossible: registration now creates the account only after the emailed code is confirmed (Decision 10).
- **Passwords.** `core/passwords.verify_password` returns `False` for a stored value it cannot parse, including the empty string.
- **Auth handlers.** These are plain `def` functions run in the thread pool. Account deletion goes through `AuthService.delete_account(user, password)` and the purge callback.
- **App sign-in state.** `SessionNotifier` already exposes `justRegistered`, and `router.dart` uses it to send a new registration to `/verify-email`. `AccountNotifier` loads `/me`.
- **Outside setup.** There is no Google Cloud or Apple Developer configuration yet. Every automated test must therefore run against locally signed tokens and fake endpoints.

## Goals / Non-Goals

**Goals:**
- Check provider tokens fully on the server: signature, issuer, audience, expiry, and nonce for Apple. The app's word is never trusted.
- Every server code path can be tested with no network and no real provider accounts.
- Follow the App Store rules for providers: Apple is offered whenever Google is on iOS, and Apple's token is revoked when the account is deleted.

**Non-Goals:**
- Refreshing or using provider access tokens for anything other than revocation.
- Importing profile data (name, avatar) from providers.
- Per-IP limits on the OAuth endpoints.
- Apple sign-in through the web on Android.

## Decisions

### 1. Token checks: `pyjwt[crypto]` behind a small verifier interface
`core/identity_verifier.py` defines two things:
- `IdentityVerifier.verify(token, *, nonce=None) -> ProviderIdentity`, where `ProviderIdentity` holds `provider`, `subject`, `email`, `email_verified` and `issued_at`.
- The exceptions `InvalidProviderToken` and `ProviderUnavailable`.

There are two implementations under `services/identity/`:
- **`google_verifier.py`:** uses the JWKS at `https://www.googleapis.com/oauth2/v3/certs`. The issuer must be `accounts.google.com` or `https://accounts.google.com`, and the audience must be in `GOOGLE_CLIENT_IDS`.
- **`apple_verifier.py`:** uses the JWKS at `https://appleid.apple.com/auth/keys`. The issuer must be `https://appleid.apple.com`, the audience must be `APPLE_BUNDLE_ID`, and the `nonce` claim must equal `sha256(raw_nonce).hexdigest()`.

Both verifiers report `email_verified` as true only for the boolean `true` or the string `"true"`, because Apple sends the claim as a string. A missing claim counts as false.

Both use `jwt.PyJWKClient` with caching (keys are refetched on an unknown `kid`), a 5-second fetch timeout, RS256 only and 60 seconds of clock leeway. A failed fetch raises `ProviderUnavailable`, which becomes 503. Any decode or claim failure raises `InvalidProviderToken`, which becomes 401 at sign-in and 403 at deletion.

For tests, the verifiers take the JWKS client as a constructor argument. The tests build tokens with a locally generated RSA key and a fake JWKS client, so there is no network.

- **Alternative rejected: Google's `google-auth`.** It covers Google only and pulls in a larger dependency tree. Apple would still need PyJWT.
- **Alternative rejected: trusting the app's decoded claims.** Anyone could forge an identity.

### 2. Storage: an `identities` table and two `users` columns, schema version 4
- **`identities`.** Columns:
  - `provider`, `subject`, `created_at`;
  - `user_id`, referencing `users(id)` with `ON DELETE CASCADE`;
  - `email`, as reported when the identity was linked (kept for support only);
  - `apple_refresh_token TEXT NULL`.

  Constraints: `PRIMARY KEY (provider, subject)` and `UNIQUE (user_id, provider)`.
- **`users.created_via TEXT NOT NULL DEFAULT 'password'`.** Set to `google` or `apple` for accounts created through a provider. Existing rows get `password`.
- **`users.referral_redeemed INTEGER NOT NULL DEFAULT 0`.** Set by post-sign-up redemption (Decision 6).
- **An account without a password** stores `password_hash = ''`. `verify_password` already returns `False` for it, so password login and password-confirmed deletion fail exactly as for a wrong password. `has_password` is `password_hash != ''`. A password reset writes a real hash, which gives the account a password.
- **`pending_registrations`.** Columns: `email` (primary key, lowercased), `password_hash`, `referral_code` (nullable, normalised), `created_at`. One row per email. Re-registering replaces it, confirming deletes it, and each insert deletes rows older than 24 hours.
- **`email_codes` and `email_sends` are re-keyed by email address.** `email_codes` gets `PRIMARY KEY (email, purpose)` and `email_sends` an index on `(email, sent_at)`, with purposes `registration` and `password_reset`. Neither table references `users`, since a registration code exists before its account. Account deletion therefore deletes that email's rows explicitly in the same transaction. The migration drops and recreates both tables. They only hold codes valid for 15 minutes and send times kept for an hour, so at worst a reset code in flight during the upgrade has to be requested again.
- **Existing unverified accounts.** The v4 migration runs `UPDATE users SET email_verified = 1 WHERE email_verified = 0` (the user's decision; see Risks). `email_verified` and `referral_bonus_pending` then stay in the table, because dropping a column in SQLite means rebuilding a table that others reference. No code reads them after this change. New accounts still write `email_verified = 1`, so a rollback to the version-3 server does not treat them as unverified.
- **`SCHEMA_VERSION = 4`.** The column and table checks decide what runs, as before.

- **Alternative rejected: rebuilding `users` to make `password_hash` nullable.** SQLite cannot drop `NOT NULL` without copying the table, and several tables reference `users` with foreign keys. An empty-string sentinel is safe because the verifier already treats it as invalid.

### 3. Find, link or create in one store transaction
`sign_in_with_identity(identity, now, bonus, max_rewards) -> (User, created)` runs under the lock in one transaction:
1. If `(provider, subject)` exists, return its user. The account's email is not changed.
2. Otherwise, if the token has no email, raise `ProviderEmailMissing`. If its `email_verified` is not true (Google or Apple), raise `ProviderEmailUnverified`. These checks happen before any write.
3. If a user has that email (lowercased):
   - If they already have an identity of this provider, raise `ProviderAlreadyLinked`.
   - Otherwise insert the identity and return them with `created=False`. Every account's email is proven (Decision 10), so linking changes nothing else about the account.
4. Otherwise insert a user with:
   - the lowercased email;
   - `password_hash = ''`;
   - `created_via = provider`;
   - a new referral code.

   Also delete any pending registration for that email, so a stale code can't later collide with the new account (confirming it would answer 409 anyway).

   Then insert the identity and return it with `created=True`.

The primary key and the lock make two simultaneous first sign-ins of the same identity safe: the second finds the identity row.

Apple only sends the email on the first authorization, so step 2 only applies to identities that are not linked yet.

### 4. Apple authorization code and revocation
After a successful Apple sign-in, `services/apple_revocation.py` exchanges the `authorization_code` at `https://appleid.apple.com/auth/token`. It does this only when `APPLE_TEAM_ID`, `APPLE_KEY_ID` and `APPLE_PRIVATE_KEY_PATH` are set and the identity has no stored token.
- **The client secret** is an ES256 JWT signed with the `.p8` key. Its `iss` is the team ID, its `sub` is the bundle ID, its `aud` is `https://appleid.apple.com`, and it is valid for 5 minutes.
- **On success**, the returned `refresh_token` is stored in `identities.apple_refresh_token`.
- **The exchange runs synchronously** with a 10-second timeout. A failure is logged (status code or exception type only) and does not fail the sign-in. The next Apple sign-in for that identity tries again.

When an Apple-linked account is deleted, the token is read before the delete. After the delete commits, a background task posts to `https://appleid.apple.com/auth/revoke` with `token_type_hint=refresh_token`. A wrapper catches and logs every exception.

When the Apple key settings are absent, sign-in still works (the bundle ID alone is enough to check tokens), and a startup warning says revocation is disabled.

The HTTP calls use the standard library's `urllib.request`, so no HTTP client dependency is added. Tests replace the poster function.

- **Alternative rejected: revoking before deleting.** A slow or failing Apple endpoint would delay or block deletion. The App Store rule is satisfied by the attempt, and the failure is logged.
- **Alternative rejected: skipping the code exchange.** Without a refresh token there is nothing to revoke.

### 5. Deletion confirmation
`DeleteAccountRequest` becomes `{password?: str, provider?: "google"|"apple", token?: str, nonce?: str}`. Exactly one form must be present, either `password` or `provider` with `token`; pydantic validation answers 422 for any other shape.

- **Password form:** unchanged, including the login throttle.
- **Provider form:**
  - Verify the token with that provider's verifier (Apple also needs `nonce`).
  - Check that `(provider, subject)` is linked to this user.
  - Check that `now - issued_at <= 5 minutes`.
  - Any failure is 403 `invalid_provider_token`.

  The provider form is not throttled, because a valid token cannot be guessed.

Deleting a user cascades to `identities`. Apple revocation follows Decision 4.

### 6. Referral redemption after a provider sign-up
`redeem_referral(user_id, code, now, window, bonus, max_rewards)` runs in one transaction.
1. It refuses with `ReferralNotAllowed` unless all of these hold:
   - `created_via != 'password'`;
   - `created_at > now - 24h`;
   - `referral_redeemed = 0`;
   - `referred_by IS NULL`.
2. It refuses with `InvalidReferralCode` if the code is unknown or is the account's own.
3. Otherwise it sets `referred_by` and `referral_redeemed = 1`, adds the bonus to the account, and rewards the referrer if they are under the cap.

The account is already verified, so the reward is paid immediately rather than through `referral_bonus_pending`. The 24-hour window is a constant in `core/`, not a setting.

### 10. Registration creates the account only after the code is confirmed
- **`POST /auth/register`** runs these steps:
  1. Validate the format, then the referral code (400 if unknown), then that no account has the email (409).
  2. Hash the password outside the lock.
  3. Under the lock, in one transaction, check the per-email limits. If one applies, answer 429 with `Retry-After` and keep the old pending row and code.
  4. Otherwise upsert `pending_registrations`, upsert the `registration` code and insert a send row.
  5. Schedule the email after the response, as today, and answer 202 `{}`.
- **`POST /auth/register/confirm`** takes `{email, code, password}`. It runs in two steps so the slow password check never holds the store lock:
  1. **Check the code (one transaction under the lock).** Run the `consume_code` logic for the `registration` code, without deleting the code on `ok`. `wrong` gives 400 `invalid_code`, and `expired` (including no pending row) gives 400 `code_expired`. On `ok`, return the pending row's `password_hash` and `created_at`.
  2. **Check the password, outside the lock.** Run `verify_password(password, pending_hash)`.
  3. **Commit (one transaction under the lock).** Re-read the pending row and require the same `created_at` and `password_hash` as in step 1, so a re-registration in between is caught.
     - On a password mismatch or a changed row, delete the pending row and its code and answer 409 `registration_changed`.
     - If an account now has the email, delete the pending row and answer 409 `email_taken`.
     - Otherwise insert the user from the pending row with `email_verified = 1` and `created_via = 'password'`. If the pending referral code still belongs to an account, link it and pay both sides under the cap. If that account was deleted meanwhile, pay only the new account. Delete the pending row and its code, and create a session. The response is `AuthResponse` with 201.
- **Why the password is checked on confirm.** Round-2 review showed that anyone could register the same email a minute after the real owner, with their own password, and the owner would then confirm the newest code from their inbox and get an account with the stranger's password. Requiring the registering password at confirm means the account is only created when the same person holds both the inbox (the code) and the password. A stranger's re-registration can then only make the owner's confirm fail with `registration_changed`, after which the owner registers again.
  - **Alternative rejected: refusing to replace a pending registration while its code is live.** A stranger could still win after the 15 minutes if the owner is slow, and could block the owner for 15 minutes.
  - **Alternative rejected: accepting the risk.** It reopens the takeover this change exists to close.
- **Order of checks.** The code is checked before the password, so someone without the inbox learns nothing about the password and always gets `invalid_code` or `code_expired`. A wrong password with a correct code discards the registration rather than counting attempts, so nobody can guess passwords against a valid code.
- **Code rules stay as they are:** the TTL, attempts, 60-second and 5-per-hour limits now apply per email address. Password-reset codes are keyed by the account's email.
- **Alternative rejected: keep creating the account at registration and take it over cleanly at link time** (wipe the password and revoke sessions). It fixes the takeover, but anyone can still squat someone else's email and block their registration, and the unverified-account machinery (gate, banner, deferred referral) stays.
- **Alternative rejected: a separate change first.** The user chose to keep one feature in flight.

### 11. Removing the unverified-account machinery
Because no account can be unverified, this change deletes the following:
- **Server:** `POST /auth/verify-email` and `/resend`, the `email_not_verified` gate in `generation_service.submit`, `mark_email_verified`, the `referral_bonus_pending` logic, `email_verified` in `AuthResponse` and `MeResponse`, and the verification step in password reset.
- **App:** the Verify email screen and route, the home banner, `email_not_verified` handling in `submit_flow.dart`, `emailVerified` in `Session` and `UserProfile`, and `justRegistered`.
- **Tests:** the tests for these are deleted or rewritten. The conftest `client` fixtures create accounts through the store or through register-then-confirm.

No compatibility shims are kept, because the project has no users.

### 12. Housekeeping for email-keyed rows, and no database access at import
- **Pruning (closes round-2 review finding S2).** `email_codes` and `email_sends` are no longer tied to an account, so they would otherwise keep the addresses of people who never registered. Every `start_registration` and every `issue_code` call deletes, in the same transaction and for all addresses:
  - `email_codes` rows past `expires_at`;
  - `email_sends` rows older than the one-hour send window;
  - `pending_registrations` rows older than 24 hours.

  The server also runs the same pruning at startup, next to the existing retention sweep. That bounds how long an abandoned address stays, even if nobody registers afterwards: until the next registration, code issue or reset request, or the next server start. The periodic retention sweep does not prune these rows.
- **No database at import (closes S3).** `main.py` no longer creates a module-level `app = create_app()`. The server is started with `uvicorn --factory image_edit_server.main:create_app`. Tests already build apps from `create_app(settings)` on temporary paths, so importing `image_edit_server.main` no longer opens or migrates `server/storage/app.db`.
  - **Alternative rejected: a separate `asgi.py` entry module.** It is one more file for no gain over the factory flag uvicorn already supports.

### 7. Settings and startup checks
New settings, with their defaults:

| Setting | Default |
|---|---|
| `GOOGLE_CLIENT_IDS` | `[]` |
| `APPLE_BUNDLE_ID` | `""` |
| `APPLE_TEAM_ID` | `""` |
| `APPLE_KEY_ID` | `""` |
| `APPLE_PRIVATE_KEY_PATH` | `""` |

Google is configured when `GOOGLE_CLIENT_IDS` is non-empty, and Apple sign-in when `APPLE_BUNDLE_ID` is set.

The server refuses to start in these cases:
- some but not all of the three Apple key settings are set;
- the key settings are set without `APPLE_BUNDLE_ID`;
- the key file cannot be read.

`GOOGLE_CLIENT_IDS` accepts the iOS, Android and web/server client IDs. With `serverClientId` set in the app, Android tokens carry the web client ID as the audience; iOS tokens carry the iOS client ID.

### 8. API surface
- **`POST /auth/oauth/google`** takes `{id_token}`.
- **`POST /auth/oauth/apple`** takes `{identity_token, nonce, authorization_code}`.
- **Both** return `AuthResponse` plus `created: bool`.
- **`POST /auth/register`** takes `{email, password, referral_code?}` and returns 202 `{}`. **`POST /auth/register/confirm`** takes `{email, code}` and returns 201 `AuthResponse`.
- **`AuthResponse`** is `{token, id, email}` everywhere (register-confirm, login, password-reset confirm and the provider endpoints, which add `created`). `email_verified` is gone.
- **`POST /me/referral`** takes `{code}` and returns 200 `{}`.
- **`MeResponse`** gains `providers: list[str]` (sorted) and `has_password: bool`.

All new handlers are plain `def`. Error mapping:

| Error | Status | Code |
|---|---|---|
| `InvalidProviderToken` | 401 at sign-in, 403 at deletion | `invalid_provider_token` |
| `ProviderUnavailable` | 503 | `provider_unavailable` |
| Provider not configured | 503 | `provider_not_configured` |
| `ProviderEmailUnverified` | 400 | `provider_email_unverified` |
| `ProviderEmailMissing` | 400 | `provider_email_missing` |
| `ProviderAlreadyLinked` | 409 | `provider_already_linked` |
| `ReferralNotAllowed` | 409 | `referral_not_allowed` |
| Registration limited | 429 + `Retry-After` | `too_many_requests` |
| Registration code wrong or expired | 400 | `invalid_code` or `code_expired` |
| Email registered meanwhile | 409 | `email_taken` |
| Correct code, password does not match the pending registration (or it was replaced mid-confirm) | 409 | `registration_changed` |

### 9. App: provider sign-in behind an injectable interface
`core/provider_sign_in.dart` defines `ProviderSignIn.signIn() -> ProviderCredential?`, which returns null when the user cancels. There are two implementations:
- **`GoogleProviderSignIn`** uses `google_sign_in` with `clientId` set to `GOOGLE_IOS_CLIENT_ID` on iOS and `serverClientId` set to `GOOGLE_SERVER_CLIENT_ID`, and returns the ID token.
- **`AppleProviderSignIn`** uses `sign_in_with_apple` with the email scope. It generates a random 32-byte nonce, passes its SHA-256 to Apple using `crypto`, and returns the identity token, the raw nonce and the authorization code.

Both are exposed through Riverpod providers so widget tests can override them.

Button visibility:
- **Google** is shown when `GOOGLE_SERVER_CLIENT_ID` is set, and on iOS only when `GOOGLE_IOS_CLIENT_ID` is also set.
- **Apple** is shown when `Platform.isIOS` and `APPLE_SIGN_IN=true`.

Native setup:
- **iOS:** add a `Runner.entitlements` with `com.apple.developer.applesignin`. Add a `CFBundleURLTypes` entry whose scheme comes from the build setting `GOOGLE_REVERSED_CLIENT_ID`, defined in a git-ignored `ios/Flutter/GoogleSignIn.xcconfig`, with a checked-in `GoogleSignIn.xcconfig.example`.
- **Android:** no code change. The SHA-1 is registered in the console.

Routing:
- `SessionNotifier` gains `signInWithProvider(credential)` and `justCreatedViaProvider`. The redirect sends that state to `/referral-prompt`. The prompt screen clears the flag in `initState`.
- **Registration:**
  - `register_screen.dart` calls `register(...)`. On 202 it stores the entered values in a `registrationDraftProvider` (in memory only, never persisted) and pushes `/confirm-registration`. No session is created yet.
  - The new `confirm_registration_screen.dart` reads the email from the draft. Confirm calls `confirmRegistration(email, code, password)` with the draft's password. On success the session is stored, the draft is cleared, and the redirect lands on `/`. On `registration_changed` the app pops back to the registration screen with the values kept and a message to submit again.
  - Resend calls `register(...)` again with the draft's values.
  - Back pops to the registration screen, which still has its values.
  - `/confirm-registration` is allowed while signed out. If there is no draft, it redirects to `/register`.
- **Error codes:** `api_errors.dart` adds the seven provider codes. `email_not_verified` and `already_verified` are removed.

The password sits in memory (the draft) only while the Confirm screen is open, so Resend can re-send without asking again. It is never written to disk.

Deletion in the app: when `hasPassword` is false, `profile_screen.dart` runs the linked provider's sign-in. That is Apple if the account is linked to Apple and the app is on iOS, otherwise Google. It then calls `deleteAccount(provider:, token:, nonce:)`. A cancelled sign-in returns to the profile silently.

Screen states:

| Screen | Loading | Empty / initial | Error | Success |
|---|---|---|---|---|
| Register (email form) | Submit shows a spinner and is disabled | Fields empty; inline message for a short password | `email_taken`: "Email already registered". `invalid_referral_code`: "Code not recognised". 429: "Too many codes requested, try again in N s". Values kept in every case | Push `/confirm-registration` |
| Confirm registration | Confirm and Resend show a spinner and are disabled while in flight | Code field empty, Confirm disabled, Resend countdown from 60 s | `invalid_code`: "Code is incorrect". `code_expired`: "Code has expired, tap Resend". 429 on Resend: message and countdown from `Retry-After`. `email_taken`: "Email already registered" with a "Go to sign-in" action. `registration_changed`: pop to the registration screen, values kept, "Your registration changed. Submit it again." | Session stored, draft cleared, home |
| Sign-in and register (provider buttons) | The tapped button shows a spinner, and all submit controls are disabled while in flight | Buttons hidden for unconfigured providers; Apple hidden on Android | `invalid_provider_token`: "Sign-in failed, try again". `provider_email_unverified`: "Verify your Google email first" or "Verify your Apple email first", naming the provider used. `provider_email_missing`: "Apple didn't share an email; remove this app in Apple ID settings and try again". `provider_already_linked`: "This account is already linked to another Google account". 503: "Sign-in is unavailable right now". Cancel: nothing shown | Session stored. New account goes to `/referral-prompt`, an existing one to `/` |
| Referral prompt | Apply shows a spinner and is disabled | Code field empty, Apply disabled | `invalid_referral_code`: "Code not recognised", value kept. `referral_not_allowed`: "This account can't redeem a code", then go home | Account refreshed, go to `/` |
| Profile provider line | Hidden while the account loads | Hidden when there are no providers | Hidden if the account failed to load | "Signed in with Google" and/or "Signed in with Apple" |
| Profile, Delete account | Spinner during the provider sign-in and the delete | Confirmation dialog; password field only when `hasPassword` | Wrong password: "Password is incorrect". `invalid_provider_token`: "Couldn't confirm with Google/Apple". Cancel: nothing shown | Session cleared, sign-in screen |

## Risks / Trade-offs

- **[What data is stored, and for how long]**
  - An `identities` row per linked provider holds the provider subject, the email reported when it was linked, and for Apple a refresh token. It lives as long as the account and is removed by the cascade on deletion.
  - `created_via` and `referral_redeemed` live as long as the account.
  - A pending registration holds an email, a password hash and an optional referral code. It lives until it is confirmed, replaced or discarded (`registration_changed`). Otherwise it is pruned once it is more than 24 hours old, at the next registration, code issue or server start (Decision 12).
  - Code and send rows for an address hold that address. Expired codes, and send rows older than an hour, are pruned on the same triggers. An address that never registers therefore stays only until the next such event.
  - The app's registration draft holds the plain password in memory only. It is cleared on a successful confirm and whenever the user leaves the registration flow (signing in, or leaving the register screen).
  - Provider ID tokens and authorization codes are never stored.
- **[Who can read it]**
  - Only the server process.
  - `GET /me` exposes only the provider names and `has_password`. It never exposes subjects or tokens.
- **[What is logged]**
  - Sign-in outcomes are logged with the user id and provider.
  - Verification failures are logged with the reason class (expired, audience, signature).
  - Failed Apple code exchanges and revocations are logged with the HTTP status or exception type.
  - No token, code or refresh token is ever logged. A test captures the logs from an Apple sign-in with a bad token and asserts that the token text is absent.
- **[Apple refresh token stored in plain text]**
  - Someone holding the database can use it only to get Apple access tokens that identify the user to this app. They already hold everything else.
  - Encrypting it would need a key-management design. → Accepted, and recorded as a follow-up.
- **[Existing data and migration]**
  - The first start does all of the following in one transaction, and a re-run changes nothing:
    - adds two columns and the `identities` and `pending_registrations` tables;
    - recreates `email_codes` and `email_sends` keyed by email;
    - marks every unverified account verified.
  - Existing accounts keep their passwords and get `created_via = 'password'`.
  - **Accepted risk, at the user's decision:** accounts that registered but never verified become verified without anyone having proven the email. Today these exist only in development databases (`CLAUDE.md`: no users yet). If this ever ran on real data, someone who squatted an email before the upgrade would keep that account and could then be linked by the real owner's Google sign-in. Before any real launch, check that no account was created between the email-verification release and this one, or delete such accounts by hand.
  - Rollback: the version-3 server ignores the extra table and columns. Provider-only accounts (empty hash) then simply cannot log in until a password reset.
- **[Linking by email]**
  - Anyone controlling a Google account with a verified address matching an existing account gets into that account. This is the industry-standard trade-off, and it depends on the provider's verification.
  - Unverified provider emails (Google or Apple) are refused. Apple relay addresses never match a password account.
  - Every account's email has been proven by a registration code, a provider, or (for old development data) the migration. So a link always joins two parties who proved control of the same address.
- **[Registration reveals registered emails]** `POST /auth/register` still answers 409 for a taken email, as it did before. This is a known enumeration that the earlier changes accepted. Password reset stays non-revealing.
- **[Email bombing through registration]** Anyone can make the server send registration codes to an address, capped at 5 an hour per address. This is the same bound as reset. → Accepted.
- **[Failure and retry]**
  - A provider's key endpoint being down → 503 `provider_unavailable`; the user retries. Cached keys keep sign-in working through short outages.
  - A failed Apple code exchange → sign-in succeeds, and the exchange is retried on the next Apple sign-in.
  - A failed revocation → logged, and the deletion has already completed. It is not retried, because there is no account left to retry from.
- **[Background tasks when a call raises]** The revocation task's wrapper catches every exception and logs it. It runs after the response and nothing depends on it.
- **[Thread-safety of shared state]**
  - Find-link-create, redemption, the provider deletion check, starting a registration and confirming one all run under `SqliteUserStore._lock` in single transactions. A provider sign-in and a registration confirm racing for the same email therefore serialise: whichever commits second sees the account and links to it (provider) or answers 409 (confirm).
  - Confirm's password check runs between two transactions. The commit step re-reads the pending row and compares `created_at` and `password_hash`, so a re-registration landing in that gap gives `registration_changed` and never an account with the wrong password. Two concurrent confirms of the same registration still create exactly one account. The second gets 409 `email_taken` if both pass the code check before either commits, or `code_expired` if the first has already deleted the pending row.
  - `PyJWKClient`'s key cache is shared across thread-pool workers. PyJWT guards its cache with a lock, and the worst case is a duplicate fetch.
  - The verifiers and the revocation client hold no other mutable state.
- **[Clock skew]** 60 seconds of leeway on `exp` and `iat`. The 5-minute freshness window for deletion uses the server clock.
- **[Configuration mistakes]** A wrong `GOOGLE_CLIENT_IDS` shows up as 401 `invalid_provider_token` on every Google sign-in. The README lists which client ID goes where, and the server logs the rejected audience (not the token) at WARNING.
- **[Can't test against real providers in CI]** All provider calls are behind fakes. Real sign-in is covered only by the manual tasks, which stay unticked until the consoles exist.

## Migration Plan

1. Deploy the server and the app together. The old app expects registration to return a session, and the new server answers 202. The first start migrates `app.db` to schema version 4.
2. Until `GOOGLE_CLIENT_IDS` and `APPLE_BUNDLE_ID` are set, the provider endpoints answer 503 and the app hides the buttons (its `.env` keys are blank). Nothing changes for current users.
3. After the consoles are set up, fill in the server settings and the app's `.env` and xcconfig, and rebuild the app.
4. Rollback: redeploy the previous server and app. The extra tables and columns are ignored. `email_codes` and `email_sends` would need recreating in their version-3 shape, which `_migrate()` does not do when going backwards. A rollback should therefore restore a backup of `app.db` taken before the upgrade.
