# Design

## Context

See `proposal.md` for the motivation and `specs/` for the behaviour. The current code:

- **The retention sweep** (`services/retention_service.py`) deletes `outputs/<id>.png` once `now - mtime >= OUTPUT_RETENTION_HOURS`, and the finished-job pass removes records whose `finished_at` is older than the period.
- **The worker** writes the image to `staging/`, checks it, then `promote_staged_output` moves it into `outputs/` with `os.replace`, which keeps the file's mtime, and sets `succeeded`, `result_url` and `finished_at`.
- **`get_status`** builds `JobStatusResponse(job_id, status, result_url, error)` from the in-memory `Job`, and has no access to settings.
- **The app's status screen** saves the result to My creations once, from `didChangeDependencies`, and shows a SnackBar "Couldn't save to My creations" on failure. The save outcome isn't kept in state.

## Goals / Non-Goals

**Goals:**
- `expires_at` matches when the sweep can really delete the image.
- The note reflects whether the device copy exists.

**Non-Goals:**
- Exact-second accuracy across clock skew between the server and the device.
- Live countdowns.

## Decisions

### 1. `expires_at` is computed once, in the worker, from the promoted file's mtime
Right after promoting, the worker reads `os.stat(outputs/<id>.png).st_mtime`, adds `OUTPUT_RETENTION_HOURS`, and stores the result as `Job.expires_at` (an aware UTC `datetime`) alongside `succeeded`. `get_status` passes it through, and `JobStatusResponse.expires_at: Optional[datetime]` is serialised as ISO 8601 with `Z` or `+00:00`.

If the stat fails (practically impossible right after a successful `os.replace`), the worker falls back to `finished_at + retention` and logs the fallback. Either way the job still succeeds.

- **Alternative rejected: `finished_at + retention`.** The sweep measures from mtime, and mtime is set when the pipeline wrote the staged file, which is slightly before `finished_at`. Using mtime keeps the promise exact: the image is never deleted before `expires_at`.
- **Alternative rejected: computing it in `get_status`** by stat-ing the file per request. That adds file I/O to a 2-second polling endpoint and needs settings plumbing.

### 2. The app tracks the save outcome and renders the note from it
The status screen's state gains `_SaveState { pending, saved, failed }`, set by the existing save call: `saved` on success, and `failed` on an error (with the SnackBar) or when there is no session (no SnackBar, because the save is skipped). `_SuccessView` shows the note under the image when `job.expiresAt != null` and the state isn't `pending`.

The time is formatted with `MaterialLocalizations.formatMediumDate` plus `formatTimeOfDay` on the local time from an injectable `expiryToLocalProvider`, which defaults to `utc.toLocal()` and which tests replace to fix a time zone. `intl` isn't a dependency, and My creations already formats dates this way.

The existing "Couldn't save" SnackBar stays. The note repeats the advice in a lasting place.

- **Alternative rejected: always showing the deletion warning.** The user chose to reassure when the device copy exists.

### 3. Wording
The text is from the spec, in a small `bodySmall` style under the image, with a check icon for saved and a warning icon for not saved. It is plain English, ready for localisation later.

Screen states:

| Status screen, succeeded | Note |
|---|---|
| Saving to My creations (pending) | None |
| Saved, `expires_at` present | "Saved to My creations on this device. Our copy is deleted on <date, time>." with a check icon |
| Save failed, `expires_at` present | "Not saved on this device. Download or share it before <date, time>, when it's deleted." with a warning icon |
| `expires_at` missing (an older server) | None. Everything else unchanged |

## Risks / Trade-offs

- **[What data is stored, and for how long]** `Job.expires_at`, in memory, for the life of the job record (at most the retention period, then the sweep removes it). Nothing new is persisted, on the server or the device.
- **[Who can read it]** Only the job's owner, through the existing owner-scoped status endpoint.
- **[What is logged]** Only the fallback case: `expires_at_fallback job=<id>`.
- **[Existing data and migration]** None. Jobs created before a deploy are gone after a restart anyway, because the job store is in memory. An older app ignores the field, and a newer app against an older server shows no note.
- **[Failure and retry]** A stat failure falls back to `finished_at + retention`, which is at most seconds later. The app treats a missing or unparsable `expires_at` as absent and shows no note.
- **[Background tasks when a call raises]** The stat is inside the worker's existing `try`. The fallback means it can't fail the job.
- **[Thread-safety of shared state]** `expires_at` is set in the same `store.update` call as `succeeded`, so a poll never sees `succeeded` without it.
- **[Clock skew]** The note uses the server's UTC time converted on the device. A wrong device clock or time zone shifts only how the time is displayed, not when the deletion happens. → Accepted.

## Migration Plan

Deploy the server and app in either order: the field is additive and optional. Rollback is redeploying the previous version.
