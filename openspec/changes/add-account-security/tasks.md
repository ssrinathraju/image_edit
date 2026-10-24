# Tasks

Work on branch `feat/add-account-security`. Do not push to `main`. Server tasks run in `server/` and app tasks in `app/`. "Decision N" refers to `design.md`. Tests use temporary storage and fakes only. Record the md5 of `server/storage/app.db` and the `server/storage/inputs` count before and after the server suite. Keep every file under `server/src` below 1000 lines.

## 1. Server: re-authentication and storage

- [x] 1.1 Extract `AuthService.reauthenticate` (Decision 1) and move `delete_account` onto it, keeping its error codes. Verify that the existing `tests/api/test_delete_account.py` passes **unchanged**, and that new `tests/services/test_reauth.py` covers: a password ok and wrong (counting toward the throttle), the throttle at 5, a fresh provider token ok, a stale one, another account's identity, and a provider-only account sending a password.
- [x] 1.2 Add the `EMAIL_CHANGE` code purpose, the `pending_email_changes` table (schema version 7), and the store methods: upsert and read pending, confirm email change (consume, email-taken check, update, delete other sessions), set the password while deleting other sessions, `link_identity`, and unlink with the last-method check. Verify:
  - repository tests cover each method, including the UNIQUE race giving taken, the last-method refusal, the current session being kept, and the cascade on account deletion;
  - the v6 to v7 migration and a re-run;
  - the email-change code counting in the per-address hourly cap.

## 2. Server: endpoints

- [x] 2.1 `POST /me/password` (Decision 2) and the "password changed" notification (Decision 5). Verify that `tests/api/test_account_security.py` covers every scenario of "Set or change the password" and "Confirm identity before a sensitive change", including the notification going to the recording sender with no code or password in it.
- [x] 2.2 `POST /me/email` and `POST /me/email/confirm` (Decision 3), plus the "email changed" notification to the old address. Verify that the tests cover every scenario of "Request an email change" and "Confirm an email change with the code": the code going to the new address, taken (both at request and at confirm), wrong or expired code, 429 with `Retry-After`, other sessions getting 401, login with the new email, and the old-address notification text.
- [x] 2.3 `POST /me/providers/{google|apple}` and `DELETE /me/providers/{provider}` (Decision 4). Verify, with fake verifiers and a fake Apple `post`, every scenario of "Link a provider to the signed-in account" and "Unlink a provider", including Apple revocation on unlink and a failing revocation not blocking it.
- [x] 2.4 Privacy and docs: a log-capture test across all endpoints asserting no password, code, token or address in the log; `server/README.md` updated with the endpoints, errors and curl examples, verified against a local stub server on a temporary storage root (your own free port, stopping only your own process).

## 3. App

- [x] 3.1 API client methods, the error codes, and `Reauth` (Decision 7). Verify with `test/core/api_client_test.dart` and `test/core/api_errors_test.dart`.
- [ ] 3.2 The security section, the re-authentication helper, and the Change or Set password screen. Verify with widget tests for both row variants, re-auth by password and by provider (and a cancelled sheet), `reauth_failed` keeping values, and the success SnackBar.
- [ ] 3.3 The Change email screen and its code step. Verify with widget tests for `email_taken`, `invalid_code`, `code_expired`, the Resend countdown, and success updating the profile email with the SnackBar.
- [ ] 3.4 Link and unlink rows. Verify with widget tests for linking (success and `provider_in_use`), unlinking (confirm then re-auth then success), `last_sign_in_method`, cancel, and the Apple row hidden on Android.

## 4. Integration and hand-off

- [ ] 4.1 Run `uv run pytest -q` in `server/`, and `flutter analyze && flutter test` in `app/`. Verify that everything passes with zero analyzer warnings, that the `app.db` md5 and `inputs` count are unchanged, and that `openspec validate add-account-security --strict` passes.
- [ ] 4.2 **Manual. iOS simulator**, against a local log-mode server on a temporary storage root, with two simulators signed in to the same account:
  - Change the password on one: the other is signed out, and the log shows the notification.
  - Change the email: the code is in the log for the new address; confirm it; the other device is signed out, the old-address notification is in the log, and sign-in works with the new email.
  - A wrong current password shows the message.

  This box stays unticked until someone runs it.
- [ ] 4.3 **Manual, needs the consoles.** Link and unlink Google on a password account; set a password on a Google-only account, then unlink Google; the last-method refusal on an Apple-only account; Apple unlink removing the app from Apple ID settings. This box stays unticked until someone runs it.
- [ ] 4.4 Push `feat/add-account-security`. Verify with `git log origin/feat/add-account-security -1` that it matches the local HEAD.
