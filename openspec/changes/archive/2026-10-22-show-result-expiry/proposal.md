# Proposal

## Why

The server deletes every generated image after the retention period (24 hours by default), and today nothing tells the user. The app does save each result to My creations on the device, but users can't know that, and when that save fails they lose the image without warning. This was recorded as a follow-up in `todo.md` by `enforce-output-retention`.

## What Changes

- **Server:** `GET /generations/{job_id}` gains `expires_at` (UTC, ISO 8601) for succeeded jobs. It is the moment the image was written plus `OUTPUT_RETENTION_HOURS`, which is the same clock the retention sweep uses. For any other status it is null.
- **App:** the status screen shows a note under a succeeded result, with the time in the device's local date and time:
  - once the image is saved to My creations: "Saved to My creations on this device. Our copy is deleted on <date, time>."
  - if that save failed: "Not saved on this device. Download or share it before <date, time>, when it's deleted."
  - while the save is in progress, or with no `expires_at`, there is no note.
- `todo.md`: the "Tell users when a result expires" item is removed.

Out of scope:
- showing expiry in My creations, since the device copy never expires;
- a relative "in N hours" display;
- notifications before expiry;
- changing the retention period.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `photo-generation`: a new requirement, "Report when a result expires".
- `generation-flow-ui`: a new requirement, "Say how long the server keeps the result".

## Impact

- **Server:** `schemas/api.py` (`JobStatusResponse.expires_at`), `schemas/job.py` (`Job.expires_at`), `services/worker.py` (sets it on success), `services/generation_service.py` (`get_status` returns it), and `server/README.md`.
- **App:** `schemas/job.dart` (`expiresAt`) and `features/generation_status/generation_status_screen.dart`, which gains the note and tracks the save state.
- **API:** one new nullable field on the status response. Older apps ignore it.
- **Data:** none persisted. `expires_at` lives on the in-memory job record.
