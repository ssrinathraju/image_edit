# Tasks

Work on branch `feat/enforce-output-retention`. Do not push to `main`; open a PR at the end (group 7). All commands run in `server/`.

## 1. Settings and job store hardening

- [ ] 1.1 In `configs/settings.py` make `OUTPUT_RETENTION_HOURS` a `Field(default=24, ge=1)` and add `RETENTION_SWEEP_MINUTES: int = Field(default=10, ge=1)`; verify `tests/configs/test_settings.py` asserts both defaults, an env override, and that `Settings(OUTPUT_RETENTION_HOURS=0)` and `Settings(RETENTION_SWEEP_MINUTES=0)` raise a validation error whose text names the setting
- [ ] 1.2 In `repos/in_memory_job_store.py` make `list_queued` iterate `list(self._store.values())`; verify `tests/repos/test_in_memory_job_store.py` gains a stress test in which one thread creates and deletes jobs in a loop while another calls `list_queued()` thousands of times without raising

## 2. File storage helpers

- [ ] 2.1 Add `list_output_files(storage_root)`, `list_input_job_ids(storage_root)`, and `delete_output(job_id, storage_root)` to `repos/file_storage.py` per design Decisions 1 and 7 (regular `*.png` files only, symlinks skipped, directories only for inputs, a missing folder returning an empty list); verify `tests/repos/test_file_storage.py` covers listing with a mix of png, non-png, nested, and symlinked entries, a missing `outputs/` or `inputs/` folder, and `delete_output` on an existing and a missing file

## 3. Retention service

- [ ] 3.1 Add `services/retention_service.py` with `sweep(store, settings, now) -> SweepResult` per design Decisions 2 to 5: scan off-loop with `asyncio.to_thread`, then on the loop delete expired outputs (and the job record only when the job is terminal) and delete input folders whose job is not in the store, in batches of 200 with `await asyncio.sleep(0)`; each file or folder in its own `try/except` that logs and continues. Verify `tests/services/test_retention_service.py` covers: an image older than the retention deleted, one younger kept, an image exactly at the limit deleted, the matching terminal job record removed, a queued or running job's record and a non-expired image untouched, an expired image with no job deleted, a non-png file and a symlink left alone, an input folder with no job deleted, an input folder of a queued job kept, a failing delete of one file not stopping the rest, and the returned counts

## 4. Scheduling and wiring

- [ ] 4.1 Add `run_retention(store, settings, clock)` to `services/retention_service.py` (sleep `RETENTION_SWEEP_MINUTES`, sweep, repeat; each pass wrapped so an exception is logged and the loop continues); verify the tests cover a pass that raises followed by a pass that still runs, the sleep interval being read from settings, and clean cancellation
- [ ] 4.2 In `main.py` `lifespan` run one `sweep` after the usage refund and before the workers are created (a failure is logged, not fatal), start `run_retention` as a task next to the workers, and cancel it on shutdown; verify `tests/test_main.py` covers: files aged beyond retention are gone and orphan faces removed before the first request is served, a failing startup sweep still lets the app start, and the retention task being cancelled on shutdown

## 5. End to end

- [ ] 5.1 Add `tests/integration/test_retention_flow.py` using the real app and stub pipeline: submit a generation and wait for success, fetch the image (200), age the output file past the retention period, run a sweep, then assert the image URL and `GET /generations/{id}` both answer 404; a second image younger than the period is still served. Also restart the app on the same storage directory with a leftover `inputs/<id>/` folder and assert it is removed

## 6. Documentation

- [ ] 6.1 Update `server/README.md`: remove "enforcement deferred" and document `IMAGE_EDIT_OUTPUT_RETENTION_HOURS` and `IMAGE_EDIT_RETENTION_SWEEP_MINUTES`, a short "Retention" section (what is swept, mtime-based age, the startup sweep, orphan reference faces, the single-process assumption, and the warning that the first start after upgrading deletes images already past the period, with how to avoid it); add a line to `todo.md` for the follow-up (show `expires_at` in the status response and a note in the app); verify the documented environment variables work by starting the app with `IMAGE_EDIT_OUTPUT_RETENTION_HOURS=0` and seeing it refuse to start

## 7. Verification and PR

- [ ] 7.1 Run `uv run pytest -q` in `server/` and `flutter analyze && flutter test` in `app/` (no app files should change); verify all pass, then run `openspec validate enforce-output-retention --strict`
- [ ] 7.2 Manual run against a copy of a real `storage/` folder that has old outputs: start the server and confirm the old images are removed at startup, a freshly generated image is served, `curl` on an expired URL gives 404, and the log line reports the counts. Leave this box unchecked if it could not be run and say so in the PR
- [ ] 7.3 Push the branch and open a PR to `main` with a summary, the test plan, and which steps of 7.2 were exercised, including the first-start deletion warning
