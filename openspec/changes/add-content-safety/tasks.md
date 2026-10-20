# Tasks

Work on branch `feat/add-content-safety`. Do not push to `main`. Server tasks run in `server/` and app tasks in `app/`. "Decision N" refers to `design.md`. Tests use temporary storage and fake classifiers only: never download or load a real model in the test suite. Record the md5 of `server/storage/app.db` and the `server/storage/inputs` count before and after the server suite.

## 1. Server: matcher, classifier interface, settings

- [x] 1.1 Add `core/safety.py`: `TermMatcher` (normalising and whole-word matching, plus the joined form for single-letter runs, Decision 1), `load_terms(path)`, and the `ImageClassifier` protocol. Add the settings from Decision 8, with their startup checks. Add `seed/safety/blocked_terms.txt` with a short starter list. Verify:
  - `tests/core/test_safety.py` covers each scenario of "Screen custom prompts against a term list" at the unit level (`N-U-D-3`, `Nüde`, `grassy`, `classic`), multi-word phrases, comment lines, and an empty list refusing to load;
  - `tests/configs/test_settings.py` covers the defaults, the bounds, an unknown `SAFETY_STUB_FLAG` value being refused, and a `SAFETY_STUB_FLAG` other than `none` with a non-stub backend being refused.
- [x] 1.2 Add `services/safety/stub_classifier.py` and `services/safety/local_classifier.py` (lazy `transformers` import, `nsfw` label score, a `threading.Lock` around inference). Wire them in `main.py` with startup enforcement (Decision 2). Verify:
  - `tests/services/safety/test_classifiers.py` covers the stub returning 0.0, and 1.0 when set to flag;
  - `tests/test_main.py` covers `SAFETY_STUB_FLAG` `none`, `outputs` and `all` building the right pair of stubs;
  - the local classifier works with a fake injected `transformers` pipeline (no real model), picking the `nsfw` score and serialising concurrent calls;
  - `tests/test_main.py` covers a non-stub backend whose classifier fails to load refusing to start, and the stub backend starting without loading a model.

## 2. Server: storage

- [ ] 2.1 Add `repos/user_store_safety.py` with the tables and methods from Decision 5, and schema version 6. Verify:
  - `tests/repos/test_user_store_safety.py` covers `suspended_until` with 2 strikes (None), with 3 (the third-most-recent plus the window), and after the oldest ages out;
  - the report cap at 20 within 24 hours;
  - two threads adding the 20th report creating exactly one;
  - `list_open_reports` newest first, `resolve_report`, `expired_reports`, and deletion cascading with the user;
  - `tests/repos/test_user_store_migration.py` covers v5 to v6 and a re-run;
  - every file under `server/src` stays under 1000 lines.

## 3. Server: submit checks

- [ ] 3.1 Add the pause check, prompt screening and upload screening in `generation_service.submit`, in the order of Decision 3. Verify that `tests/api/test_generations_safety.py`, with fake classifiers, covers:
  - `generation_suspended` with `suspended_until`, raised before uploads are read;
  - `prompt_blocked` with no echo, no job and unchanged remaining generations;
  - templates not screened;
  - `photo_blocked` with no stored file, no job and unchanged remaining generations;
  - a classifier error at upload giving 503 `safety_unavailable` with nothing counted;
  - safe input still giving 202;
  - the log capture for a blocked prompt containing the account id and not the prompt.

## 4. Server: output screening and strikes

- [ ] 4.1 Write pipeline output to `staging/`, check it, and move safe images into `outputs/`. Handle the flagged and error paths, the refunds, and strikes through `_call_safely`. Clean `staging/` in `finally` and at startup (Decision 4). Verify that `tests/services/test_worker.py` covers:
  - safe output: `succeeded`, the image in `outputs/` and nothing in `staging/`;
  - flagged output: `failed/content_blocked`, no file in either folder, a refund and one strike;
  - a classifier error: `failed/safety_check_failed`, a refund and no strike;
  - a raising `record_strike` not stopping the worker;
  - a flagged image never fetchable via `/images/{id}.png` (also checked by an API test that polls during the check using a slow fake classifier);
  - startup clearing leftover staging files.

## 5. Server: reports

- [ ] 5.1 Add `POST /reports` (Decisions 6 and 7), copying the report image from the server or the device, and storing it under `reports/`. Verify that `tests/api/test_reports.py` covers every scenario of "Accept reports of results" and "Limit reports per account", including an invalid category, a note over 500 characters, an invalid uploaded image, another account's job, and source `none`.
- [ ] 5.2 Add report expiry to the retention sweep, image cleanup on account deletion, and orphan-image cleanup (Decision 6). Verify:
  - `tests/services/test_retention_service.py` covers a 31-day-old report and its image being removed, a 29-day-old one being kept, a reported image surviving the 24-hour output sweep, and a per-report error not stopping the sweep;
  - `tests/api/test_delete_account.py` covers a deleted reporter's reports and images being gone.
- [ ] 5.3 Add `scripts/reports.py` (`list`, `show --out`, `resolve --outcome`). Verify that `tests/scripts/test_reports_cli.py` covers each command against a temporary database and an unknown id.
- [ ] 5.4 Update `server/README.md` (the safety settings, the term list, the model download and pre-fetch, staging, the reports API and CLI, the new error codes, schema version 6). Add `todo.md` items: tune the threshold and term list against real outputs before launch, and add reported-image retention to the privacy review. Verify the curl examples against a local stub server on a temporary storage root with `SAFETY_STUB_FLAG` set to `outputs` and to `all`, using your own free port and stopping only your own process.

## 6. App

- [ ] 6.1 Add the error codes and `suspended_until` parsing, the `content_blocked` failure text, and the submit-flow messages and paused dialog (Decision 9). Verify that tests cover each message, the dialog's local time, the form values being kept, and the `content_blocked` view showing no image.
- [ ] 6.2 Add `features/report/report_sheet.dart`, `submitReport` on the API client, and the Report action on the status success view and the creation detail screen. Verify that tests cover:
  - Send disabled without a category;
  - the request carrying the job id, category, note and image bytes from each screen;
  - the success SnackBar;
  - `too_many_reports`;
  - a network error keeping the values;
  - Cancel sending nothing.

## 7. Integration and hand-off

- [ ] 7.1 Run `uv run pytest -q` in `server/`, and `flutter analyze && flutter test` in `app/`. Verify that everything passes with zero analyzer warnings, that the `app.db` md5 and `inputs` count are unchanged, and that `openspec validate add-content-safety --strict` passes.
- [ ] 7.2 **Manual. iOS simulator** against a local stub server on a temporary storage root:
  - a blocked word in a custom prompt shows the prompt message;
  - with `SAFETY_STUB_FLAG=all`, a photo shows "can't be used";
  - with `SAFETY_STUB_FLAG=outputs`, a result shows the content-rules message;
  - three blocked results show the paused dialog with an end time;
  - Report from the status screen and from My creations shows "Thanks, we'll review it."
  - `scripts/reports.py list` shows both reports.

  This box stays unticked until someone runs it.
- [ ] 7.3 **Manual, needs the `ml` group and network.** Start with `MODEL_BACKEND=sana` and the real classifier, generate a few template images, and check that none of the safe templates are blocked at the default threshold. Note any false positives in the PR. This box stays unticked until someone runs it.
- [ ] 7.4 Push `feat/add-content-safety`. Verify with `git log origin/feat/add-content-safety -1` that it matches the local HEAD.
