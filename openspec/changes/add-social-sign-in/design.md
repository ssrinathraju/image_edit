# Design

## Context

See `proposal.md` for the motivation and `specs/` for the behaviour contract. The current state that matters here:

- **Accounts.** These live in SQLite through `repos/user_store.py` (`SqliteUserStore`, schema version 3).
  - `users.password_hash` is `TEXT NOT NULL`.
  - `_migrate()` adds missing columns by checking `PRAGMA table_info`, in one transaction.
  - Every store method runs under `self._lock` in a single transaction.
- **Verification and referrals.** `mark_email_verified` pays a pending referral on the first 0→1 transition (the `add-email-verification-and-reset` design, Decision 5).
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
- **`SCHEMA_VERSION = 4`.** The column and table checks decide what runs, as before.

- **Alternative rejected: rebuilding `users` to make `password_hash` nullable.** SQLite cannot drop `NOT NULL` without copying the table, and several tables reference `users` with foreign keys. An empty-string sentinel is safe because the verifier already treats it as invalid.

### 3. Find, link or create in one store transaction
`sign_in_with_identity(identity, now, bonus, max_rewards) -> (User, created)` runs under the lock in one transaction:
1. If `(provider, subject)` exists, return its user. The account's email is not changed.
2. Otherwise, if no account is linked and the token has no email, raise `ProviderEmailMissing`. If Google's `email_verified` is not true, raise `ProviderEmailUnverified`. These checks happen before any write.
3. If a user has that email (lowercased):
   - If they already have an identity of this provider, raise `ProviderAlreadyLinked`.
   - Otherwise insert the identity, run the verification transition (Decision 5 of the email-verification design, which may pay a pending referral), and return them with `created=False`.
4. Otherwise insert a user with:
   - the lowercased email;
   - `password_hash = ''`;
   - `email_verified = 1`;
   - `created_via = provider`;
   - a new referral code.

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
- **Both** return `AuthResponse` plus `created: bool`. Login and register keep their current shape.
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
- `SessionNotifier` gains `signInWithProvider(credential)` and `justCreatedViaProvider`. The redirect sends that state to `/referral-prompt`, using the same mechanism as `justRegistered`.
- The prompt screen clears the flag in `initState`.
- `api_errors.dart` adds the seven new codes.

Deletion in the app: when `hasPassword` is false, `profile_screen.dart` runs the linked provider's sign-in. That is Apple if the account is linked to Apple and the app is on iOS, otherwise Google. It then calls `deleteAccount(provider:, token:, nonce:)`. A cancelled sign-in returns to the profile silently.

Screen states:

| Screen | Loading | Empty / initial | Error | Success |
|---|---|---|---|---|
| Sign-in and register (provider buttons) | The tapped button shows a spinner, and all submit controls are disabled while in flight | Buttons hidden for unconfigured providers; Apple hidden on Android | `invalid_provider_token`: "Sign-in failed, try again". `provider_email_unverified`: "Verify your Google email first". `provider_email_missing`: "Apple didn't share an email; remove this app in Apple ID settings and try again". `provider_already_linked`: "This account is already linked to another Google account". 503: "Sign-in is unavailable right now". Cancel: nothing shown | Session stored. New account goes to `/referral-prompt`, an existing one to `/` |
| Referral prompt | Apply shows a spinner and is disabled | Code field empty, Apply disabled | `invalid_referral_code`: "Code not recognised", value kept. `referral_not_allowed`: "This account can't redeem a code", then go home | Account refreshed, go to `/` |
| Profile provider line | Hidden while the account loads | Hidden when there are no providers | Hidden if the account failed to load | "Signed in with Google" and/or "Signed in with Apple" |
| Profile, Delete account | Spinner during the provider sign-in and the delete | Confirmation dialog; password field only when `hasPassword` | Wrong password: "Password is incorrect". `invalid_provider_token`: "Couldn't confirm with Google/Apple". Cancel: nothing shown | Session cleared, sign-in screen |

## Risks / Trade-offs

- **[What data is stored, and for how long]**
  - An `identities` row per linked provider holds the provider subject, the email reported when it was linked, and for Apple a refresh token. It lives as long as the account and is removed by the cascade on deletion.
  - `created_via` and `referral_redeemed` live as long as the account.
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
  - The first start adds two columns and one table in one transaction, and a re-run changes nothing.
  - Existing accounts keep their passwords and get `created_via = 'password'`.
  - Rollback: the version-3 server ignores the extra table and columns. Provider-only accounts (empty hash) then simply cannot log in until a password reset.
- **[Linking by email]**
  - Anyone controlling a Google account with a verified address matching an existing account gets into that account. This is the industry-standard trade-off, and it depends on the provider's verification.
  - Unverified Google emails are refused. Apple relay addresses never match a password account.
- **[Failure and retry]**
  - A provider's key endpoint being down → 503 `provider_unavailable`; the user retries. Cached keys keep sign-in working through short outages.
  - A failed Apple code exchange → sign-in succeeds, and the exchange is retried on the next Apple sign-in.
  - A failed revocation → logged, and the deletion has already completed. It is not retried, because there is no account left to retry from.
- **[Background tasks when a call raises]** The revocation task's wrapper catches every exception and logs it. It runs after the response and nothing depends on it.
- **[Thread-safety of shared state]**
  - Find-link-create, redemption and the provider deletion check all run under `SqliteUserStore._lock` in single transactions.
  - `PyJWKClient`'s key cache is shared across thread-pool workers. PyJWT guards its cache with a lock, and the worst case is a duplicate fetch.
  - The verifiers and the revocation client hold no other mutable state.
- **[Clock skew]** 60 seconds of leeway on `exp` and `iat`. The 5-minute freshness window for deletion uses the server clock.
- **[Configuration mistakes]** A wrong `GOOGLE_CLIENT_IDS` shows up as 401 `invalid_provider_token` on every Google sign-in. The README lists which client ID goes where, and the server logs the rejected audience (not the token) at WARNING.
- **[Can't test against real providers in CI]** All provider calls are behind fakes. Real sign-in is covered only by the manual tasks, which stay unticked until the consoles exist.

## Migration Plan

1. Deploy the server. The first start migrates `app.db` to schema version 4.
2. Until `GOOGLE_CLIENT_IDS` and `APPLE_BUNDLE_ID` are set, the provider endpoints answer 503 and the app hides the buttons (its `.env` keys are blank). Nothing changes for current users.
3. After the consoles are set up, fill in the server settings and the app's `.env` and xcconfig, and rebuild the app.
4. Rollback: redeploy the previous server. The extra table and columns are ignored.
