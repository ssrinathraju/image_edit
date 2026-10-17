# Tasks

Work on branch `feat/add-email-verification-and-reset`. Do not push to `main`. Server tasks run in `server/` and app tasks in `app/`. "Decision N" refers to `design.md`.

## 1. Server: settings and email senders

- [x] 1.1 Add the SMTP and email-code settings from Decision 1 to `configs/settings.py`, with startup validation for three cases: `SMTP_HOST` set with an empty `SMTP_FROM`, an unknown `SMTP_SECURITY`, and any numeric email setting below 1. Verify that `tests/configs/test_settings.py` asserts every default, one environment override, and each refusal.
- [x] 1.2 Add `core/email_sender.py` (the `EmailSender` protocol), `services/email/log_sender.py` and `services/email/smtp_sender.py` (stdlib `smtplib`, `starttls`/`ssl`/`none`, 10-second timeout, login only when a username is set). Verify:
  - `tests/services/email/test_log_sender.py` checks with `caplog` that recipient, subject and body are logged.
  - `tests/services/email/test_smtp_sender.py` replaces `smtplib.SMTP`/`SMTP_SSL` with a fake and checks host, port, STARTTLS use, login, and the sent message's `From`/`To`/`Subject`/body for each security mode.
- [ ] 1.3 Make the sender injectable in the app factory in `main.py`. Choose the SMTP sender when `SMTP_HOST` is set, otherwise the log sender, and log a startup warning when the log sender is chosen. Verify `tests/test_main.py` covers both choices, the warning, and an injected sender being used.

## 2. Server: schema migration and store operations

- [ ] 2.1 In `repos/user_store.py`:
  - Add the `email_verified` and `referral_bonus_pending` columns and the `email_codes` and `email_sends` tables, following Decision 3.
  - On first add, mark existing users verified in the same transaction.
  - Set `SCHEMA_VERSION = 3`.
  - Add `email_verified` to the `User` dataclass and to every query that builds a `User`.

  Verify that `tests/repos/test_user_store_migration.py` covers:
  - a fresh database;
  - a version-2 database with users, sessions and paid referrals: users become verified, bonuses and sessions are unchanged, and pending stays 0;
  - running the migration twice changing nothing.
- [ ] 2.2 Add `issue_code(...)` and `consume_code(...)` to `SqliteUserStore` and the `UserStore` protocol, following Decision 4, with an injected clock. Verify `tests/repos/test_user_store_codes.py` covers each of the following:
  - a new code replacing the old one;
  - purposes being independent;
  - reuse after `ok` being rejected;
  - expiry at 15 and 16 minutes;
  - 5 wrong attempts making the correct code `expired`;
  - a new code resetting attempts;
  - the 60-second limit with a correct `retry_after`;
  - the 5-per-hour cap counting both purposes;
  - the cap freeing after 61 minutes;
  - old send rows being pruned;
  - rows being removed when the user is deleted;
  - the stored hash not containing the digits;
  - two threads consuming the same code with exactly one `ok`.
- [ ] 2.3 Change `register_user` to stop paying rewards: insert 0 bonus credits and set `referral_bonus_pending` when a valid code is used. Add `mark_email_verified(user_id, bonus, max_rewards)` following Decision 5. Verify `tests/repos/test_user_store_referrals.py` is updated to cover:
  - registration paying nothing;
  - verification paying both accounts;
  - a second call paying nothing;
  - the referrer cap;
  - a deleted referrer still letting the friend be paid;
  - an account without a referral getting nothing.
- [ ] 2.4 Add `reset_password(user_id, code, new_hash, now, bonus, max_rewards)` following Decision 6. Verify `tests/repos/test_user_store_reset.py` covers:
  - success changing the hash, deleting all sessions, verifying the account and paying a pending referral;
  - a wrong code changing nothing and counting an attempt;
  - an expired code changing nothing.

## 3. Server: email code service

