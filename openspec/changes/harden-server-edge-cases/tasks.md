# Tasks

Work on branch `feat/harden-server-edge-cases`. Do not push to `main`. Server tasks run in `server/` and app tasks in `app/`. "Decision N" refers to `design.md`. Tests use temporary storage only. Record the md5 of `server/storage/app.db` and the `server/storage/inputs` count before and after the server suite.

## 1. Server: split `repos/user_store.py` (no behaviour change)

- [x] 1.1 Move the `SqliteUserStore` methods into the mixin modules from Decision 6, keeping every name, signature and SQL statement unchanged. Verify:
  - every file under `server/src` is under 1000 lines (`wc -l`);
  - `uv run pytest -q` passes with **no test file edited** in this commit;
  - a new `tests/repos/test_user_store_surface.py` asserts that every public method listed in the `UserStore` protocol exists on `SqliteUserStore`.

## 2. Server: fixes

- [x] 2.1 Unknown plan (Decision 3): `effective_plan`, a `daily_limit` that never raises, `/me` reporting `free`, and the warning with the user id only. Verify that `tests/core/test_plans.py` and `tests/api/test_me.py` cover a stored `gold` plan: `/me` gives 200 with plan `free` and the free limit, a submit uses the free limit, and a log capture has the user id and no `gold`.
- [x] 2.2 Quota pre-check (Decision 2): `QuotaService.has_remaining` is called before face validation. Verify that `tests/api/test_generations_quota.py` covers:
  - an exhausted account getting 429 without `_read_and_validate_faces` being called (patch it to fail the test if called);
  - an account with 1 left sending an invalid image getting 400 and still having 1;
  - the existing concurrent test still passing.
- [x] 2.3 Finished job records (Decision 4): `Job.finished_at` set by the worker, `list_all` on the store, and the sweep's second pass. Verify that `tests/services/test_retention_service.py` and `tests/services/test_worker.py` cover:
  - a failed job older than the retention period being removed (status gives 404);
  - a recent failed job being kept;
  - a queued or running job older than the period being kept;
  - an old succeeded job's record and image both being removed;
  - a per-record error being logged with the sweep continuing;
  - the worker setting `finished_at` on both terminal paths.
- [x] 2.4 Date-of-birth typing (Decision 5). Verify that `tests/api/test_age_and_consent.py` covers `19900101`, `true`, `{}`, `[]` and a 200-character string on register, Google sign-in and `/me/age`: each gives 400 `invalid_date_of_birth`, with a body that doesn't contain the sent value. Provider sign-in with `"date_of_birth": null` still gives `age_required` for a new account.
- [x] 2.5 Update `todo.md`: remove the five items this change fixes (friendly failure text, uploads read before the quota check, unknown plan 500, failed jobs never swept, non-string date of birth) and the `user_store.py` split item. Add a deployment note: cap the request body size at the proxy. Verify by reading `todo.md`.

## 3. App: failure text

- [x] 3.1 Add `failure_messages.dart` and use it in `_FailureView` (Decision 1). Verify that `test/features/generation_status/generation_status_screen_test.dart` covers `pipeline_failed` showing the plain message and not the code, and an unknown code and a null code showing the general message.

## 4. Integration and hand-off

- [x] 4.1 Run `uv run pytest -q` in `server/`, and `flutter analyze && flutter test` in `app/`. Verify that everything passes with zero analyzer warnings, that the `server/storage/inputs` count and `app.db` md5 are unchanged, and that `openspec validate harden-server-edge-cases --strict` passes.
- [ ] 4.2 **Manual. iOS simulator** against a local log-mode server on a temporary storage root: use up the daily allowance, then submit again with a photo. The limit dialog appears at once, and generation works normally before the limit. The failure text is covered by widget tests only, because the stub pipeline can't be made to fail. This box stays unticked until someone runs it.
- [x] 4.3 Push `feat/harden-server-edge-cases`. Verify with `git log origin/feat/harden-server-edge-cases -1` that it matches the local HEAD.
