# Design

## Context

See `proposal.md` for motivation and `specs/` for the behavior contract.

Current state that shapes the approach:

- Generated images are written by the worker to `<STORAGE_ROOT>/outputs/<job_id>.png` and served by a `StaticFiles` mount at `/images`. Nothing removes them except `purge_user_jobs` on account deletion. The `OUTPUT_RETENTION_HOURS` setting is defined and documented ("enforcement deferred") but unused.
- Reference faces live in `<STORAGE_ROOT>/inputs/<job_id>/` and are removed in the worker's `finally` block. A restart drops the in-memory jobs but not the folders, so interrupted jobs leave faces behind. Nothing cleans them later.
- Jobs are in `InMemoryJobStore`, a plain `dict`. `list_queued` iterates the live `values()` view; `list_for_user` already iterates a snapshot. The worker runs on the event loop. Auth endpoints are plain `def` handlers, so `purge_user_jobs` already deletes from the store in a thread-pool thread.
- A job is created in the store **before** its uploads are written, so an input folder never exists without its job (until that job disappears).
- The previous worker bug (an unguarded exception in bookkeeping killing the loop) is the model for how not to write a background task here.

## Goals / Non-Goals

**Goals:**

- Bounded disk use for generated images, with a retention period operators can set.
- Reference faces never outlive the server run that received them.
- A sweeper that cannot take the worker or the server down.

**Non-Goals:**

- Telling users when a result will disappear (follow-up: `expires_at` plus app text).
- Persisting jobs, history, per-plan retention, or non-local storage.

## Decisions

### 1. A sweep service, with the scanning and the deciding kept apart

`services/retention_service.py` exposes:

- `async sweep(store, settings, now) -> SweepResult` — one pass over outputs and inputs.
- `async run_retention(store, settings, clock)` — the periodic loop.

`repos/file_storage.py` gains the filesystem pieces: `list_output_files(storage_root)` (regular `*.png` files directly in `outputs/`, symlinks skipped), `list_input_job_ids(storage_root)` (directory names under `inputs/`), and `delete_output(job_id, storage_root)`. The service decides; the repo touches the disk. This also makes the service testable with a fake store and a temp directory.

### 2. Age comes from the file's modification time

An image expires when `now - mtime >= OUTPUT_RETENTION_HOURS`. The worker writes the file when generation finishes, so mtime is the moment the result became available, which is what "kept for 24 hours" means to a user.

- **Why not the job record:** jobs vanish on restart, but their images stay. Using mtime is the only way to expire images that no job refers to, which is exactly the backlog (18 files on a dev machine today) the first sweep must clear.
- **Why not the job id:** a ULID encodes submission time, not completion, and non-ULID files would need special handling.
- **Caveat:** restoring a backup or copying the folder resets mtimes, so those images would live another full period. Accepted; retention is a cost control, not a legal deletion deadline.

### 3. Orphaned faces are defined by the job store, not by age

An input folder is an orphan when `store.get(<folder name>)` returns `None`. No timing heuristic is needed because of the ordering noted in Context: a job is created before its uploads, and is removed only after its folder is gone (the worker's `finally`, or `purge_user_jobs`). At startup the store is empty, so every leftover folder is an orphan and is removed; later sweeps remove only folders whose job has gone. Folders of queued or running jobs are always kept.

### 4. Keep every store access on the event loop

`InMemoryJobStore` is not thread-safe. `list_queued` iterates the live dict view, so a `delete` from another thread could raise "dictionary changed size during iteration" inside the worker and kill it. Therefore:

- The disk **scan** (listing and `stat`) runs in `asyncio.to_thread`; it reads only the filesystem.
- Everything that touches the store (`get`, `delete`) and the actual deletions run on the loop, in batches of 200 with `await asyncio.sleep(0)` between batches, so a large first-run backlog cannot stall requests.
- `list_queued` is changed to iterate `list(self._store.values())`, matching `list_for_user`. This also hardens the existing path where `purge_user_jobs` deletes from a pool thread.

### 5. What a sweep does to a job record

For each expired image: if a job with that id exists and is in a terminal state (`succeeded` or `failed`), delete the record; if it is queued or running, leave both alone (an image should not exist yet, and a live job must not be pulled out from under the worker). Then delete the file. Deleting the record makes `GET /generations/{id}` answer 404, as the spec says. A client that already loaded the image keeps working: the app caches the bytes it fetched, so Share and Download still work on an open screen; only a fresh open fails, with the existing "Could not load the image" state.

### 6. Scheduling and failure handling

- **Startup:** `lifespan` runs one `sweep` before the workers are created, after the usage refund. A failure is logged and does not stop startup; the periodic task retries.
- **Periodic:** `run_retention` sleeps `RETENTION_SWEEP_MINUTES` (default 10), then sweeps, forever. Each pass is wrapped in `try/except Exception` that logs and continues. Inside a pass, each file or folder is handled in its own `try/except`, so one undeletable file does not block the rest. The task is cancelled with the workers on shutdown.
- **Logging:** one `info` line per pass that removed something: counts of outputs and orphan input folders.

### 7. Safety limits on what gets deleted

Only regular `*.png` files directly inside `outputs/` and only directories directly inside `inputs/` are candidates; symlinks are never followed or removed; nothing outside those two folders is touched. `templates/`, previews, and `app.db` are out of reach by construction.

### 8. Configuration

`OUTPUT_RETENTION_HOURS` becomes `Field(default=24, ge=1)` and a new `RETENTION_SWEEP_MINUTES` is `Field(default=10, ge=1)`. Pydantic's validation error names the field, which satisfies the spec's fail-fast requirement; `app = create_app()` runs at import, so the server stops at startup.

### 9. Test seams

`sweep` takes `now` as a parameter and the loop takes a clock, so tests age files with `os.utime` instead of sleeping. A fake store and `tmp_path` cover the decisions; one integration test uses the real app to check the 404s end to end.

## Risks / Trade-offs

- [The first start after upgrade irreversibly deletes every output older than the retention period] → Called out in the proposal, README, and PR. Operators who want to keep old images raise `OUTPUT_RETENTION_HOURS` or copy `storage/outputs/` first.
- [Users lose results after 24 hours with no warning] → Acceptable while Download and Share exist; telling them when it expires needs `expires_at` and app text, listed as a follow-up.
- [mtime can be wrong after a restore or copy] → Images live longer, never shorter; accepted (Decision 2).
- [A sweep competes with requests for the event loop] → The scan is off-loop and deletion is batched with yields (Decision 4).
- [Startup sweep failure leaves faces on disk until the next pass] → Logged and retried every 10 minutes; a failing sweep is a visible error in the log, not a silent one.
- [`purge_user_jobs` still mutates the store from a pool thread] → Its snapshot iteration plus the `list_queued` fix removes the crash path; moving it onto the loop is a possible later cleanup.
- [Two server processes on one storage root would delete each other's orphan faces] → Same single-process assumption as the rest of the server; documented in the README.

## Migration Plan

No schema change. Deploying starts enforcing the setting immediately, with the deletion described above. Rollback is reverting the PR; deleted files cannot be recovered, so back up `outputs/` first where that matters.

## Open Questions

- None that change the specs or tasks. Whether a later change should expose `expires_at` and show it in the app is a product call for after this lands.
