# Proposal

## Why

Generated images are written to `storage/outputs/` and never removed except when an account is deleted. `OUTPUT_RETENTION_HOURS` (24) exists as a setting, but nothing reads it, so the folder grows without bound and every user's generated images live forever. Reference faces have a related gap: they are deleted only when a job finishes, so a restart mid-job leaves the uploaded photos on disk permanently, which breaks the spec's promise that faces are not retained beyond job completion. This change makes retention real and closes that gap.

## What Changes

- **Expire generated images**: an image older than the retention period (default 24 hours, measured from when the file was written) is deleted and no longer served. Its job record is removed, so the status endpoint answers 404 for it.
- **Sweep schedule**: a sweep runs once at startup, before any request is served, and then every 10 minutes (configurable).
- **Clean up after interrupted runs**: reference face folders whose job no longer exists (lost in a restart) are deleted at startup and on every sweep. Faces of queued or running jobs are never touched.
- **Invalid configuration fails fast**: a retention period below 1 hour or a sweep interval below 1 minute stops the server from starting.
- **Thread safety fix**: `InMemoryJobStore.list_queued` iterates a snapshot, so deletions made from another thread cannot crash the worker.
- **BREAKING (operational)**: the first start after this change deletes every generated image already older than the retention period, including images from earlier runs that no job refers to. That deletion cannot be undone.

Out of scope: telling users how long a result is kept (an `expires_at` in the status response and a note in the app), generation history, per-plan retention, moving images to object storage, disk-space monitoring, and cleaning the usage ledger or accounts.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `photo-generation`: A generated image is served only until it expires; expired images and their job records are removed; leftover reference faces from interrupted runs are removed; invalid retention settings are rejected.

## Impact

- **Server**: new `services/retention_service.py`; new helpers in `repos/file_storage.py`; `main.py` lifespan runs the startup sweep and the periodic task; `configs/settings.py` gains `RETENTION_SWEEP_MINUTES` and validation on `OUTPUT_RETENTION_HOURS`; `repos/in_memory_job_store.py` snapshots in `list_queued`; README config table and notes updated. No new dependencies.
- **App**: none. A result opened after expiry already shows the existing "Could not load the image" state.
- **APIs**: no new fields. `GET /generations/{id}` and the result URL answer 404 once a result has expired.
- **Data**: files under `outputs/` and `inputs/` only. Templates, previews, `app.db`, and jobs that are still current are not touched.
