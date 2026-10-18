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

## 10. Server: registration before the account exists (added after round-1 review)

Groups 10 to 12 implement design Decisions 10 and 11 and the revised specs. Earlier ticked tasks stay ticked. Where their tests cover behaviour these groups remove, the tests are rewritten or deleted here.

- [x] 10.1 Schema: add `pending_registrations`, recreate `email_codes` and `email_sends` keyed by email (purposes `registration` and `password_reset`), and mark unverified accounts verified, all in the v4 migration (design Decision 2). New users keep writing `email_verified = 1`. Account deletion removes that email's code and send rows in the same transaction. Verify that `tests/repos/test_user_store_migration.py` covers:
  - a v3 database with an unverified account, which comes out verified and can log in;
  - the code tables recreated in their new shape;
  - running the migration twice changing nothing;

  and that `tests/repos/test_user_store_codes.py` is updated so codes and limits are per email, including the 5-per-hour cap counting registration and reset together.
- [x] 10.2 Store operations `start_registration(...)` and `confirm_registration(...)`, following Decision 10. Verify that `tests/repos/test_user_store_registration.py` covers:
  - start storing a pending row and a code;
  - a second start after 60 s replacing both;
  - a second start within 60 s being limited and keeping the first;
  - confirm creating a verified user with the pending password and deleting the pending row;
  - a wrong code counting an attempt;
  - an expired code, and confirming with no pending row;
  - an email taken meanwhile giving `email_taken` and deleting the pending row;
  - the referral paid to both at creation;
  - a referrer deleted meanwhile paying only the new account;
  - two threads confirming the same registration creating exactly one account;
  - old pending rows pruned after 24 hours.
- [x] 10.3 Endpoints: change `POST /auth/register` to the pending flow (202, or 429 with `Retry-After`), add `POST /auth/register/confirm` (201 with `AuthResponse`), and drop `email_verified` from `AuthResponse`. Verify that `tests/api/test_auth.py` covers every scenario of "Start a registration" and "Complete registration with the emailed code", using the recording sender to read codes, and that no response contains a code.
- [x] 10.4 Provider linking: remove the verification transition from `sign_in_with_identity` (Decision 3), delete any pending registration for an email when a provider creates its account, and apply the `email_verified` rule to Apple, accepting the boolean `true` or the string `"true"` only. Verify that:
  - `tests/services/identity/test_apple_verifier.py` covers the claim being missing, `false`, `"false"`, `true` and `"true"`;
  - `tests/api/test_social_sign_in.py` covers "Apple email without a verified claim is refused" and "Apple string claim is accepted";
  - `tests/api/test_auth.py` covers a pending registration confirmed after Google created the account giving 409, with the Google account unchanged.

## 11. Server: remove the unverified-account machinery

- [x] 11.1 Delete `POST /auth/verify-email` and `/resend`, the `email_not_verified` gate in `generation_service.submit`, `mark_email_verified` and the `referral_bonus_pending` logic, `email_verified` in `MeResponse`, and the verification step in password reset (Decision 11). Update `tests/conftest.py` fixtures and `tests/helpers.py` so accounts are created through the store or through register-then-confirm. Delete or rewrite the tests of removed behaviour, including `tests/api/test_email_verification.py` and `tests/api/test_generations_verified.py`. Verify:
  - `grep -rn "email_not_verified\|verify-email\|mark_email_verified\|referral_bonus_pending" server/src` finds nothing except the schema column definition;
  - the full suite passes;
  - `tests/integration/test_referral_flow.py` and `test_account_recovery_flow.py` pass against the new registration flow.
- [x] 11.2 Update `server/README.md`: the two-step registration with curl examples, the removed endpoints and fields, codes keyed per address, the v4 migration note (unverified accounts become verified, and back up `app.db` before upgrading because a rollback needs the backup). Verify by running the register and confirm curl examples against a local server in log mode. Start it on a port you choose and stop only that process.

## 12. App: confirm registration and removals

- [x] 12.1 Client and schemas: `register` returns nothing on 202, add `confirmRegistration(email, code)` returning the session, remove `verifyEmail` and `resendVerification`, and remove `emailVerified` from `Session` and `UserProfile`. Remove the `email_not_verified` and `already_verified` codes. Verify with `test/core/api_client_test.dart`, `test/core/api_errors_test.dart` and `test/schemas/account_test.dart`.
- [x] 12.2 Add `registrationDraftProvider` (in memory), `features/auth/confirm_registration_screen.dart`, and the `/confirm-registration` route (allowed while signed out, and redirecting to `/register` without a draft). Change `register_screen.dart` to push it on success. Remove `justRegistered`, `verify_email_screen.dart` and its route. Follow the states in the Decision 9 table. Verify:
  - `test/features/auth/confirm_registration_screen_test.dart` covers every scenario of "Confirm registration with the emailed code", including Back keeping the values;
  - `test/router_test.dart` covers registration landing on `/confirm-registration` with no session, and a session after confirm landing on `/`.
