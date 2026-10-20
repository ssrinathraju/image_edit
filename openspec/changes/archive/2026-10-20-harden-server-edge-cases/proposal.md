# Proposal

## Why

Earlier reviews recorded five rough edges in `todo.md`. Each one is either visible to users or a reliability gap:
- the status screen shows the raw code `pipeline_failed`;
- an account with no generations left still makes the server read and decode up to 40 MB of uploads before it answers 429;
- a corrupted plan value turns every request for that account into a 500;
- failed jobs' records are never removed, because the retention sweep only looks for images;
- a non-string `date_of_birth` gets a 422 where the spec promises 400.

Separately, `repos/user_store.py` is at 976 of its 1000-line limit, and the next server change would push it over.

## What Changes

- **App:** a failed generation shows plain-language text chosen from the error code: "We couldn't create your image this time. This one wasn't counted, so try again." Unknown or missing codes get a general message. The raw code is never shown.
- **Server, quota:** a read-only "any generations left?" check runs before uploads are read, and an exhausted account gets 429 `quota_exceeded` straight away. The atomic reservation still happens after validation, as today.
- **Server, plan:** an unknown stored plan is treated and reported as `free`, with a warning logged.
- **Server, job records:** jobs record a finish time when they succeed or fail. The retention sweep removes every finished job record older than the retention period, image or not, and never touches live jobs.
- **Server, date of birth:** any non-string or over-long `date_of_birth` gets 400 `invalid_date_of_birth`, without echoing the value.
- **Server, refactor:** `repos/user_store.py` is split into focused modules (identities, email codes and registrations, age and consent) with **no behaviour change**.

Out of scope:
- server-side human-readable messages;
- localisation;
- more failure codes from the pipeline;
- a persistent job store;
- rejecting oversized request bodies before they are received (the multipart body is still received by the framework; this change stops the handler reading and decoding it).

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `generation-flow-ui`: "Display a human-readable error on failure" now requires plain-language text chosen from the error code.
- `usage-quota`: new requirements to refuse an exhausted account before reading uploads, and to treat an unknown plan as free.
- `photo-generation`: new requirement to expire finished job records.
- `age-and-consent`: "Check a date of birth" covers non-string and over-long values.

## Impact

- **Server:**
  - `services/generation_service.py` and `services/quota_service.py` (the pre-check);
  - `core/plans.py` (the fallback);
  - `schemas/job.py` (`finished_at`), `services/worker.py` and `services/retention_service.py`;
  - `schemas/user.py` and `services/auth_service.py` (date-of-birth typing);
  - `repos/user_store.py` split into `repos/user_store.py` plus new modules under `repos/`.
- **App:** `features/generation_status/generation_status_screen.dart`, and a new `features/generation_status/failure_messages.dart`.
- **API:** no new fields or endpoints. Response codes change only where the spec already promised them (DOB 400) or where a 500 becomes a 200 (unknown plan).
- **Data:** none. The job store is in memory.
