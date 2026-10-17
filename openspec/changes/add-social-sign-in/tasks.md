# Tasks

Work on branch `feat/add-social-sign-in`. Do not push to `main`. Server tasks run in `server/` and app tasks in `app/`. "Decision N" refers to `design.md`. No test may call Google or Apple over the network.

## 1. Server: dependency, settings and verifiers

- [x] 1.1 Add `pyjwt[crypto]` with `uv add` and add the settings from Decision 7, with their startup checks. Verify that `uv run python -c "import jwt, cryptography"` succeeds and that `tests/configs/test_settings.py` covers:
  - every default;
  - `GOOGLE_CLIENT_IDS` parsed from the environment;
  - the refusals for partial Apple key settings, key settings without a bundle ID, and an unreadable key file.
- [x] 1.2 Add `core/identity_verifier.py` (`IdentityVerifier`, `ProviderIdentity`, `InvalidProviderToken`, `ProviderUnavailable`), and `services/identity/google_verifier.py` and `services/identity/apple_verifier.py`, following Decision 1, each taking an injectable JWKS client. Add a test helper in `tests/helpers.py` that makes an RSA key, a fake JWKS client, and signed Google and Apple tokens with any claims. Verify that `tests/services/identity/test_google_verifier.py` and `test_apple_verifier.py` cover:
  - a valid token;
  - each issuer form;
  - a wrong audience;
  - an expired token;
  - a token just inside the 60-second leeway;
  - a bad signature;
  - an unknown `kid`;
  - `alg=none` and HS256 being rejected;
  - a nonce match and mismatch (Apple);
  - a JWKS fetch failure raising `ProviderUnavailable`.

## 2. Server: storage

- [x] 2.1 In `repos/user_store.py` add the `identities` table, the `created_via` and `referral_redeemed` columns and `SCHEMA_VERSION = 4`, following Decision 2. Expose `has_password` on `User` (from `password_hash != ''`) and add `list_providers(user_id)`. Verify that `tests/repos/test_user_store_migration.py` covers:
  - a fresh database;
  - a version-3 database with verified users, sessions, email codes and a paid referral: all data is kept, `created_via` is `password`, and there are no identities;
  - running the migration twice changing nothing.
- [x] 2.2 Add `sign_in_with_identity(...)` with `ProviderEmailMissing`, `ProviderEmailUnverified` and `ProviderAlreadyLinked` in `core/user_store.py`, following Decision 3. Verify that `tests/repos/test_user_store_identities.py` covers each of the following:
  - a linked identity returning its user with an unchanged email;
  - linking by mixed-case email to a password account, with the password kept;
  - linking verifying an unverified account and paying its pending referral once;
  - creating a verified account with no password and a referral code;
  - an Apple relay email becoming the account email;
  - a missing email for an unknown identity;
  - an unverified Google email writing nothing;
  - a second Google identity for the same account raising `ProviderAlreadyLinked`;
  - two threads signing in the same new identity, which creates exactly one account;
  - identities being deleted with their user.
- [x] 2.3 Add `redeem_referral(...)` with `ReferralNotAllowed`, following Decision 6. Verify that `tests/repos/test_user_store_referrals.py` covers:
  - success paying both accounts;
  - lowercase codes with spaces;
  - a second redemption being refused;
  - a password-created account being refused;
  - 23 hours being accepted and 25 hours refused (with an injected clock);
  - the account's own code and an unknown code changing nothing;
  - the referrer cap.
- [x] 2.4 Add `set_apple_refresh_token(user_id, token)` and `get_apple_refresh_token(user_id)`. Verify with a test in `test_user_store_identities.py` that the token is stored for the Apple identity only and is gone after the user is deleted.

## 3. Server: Apple code exchange and revocation

- [x] 3.1 Add `services/apple_revocation.py`, following Decision 4: build the client secret with ES256, `exchange_code(code) -> refresh_token | None`, and `revoke(token)`, all through an injectable `post(url, form) -> (status, body)` that uses `urllib.request` by default with a 10-second timeout. Every failure is logged without token or code text. Verify that `tests/services/test_apple_revocation.py`, using a generated EC P-256 key, covers:
  - the client-secret claims and header (`kid`, ES256);
  - a successful exchange returning the refresh token;
  - a non-200 or raising `post` returning None and logging without the code;
  - `revoke` sending the right form;
  - a raising `post` in `revoke` being logged and not raised.