- [x] 12.3 Remove the home banner and the `email_not_verified` handling in `features/common/submit_flow.dart`. Make the `provider_email_unverified` message in `provider_buttons.dart` name the provider used. Verify:
  - the home and submit-flow tests are updated;
  - `test/features/auth/provider_buttons_test.dart` covers the Apple message naming Apple;
  - `grep -rn "emailVerified\|verify-email\|email_not_verified" app/lib` finds nothing.

## 13. Fixes from the round-2 review (S1, S2, S3)

- [x] 13.1 Server, S1: `POST /auth/register/confirm` takes `password` and follows the three-step confirm in Decision 10: check the code under the lock, check the password outside it, then commit after re-reading the pending row. A mismatch or a changed row gives 409 `registration_changed` and discards the pending row and its code. Verify that `tests/api/test_auth.py` and `tests/repos/test_user_store_registration.py` cover:
  - the scenario "Someone else's re-registration cannot set the password", end to end with the recording sender;
  - "Password is checked only after the code" (a wrong code with a wrong password gives `invalid_code` and keeps the pending row);
  - a re-registration landing between the password check and the commit giving `registration_changed`, by injecting a hook or a fake clock between the steps;
  - two confirms of the same registration creating exactly one account;
  - the S1 reproduction no longer succeeding, as a regression test (the reviewer's script was `/private/tmp/claude-501/-Users-srinathraju-Documents-workspace-image-edit/176d5f78-e998-4ffc-962d-0b0aa407cee8/scratchpad/repro_overwrite.py`, if still present).
- [ ] 13.2 App, S1: `confirmRegistration(email, code, password)` sends the draft's password. Add the `registration_changed` code to `api_errors.dart`. On that error, the Confirm screen pops to the registration screen with the values kept and the message from the Decision 9 table. Also clear the registration draft whenever the user leaves the registration flow: signing in, or leaving the register screen by any route (reviewer nit). Verify that `test/features/auth/confirm_registration_screen_test.dart` covers the password being sent and the `registration_changed` path, and that a test shows the draft is gone after Back then Sign in.
- [x] 13.3 Server, S2: prune expired `email_codes`, `email_sends` older than an hour, and `pending_registrations` older than 24 hours, for all addresses, inside `start_registration` and `issue_code` and once at startup (Decision 12). Verify with `tests/repos/test_user_store_registration.py`: an abandoned address is gone from all three tables after 30 days plus another registration, and after a restart with no other activity (using an injected clock). Turn the reviewer's reproduction (`/private/tmp/claude-501/-Users-srinathraju-Documents-workspace-image-edit/176d5f78-e998-4ffc-962d-0b0aa407cee8/scratchpad/repro_retention.py`, if still present) into a regression test.
- [x] 13.4 Server, S3: remove the module-level `app = create_app()` from `main.py`, run the server with `uvicorn --factory image_edit_server.main:create_app` (update `server/README.md` and any run script), and keep every test on temporary storage. Verify:
  - a test asserts that importing `image_edit_server.main` creates no file under the default `./storage`;
  - `md5` of `server/storage/app.db` (if present) is unchanged by a full `uv run pytest -q`;
  - the README's run command starts the server.

## 14. Integration and hand-off

- [ ] 14.1 Run `uv run pytest -q` in `server/` and `flutter analyze && flutter test` in `app/`. Verify that all pass with zero analyzer warnings and an unchanged storage pollution check. Then run `openspec validate add-social-sign-in --strict`.
- [ ] 14.2 **Manual, no consoles needed.** On the iOS simulator against a local server in log mode, started on a copy of a **pre-upgrade** `app.db` that holds an unverified account (the working copy has already been migrated by test runs before 13.4; if no older copy exists, skip the first step and say so in the PR):
  - The unverified account signs in and can generate.
  - Register a new email with a referral code: the Confirm registration screen opens with no session. Back shows the values kept. Resend shows the countdown.
  - Enter the code from the server log: home opens and both accounts show +5.
  - A wrong code shows "Code is incorrect".

  This box stays unticked until someone runs every step.
- [ ] 14.3 **Manual. Needs the Google Cloud OAuth clients, the Apple Developer App ID and key, and final bundle IDs.** Configure the server settings, the app `.env` and the xcconfig, then check:
  - iOS simulator or device:
    - Continue with Google creates an account and shows the referral prompt.
    - Skip goes home.
    - Signing out and in again goes straight home.
    - Continue with Apple, with "Hide my email", creates an account with a relay address.
    - Delete the Apple account by re-signing in with Apple, and confirm under Settings → Apple ID → Sign-In & Security that the app's authorization was removed.
  - Android emulator with Google Play services: Continue with Google works, and there is no Apple button.
  - A Google sign-in whose email matches an existing password account links to it, and the profile shows "Signed in with Google".

  This box stays unticked until someone runs every step. Name any skipped step in the PR.
- [ ] 14.4 Push `feat/add-social-sign-in`. Verify with `git log origin/feat/add-social-sign-in -1` that it matches the local HEAD.