- [ ] 3.1 Add `services/email_code_service.py`: generate a code, hash it, call `issue_code`, and return the result. Add `deliver(sender, to, purpose, code)`, which composes the subject and body (Decision 9), sends, and catches and logs every exception without the code. Verify `tests/services/test_email_code_service.py` covers:
  - 6-digit output;
  - the body containing the code and the minutes;
  - `limited` being passed through with `retry_after`;
  - a raising sender being logged without the code and not raising.

## 4. Server: registration, verification and `/me`

- [ ] 4.1 Wire registration to issue a verification code and schedule `deliver` with `BackgroundTasks`. Add `email_verified` to `AuthResponse` (register, login) and `MeResponse`. Verify `tests/api/test_auth.py` and `tests/api/test_me.py` cover:
  - register returning `email_verified: false` and the injected recording sender receiving one email with a 6-digit code;
  - login reporting the status;
  - `/me` reporting false, then true after verification;
  - no response containing the code.
- [ ] 4.2 Add `POST /auth/verify-email` and `POST /auth/verify-email/resend` to `api/auth.py` and `auth_service.py`, following the specs. Map:
  - `wrong` to 400 `invalid_code`;
  - `expired` to 400 `code_expired`;
  - an already verified account to 409 `already_verified`;
  - `limited` to 429 `too_many_requests` with `Retry-After`.

  Verify `tests/api/test_email_verification.py` covers every scenario in the `user-auth` delta for these two requirements, plus 401 without a session.
- [ ] 4.3 Update `tests/integration/test_referral_flow.py`:
  - A registers, and B registers with A's code and does not verify: both have 0 bonus.
  - B verifies with the code captured from the recording sender: both have 5.
  - B later resets the password: no further bonus.
  - C registers with A's code, A is deleted, and C verifies: C has 5.
  - The 11th verified friend of A is paid while A is not.

  Verify that the test passes.

## 5. Server: password reset

- [ ] 5.1 Add `POST /auth/password-reset/request`, following Decision 7: format check, then `issue_code` only for an existing account, a scheduled send, and always 202 `{}`. Verify `tests/api/test_password_reset.py` covers:
  - a registered email in mixed case receiving a code;
  - an unknown email getting a byte-identical response and no email;
  - a limited request getting a byte-identical response and no email;
  - a malformed email getting 400 `invalid_credentials_format`.
- [ ] 5.2 Add `POST /auth/password-reset/confirm`, following Decision 6. Verify `tests/api/test_password_reset.py` covers:
  - success returning a working token;
  - the new password logging in and the old one getting 401;
  - both earlier sessions being revoked;
  - an unverified account becoming verified;
  - a lockout being cleared;
  - unknown email, wrong code and expired code all giving the identical 400 `invalid_code`;
  - 5 weak-password requests followed by a valid one succeeding.
- [ ] 5.3 Add `tests/integration/test_account_recovery_flow.py` using the real app with a recording sender: register, request a reset, read the code from the sender, confirm, log in with the new password, and confirm that the earlier token gets 401. Verify that the test passes.

## 6. Server: generation gate

- [ ] 6.1 Add a test helper in `tests/helpers.py` that registers and verifies an account, by calling `mark_email_verified` on the store or by using the captured code. Switch every existing test that generates to use it. Verify the full suite passes again before 6.2.
- [ ] 6.2 Raise 403 `email_not_verified` as the first statement of `generation_service.submit`, following Decision 8. Verify `tests/api/test_generations_verified.py` covers:
  - an unverified valid request getting 403 with no job and unchanged remaining generations;
  - an unverified empty request getting 403 rather than 400;
  - success after verifying;
  - an unverified account still reading the status of a job created while verified (verify via the store, submit, then set `email_verified = 0` directly in the test database).

  Also confirm that `ls server/storage/inputs | wc -l` is unchanged by the suite.

## 7. Server: documentation

- [ ] 7.1 Update `server/README.md` with:
  - the new settings and the SMTP setup;
  - log mode, with how to find a code in the log and the warning that it must not be used with real users;
  - the four endpoints with curl examples;
  - the new error codes;
  - `email_verified` on the register, login and `/me` responses;
  - the 403 on generation;
  - the referral change;
  - the note that the first start marks existing accounts verified.

  Verify by running each curl example against a local server in log mode.