## 4. Server: sign-in endpoints

- [x] 4.1 Add the `POST /auth/oauth/google` and `POST /auth/oauth/apple` handlers and the `AuthService.sign_in_with_provider(...)` service method, following Decisions 3, 4 and 8. Wire the verifiers and the revocation client in `main.py` with injection points for tests, and log the startup warning when the Apple key settings are absent. Verify that `tests/api/test_social_sign_in.py` covers, through HTTP with fake verifiers and fake `post`, every scenario in `specs/social-sign-in/spec.md` for:
  - Sign in with Google;
  - Sign in with Apple;
  - Find, link, or create the account;
  - Accounts reached through a provider are verified;
  - Require a provider-verified email;
  - Refuse unconfigured providers;
  - Report an unreachable provider;
  - One identity per provider per account;
  - Keep provider tokens secret.

  It must also check that an Apple sign-in stores the refresh token from a successful exchange and retries the exchange on the next sign-in after a failed one.
- [x] 4.2 Extend `MeResponse` and `GET /me` with `providers` and `has_password`. Verify that `tests/api/test_me.py` covers a password account, a Google-created account, and a password account linked to Google.
- [x] 4.3 Verify the "Accounts without a password" requirement in `tests/api/test_auth.py`:
  - password login on a Google-created account gives a 401 identical to a wrong password;
  - a password reset on it then allows password login;
  - Google sign-in still reaches the same account.

## 5. Server: deletion and referral redemption

- [x] 5.1 Change `DeleteAccountRequest` and `AuthService.delete_account` to accept the provider form, following Decision 5. Schedule Apple revocation after the delete. Verify that `tests/api/test_delete_account.py` (new, or extend the existing file) covers:
  - the existing password scenarios still passing;
  - a Google-only account deleting with a fresh token, after which a new Google sign-in creates a new account;
  - a 10-minute-old token getting 403;
  - another identity's token getting 403;
  - a password on a provider-only account getting 403;
  - a request with neither form or with both forms getting 422;
  - an Apple-linked deletion calling `revoke` with the stored token;
  - a raising `revoke` still giving 204 with the account gone.
- [x] 5.2 Add `POST /me/referral` and `ReferralService.redeem(...)`. Verify that `tests/api/test_referral_redeem.py` covers every scenario of "Redeem a referral code after a provider sign-up".
- [x] 5.3 Add `tests/integration/test_social_flow.py` using the real app with fake verifiers. The flow:
  1. A Google sign-in creates an account (`created` true).
  2. It redeems a friend's code, and both accounts have +5.
  3. It submits a generation, which is accepted.
  4. The same identity signs in again (`created` false).
  5. A password account with the same email as a second Google identity links.
  6. The first account deletes with a fresh token, and its old session gets 401.

  Verify that it passes and that `ls server/storage/inputs | wc -l` is unchanged by the suite.

## 6. Server: documentation

- [x] 6.1 Update `server/README.md` with:
  - the new settings and which Google client ID goes where (iOS, Android, web/server);
  - the Apple key setup and the revocation warning;
  - the three endpoints with curl examples (the provider tokens shown as placeholders);
  - the new `DELETE /me` form;
  - the new `/me` fields and error codes;
  - a "console setup checklist" for Google Cloud and Apple Developer.

  Add a `todo.md` line for encrypting the stored Apple refresh token. Verify by running the `/me/referral` and unconfigured-provider (503) curl examples against a local server.

## 7. App: config, client, errors and provider sign-in

