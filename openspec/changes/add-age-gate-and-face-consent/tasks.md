# Tasks

Work on branch `feat/add-age-gate-and-face-consent`. Do not push to `main`. Server tasks run in `server/` and app tasks in `app/`. "Decision N" refers to `design.md`. Tests use temporary storage only. Record the md5 of `server/storage/app.db` before and after the server suite.

## 1. Server: age rule, settings, schema

- [x] 1.1 Add `core/age.py` with `check_date_of_birth(text, today)`, `InvalidDateOfBirth` and `UnderAge` (Decision 1), and add `CONSENT_VERSION` to settings with a startup check that it is non-empty (Decision 7). Verify:
  - `tests/core/test_age.py` covers exactly 18 today, one day short, the leap-day birth on 28 February and 1 March 2026, `2008-13-01`, `08/05/2001`, `2008-1-1`, a datetime string, tomorrow, and today;
  - `tests/configs/test_settings.py` covers the default `"1"`, an override, and an empty value refusing to start.
- [x] 1.2 Schema version 5: add `age_confirmed_at`, `consent_version` and `consent_at`, and extend `User` (Decision 2). Verify that `tests/repos/test_user_store_migration.py` covers a v4 database with accounts (all three columns NULL afterwards, everything else kept) and running the migration twice changing nothing.

## 2. Server: registration and provider sign-up

- [x] 2.1 Add `RegisterRequest` with `date_of_birth`. Check it first in the registration service and set `age_confirmed_at` in `complete_registration` (Decision 3). Verify that `tests/api/test_auth.py` covers every new scenario of "Start a registration":
  - under 18 sends no code and leaves no pending row;
  - a missing date;
  - exactly 18 confirmed shows `age_confirmed` true;
  - a malformed date gives 400 `invalid_date_of_birth`;
  - login still works without a date.
- [x] 2.2 Add an optional `date_of_birth` to both provider requests and the `adult_confirmed` parameter to `sign_in_with_identity` (Decision 4). Verify that `tests/api/test_social_sign_in.py` and `tests/repos/test_user_store_identities.py` cover:
  - `age_required` with no account created;
  - a retry with an adult date creating the account with `age_confirmed` true;
  - Apple under 18 not exchanging the code (the fake `post` is not called);
  - a linked identity without a date succeeding;
  - linking by email without a date succeeding;
  - a malformed date giving `invalid_date_of_birth`.

## 3. Server: `/me` age and consent, generation gate

- [x] 3.1 Add `POST /me/age`, `POST /me/consent`, `DELETE /me/consent` and the new `MeResponse` fields (Decision 5). Verify that `tests/api/test_age_and_consent.py` covers every scenario in `specs/age-and-consent/spec.md`, including "Never store the date of birth": no column holds it, and a log capture during register, provider sign-up and `/me/age` contains no submitted date.
- [x] 3.2 Add the gate at the top of `generation_service.submit` (Decision 6), and update the conftest fixtures so the default `client` account is age-confirmed with current consent. Add an `unconsented_client` fixture. Verify:
  - `tests/api/test_generations_gate.py` covers every scenario of "Require a confirmed age and current consent to generate", including no stored upload and unchanged remaining generations;
  - the full suite passes.
- [x] 3.3 Update `server/README.md`: the date of birth on register and the provider endpoints, the new endpoints and fields, the error codes, `CONSENT_VERSION`, and the v5 migration note. Verify the curl examples against a local server on a temporary storage root (`uvicorn --factory image_edit_server.main:create_app`, a free port, stopping only your own process).

## 4. App: client, schemas, errors

- [x] 4.1 Add `dateOfBirth` to `startRegistration`, the optional date to the provider sign-in calls, and `confirmAge`, `acceptConsent` and `withdrawConsent` to the API client. Add `ageConfirmed` and `ConsentState` to the account schema. Add the seven error codes. Verify with `test/core/api_client_test.dart`, `test/core/api_errors_test.dart` and `test/schemas/account_test.dart`.

## 5. App: age screens and routing

- [x] 5.1 Add the date-of-birth field to `register_screen.dart` (Decision 8). Verify that `test/features/auth/register_screen_test.dart` covers submit disabled without a date, the date sent as `YYYY-MM-DD`, and the `under_age` message keeping the values.
- [x] 5.2 Add the provider date-of-birth screen (`/age`) and the `age_required` handling in `provider_buttons.dart`, resending the same credential. Verify that `test/features/consent/provider_age_screen_test.dart` covers:
  - Google `age_required` leading to the screen, then a resend with the date, then signed in;
  - Apple resending the same identity token, nonce and code;
  - `under_age` returning to sign-in with no session;
  - cancel returning with no session.
- [x] 5.3 Add `/confirm-age` and `/age-blocked` and the redirect for accounts whose age isn't confirmed. Verify:
  - `test/router_test.dart` covers an unconfirmed account landing on `/confirm-age` and being kept there from every signed-in route, and a confirmed one landing on `/`;
  - the screen tests cover an adult date going home, under 18 going to `/age-blocked`, and Delete account and Sign out there.

## 6. App: consent

- [x] 6.1 Add the consent screen and text (`features/consent/`). Gate `submit_flow.dart` (check the version, accept then continue, decline keeps the form, a server `consent_required` opens the screen and retries once, `age_not_confirmed` goes to `/confirm-age`). Add the profile's consent row with Withdraw. Verify that the tests cover every scenario of "Ask for face-photo consent before the first upload" and "Show and withdraw face-photo consent on the profile", including that nothing is uploaded before Accept (the fake API sees no submit call).
- [x] 6.2 Add a `todo.md` item: "Have the face-photo consent text (`features/consent/consent_text.dart`) and the privacy policy reviewed for GDPR and BIPA before launch; bump `CONSENT_VERSION` when the text changes." Verify that the item is present.

## 7. Integration and hand-off

- [x] 7.1 Run `uv run pytest -q` in `server/`, and `flutter analyze && flutter test` in `app/`. Verify that everything passes with zero analyzer warnings, that the `server/storage/inputs` count and the `app.db` md5 are unchanged, and that `openspec validate add-age-gate-and-face-consent --strict` passes.
- [ ] 7.2 **Manual. iOS simulator**, against a local log-mode server on a temporary storage root:
  - Register with an under-18 date and see the message.
  - Register with an adult date, confirm the code, generate. The consent screen appears: Decline keeps the form, and Accept continues to the status screen.
  - On the profile, the row shows "Given on …". Withdraw, and the next generation asks again.
  - Start the server on a copy of a pre-upgrade `app.db` holding an existing account. Signing in shows Confirm your age; an adult date leads home, and an under-18 date shows the blocked screen.

  This box stays unticked until someone runs every step.
- [ ] 7.3 **Manual, needs the consoles.** A new Google or Apple sign-up asks for a date of birth before the account exists, and an existing linked account isn't asked. This box stays unticked until someone runs it.
- [ ] 7.4 Push `feat/add-age-gate-and-face-consent`. Verify with `git log origin/feat/add-age-gate-and-face-consent -1` that it matches the local HEAD.