## 8. App: schemas, client, errors

- [ ] 8.1 Add `emailVerified` to `Session`/`AuthResponse` parsing and to `UserProfile`, defaulting to `true` when absent. Add `verifyEmail`, `resendVerification`, `requestPasswordReset` and `confirmPasswordReset` to `core/api_client.dart`. Add the five error codes and the `Retry-After` parsing to `core/api_errors.dart`. Verify:
  - `test/schemas/account_test.dart` covers both the present and absent cases;
  - `test/core/api_client_test.dart` covers each request's path and body and the reset-confirm session parsing;
  - `test/core/api_errors_test.dart` covers each code and `Retry-After`.

## 9. App: verification flow

- [ ] 9.1 Add `justRegistered` to `SessionNotifier`. Update `router.dart`: add the three routes, the signed-out allow-list, and the redirect to `/verify-email` after registration, following Decision 10. Verify `test/router_test.dart` covers:
  - registration landing on `/verify-email`;
  - login landing on `/`;
  - a signed-out visit to `/forgot-password` and `/reset-password` being allowed;
  - a signed-out visit to `/verify-email` redirecting to `/login`.
- [ ] 9.2 Add `features/auth/verify_email_screen.dart` (code field, submit, Resend with countdown, Later) with the states in the Decision 10 table. Verify `test/features/auth/verify_email_screen_test.dart` covers:
  - submit disabled until 6 digits;
  - success refreshing the account and going home;
  - `invalid_code`, `code_expired` and 429 messages;
  - Resend disabled during the countdown and enabled after it, using a fake clock or `tester.pump(Duration)`;
  - Later going home.
- [ ] 9.3 Add the verification banner to `home_screen.dart`, and handle `email_not_verified` in `features/common/submit_flow.dart` by pushing `/verify-email`. Verify:
  - `test/features/home/home_screen_test.dart` covers the banner being shown when unverified, hidden when verified and hidden while loading, and the tap navigating.
  - `test/features/common/submit_flow_test.dart` covers the Verify screen opening on 403 and the photo and prompt being kept after returning.

## 10. App: password reset flow

- [ ] 10.1 Add the Forgot password link to `login_screen.dart`, passing the typed email. Add `features/auth/forgot_password_screen.dart`. Verify `test/features/auth/forgot_password_screen_test.dart` covers the prefilled email, submit navigating to `/reset-password?email=…` with the "if an account exists" text, and the malformed-email error.
- [ ] 10.2 Add `features/auth/reset_password_screen.dart`: code, new password, the short-password inline message, Resend with countdown, and storing the session on success. Verify `test/features/auth/reset_password_screen_test.dart` covers success storing the session, `invalid_code` keeping the values, a short password disabling submit, and Resend calling the request endpoint.

## 11. Integration and hand-off

- [ ] 11.1 Run `uv run pytest -q` in `server/` and `flutter analyze && flutter test` in `app/`. Verify that all pass with zero analyzer warnings and that the storage pollution check is unchanged. Then run `openspec validate add-email-verification-and-reset --strict`.
- [ ] 11.2 **Manual.** On the iOS simulator, with a local server in log mode started on a copy of an existing `app.db`, check each of the following:
  - An old account is still verified and can generate.
  - Register a new account with a referral code: the app lands on Verify email, and the home banner shows after Later.
  - Generating while unverified opens the Verify screen.
  - Enter the code from the server log: the banner disappears and both accounts show +5.
  - Resend shows the countdown.
  - Forgot password: the code from the log and a new password land on home, and the old session on a second simulator is signed out.

  This box stays unticked until someone runs the whole list. Name any step that was not run in the PR.
- [ ] 11.3 **Manual, optional.** Set `IMAGE_EDIT_SMTP_*` to a real or test SMTP account (for example Mailtrap or a Gmail app password), register, and confirm that the email arrives with the code. This box stays unticked unless it was actually run.
- [ ] 11.4 Push `feat/add-email-verification-and-reset`. Verify with `git log origin/feat/add-email-verification-and-reset -1` that it matches the local HEAD.