- [x] 7.1 Add `GOOGLE_IOS_CLIENT_ID=`, `GOOGLE_SERVER_CLIENT_ID=` and `APPLE_SIGN_IN=` to `.env.example` and `.env`. Add the matching getters and the button-visibility rules from Decision 9 to `AppConfig`. Verify that `test/configs/app_config_test.dart` covers blank and set values and each visibility rule, with the platform injected.
- [x] 7.2 Add `signInWithGoogle`, `signInWithApple`, `redeemReferral`, and the provider form of `deleteAccount` to `core/api_client.dart`. Parse `created`, `providers` and `hasPassword` (defaulting to `[]`, and to `true` when absent). Add the seven error codes to `core/api_errors.dart`. Verify that `test/core/api_client_test.dart`, `test/core/api_errors_test.dart` and `test/schemas/account_test.dart` cover each request's path and body and each parsed field.
- [x] 7.3 Add the packages (`flutter pub add google_sign_in sign_in_with_apple crypto`), `core/provider_sign_in.dart` with the Google and Apple implementations and Riverpod providers (Decision 9), and the iOS native setup:
  - `Runner.entitlements` with Sign in with Apple, referenced from the project;
  - a `CFBundleURLTypes` entry using `$(GOOGLE_REVERSED_CLIENT_ID)`;
  - `ios/Flutter/GoogleSignIn.xcconfig.example`, plus a `.gitignore` entry for the real file, included from the Debug and Release xcconfigs.

  Verify:
  - `test/core/provider_sign_in_test.dart` covers the Apple nonce being 32 random bytes whose SHA-256 is what Apple receives, and a cancelled sheet returning null, using package fakes.
  - `flutter build ios --no-codesign --debug` succeeds with an empty value in the example xcconfig copied to `GoogleSignIn.xcconfig`.

## 8. App: sign-in buttons and referral prompt

- [x] 8.1 Add `signInWithProvider` and `justCreatedViaProvider` to `SessionNotifier`. Update `router.dart` with `/referral-prompt` and the redirect. Verify that `test/router_test.dart` covers:
  - a new provider account landing on `/referral-prompt`;
  - an existing one landing on `/`;
  - email/password registration still landing on `/verify-email`.
- [x] 8.2 Add the Continue with Google and Continue with Apple buttons to `login_screen.dart` and `register_screen.dart` (a shared widget in `features/auth/provider_buttons.dart`) with the states in the Decision 9 table. Verify that `test/features/auth/provider_buttons_test.dart`, with overridden `ProviderSignIn` providers, covers:
  - Google success going home;
  - the Apple button hidden on Android and when not configured;
  - Google hidden when not configured;
  - a cancel showing nothing;
  - each server error message.
- [x] 8.3 Add `features/auth/referral_prompt_screen.dart`. Verify that `test/features/auth/referral_prompt_screen_test.dart` covers:
  - Apply success refreshing the account and going home;
  - `invalid_referral_code` keeping the value;
  - `referral_not_allowed` going home;
  - Skip going home without a request;
  - Apply disabled while the field is empty.

## 9. App: profile

- [x] 9.1 Add the provider line to `profile_screen.dart`, and change Delete account to use the provider sign-in when `hasPassword` is false (Decision 9). Verify that `test/features/profile/profile_screen_test.dart` covers:
  - "Signed in with Google" shown, and no line for a password-only account;
  - a provider-only delete running the overridden Google sign-in and calling `deleteAccount` with the token, then the sign-in screen;
  - a cancelled provider sign-in staying on the profile with no error;
  - `invalid_provider_token` showing the message;
  - a password account still using the password dialog.

## 10. Integration and hand-off

- [ ] 10.1 Run `uv run pytest -q` in `server/` and `flutter analyze && flutter test` in `app/`. Verify that all pass with zero analyzer warnings and an unchanged storage pollution check. Then run `openspec validate add-social-sign-in --strict`.
- [ ] 10.2 **Manual. Needs the Google Cloud OAuth clients, the Apple Developer App ID and key, and final bundle IDs.** Configure the server settings, the app `.env` and the xcconfig, then check:
  - iOS simulator or device:
    - Continue with Google creates an account and shows the referral prompt.
    - Skip goes home.
    - Signing out and in again goes straight home.
    - Continue with Apple, with "Hide my email", creates an account with a relay address.
    - Delete the Apple account by re-signing in with Apple, and confirm under Settings → Apple ID → Sign-In & Security that the app's authorization was removed.
  - Android emulator with Google Play services: Continue with Google works, and there is no Apple button.
  - A Google sign-in whose email matches an existing password account links to it, and the profile shows "Signed in with Google".

  This box stays unticked until someone runs every step. Name any skipped step in the PR.
- [ ] 10.3 Push `feat/add-social-sign-in`. Verify with `git log origin/feat/add-social-sign-in -1` that it matches the local HEAD.
