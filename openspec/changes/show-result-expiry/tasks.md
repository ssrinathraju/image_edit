# Tasks

Work on branch `feat/show-result-expiry`. Do not push to `main`. Server tasks run in `server/` and app tasks in `app/`. "Decision N" refers to `design.md`. Tests use temporary storage only. Record the md5 of `server/storage/app.db` and the `server/storage/inputs` count before and after the server suite.

## 1. Server

- [x] 1.1 Add `Job.expires_at` and `JobStatusResponse.expires_at`, set it in the worker from the promoted file's mtime plus `OUTPUT_RETENTION_HOURS` (falling back to `finished_at + retention` and logging), and pass it through `get_status` (Decision 1). Verify:
  - `tests/services/test_worker.py` covers a succeeded job's `expires_at` equalling the output mtime plus retention (set the mtime with `os.utime`, use a 48-hour setting), the fallback when the stat raises, and failed or blocked jobs having none;
  - `tests/api/test_generations_status.py` covers the field in the response (ISO 8601 UTC) for succeeded jobs, and null for queued, running and failed ones;
  - a test shows the retention sweep does not delete the image before `expires_at`.
- [x] 1.2 Update `server/README.md` (the status response example gains `expires_at`) and remove the "Tell users when a result expires" item from `todo.md`. Verify the status curl example against a local stub server on a temporary storage root (`uvicorn --factory image_edit_server.main:create_app`, a free port, stopping only your own process).

## 2. App

- [x] 2.1 Parse `expires_at` into `GenerationJob.expiresAt` (null when missing or invalid), add the save-state tracking and the note to the status screen (Decisions 2 and 3). Verify:
  - `test/schemas/job_test.dart` covers a present, missing and invalid value;
  - `test/features/generation_status/generation_status_screen_test.dart` covers the saved note, the save-failed note, no note while the save is pending, and no note without `expires_at`;
  - a test that sets a +05:30 time zone (or injects one into the formatter) shows 23 October, 3:30 PM for `2026-10-23T10:00:00Z`.

## 3. Integration and hand-off

- [x] 3.1 Run `uv run pytest -q` in `server/`, and `flutter analyze && flutter test` in `app/`. Verify that everything passes with zero analyzer warnings, that the `app.db` md5 and `inputs` count are unchanged, and that `openspec validate show-result-expiry --strict` passes.
- [ ] 3.2 **Manual. iOS simulator** against a local stub server on a temporary storage root: generate an image. The status screen shows "Saved to My creations on this device. Our copy is deleted on …" with tomorrow's date at the right local time. This box stays unticked until someone runs it.
- [ ] 3.3 Push `feat/show-result-expiry`. Verify with `git log origin/feat/show-result-expiry -1` that it matches the local HEAD.
