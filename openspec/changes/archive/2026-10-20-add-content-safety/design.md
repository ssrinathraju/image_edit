# Design

## Context

See `proposal.md` for the motivation and `specs/` for the behaviour. The current state:

- **Submit.** `generation_service.submit` runs in this order: the age and consent gate, the quota pre-check, face count, reading and validating uploads (`_read_and_validate_faces` returns bytes), resolving the prompt (`_resolve_prompt` returns the template prompt or the custom one), reserving, then creating the job and saving uploads.
- **Worker.** The worker calls `pipeline.run(faces, prompt, out_path)`, then marks the job `succeeded` and settles. Any exception gives `failed / pipeline_failed` and a refund. Inputs are deleted in `finally`.
- **Pipelines.** `main._make_pipeline` picks `stub` or `sana`. The `ml` dependency group holds `torch` and `transformers`; the default install doesn't.
- **Store and retention.** The store is `SqliteUserStore` composed from mixins (schema version 5), and the retention sweep lives in `services/retention_service.py`, with the report pass in `services/report_retention.py`. Account deletion goes through `AuthService.delete_account`, then the store's `delete_user` (with cascades) and the job purge.
- **App.** `failure_messages.dart` maps job error codes, `submit_flow.dart` handles submit errors, and `ImageActionRow` is shared by the status and creation detail screens.

## Goals / Non-Goals

**Goals:**
- No unsafe image is ever served: screening happens before `succeeded`, and it fails closed.
- Every server code path can be tested without ML libraries, using fake classifiers.
- No face-derived image leaves the server for moderation.

**Non-Goals:**
- Perfect accuracy. The threshold and term list are tunable and will need tuning.
- An admin UI, appeals, or automatic actions on reports.
- Screening on the device.

## Decisions

### 1. The term matcher is a pure function in `core/safety.py`
`TermMatcher(terms)` with `matches(prompt) -> bool`.
- **Normalising** (Python standard library only):
  1. NFKD, then drop combining marks;
  2. lowercase;
  3. map `0→o 1→i 3→e 4→a 5→s 7→t @→a $→s`;
  4. replace each run of non-letters with one space;
  5. wrap the result in spaces.
- **Terms** are normalised the same way. Each term matches if `" " + term + " "` occurs in the normalised prompt, which gives whole-word and whole-phrase matching.
- **Spelled-out words.** A prompt like `N-U-D-3` normalises to `n u d e`, which a plain term wouldn't match. So the matcher also joins each run of spelled-out single letters (`n u d e` → `nude`) and tests every single-word term as a substring of each joined run. A neighbouring one-letter word therefore cannot hide a term: in `a N-U-D-3 woman` the run is `a n u d e`, which joins to `anude` and contains `nude`. Multi-word terms match only through the whole-phrase check above.
  - **Trade-off:** a spelled-out word that merely contains a term, such as `g r a p e`, is also blocked.
- **The list** lives in `seed/safety/blocked_terms.txt`: one term or phrase per line, with `#` comments. It's loaded at startup and must contain at least one term, or the server won't start.
- **The starter list** covers sexual content, minors in a sexual context, graphic violence and slurs. It's kept short and is meant to be curated by the operator.

- **Alternative rejected: regular expressions per term.** They're harder for an operator to maintain and easy to get catastrophically slow. Normalised substring matching is linear in the prompt length.

### 2. Classifier interface and implementations
`core/safety.py`: `ImageClassifier.score(image_bytes: bytes) -> float`, the NSFW probability in [0, 1]. A score of `SAFETY_NSFW_THRESHOLD` (default 0.7) or more means flagged.

- **`services/safety/local_classifier.py`:** loads `transformers.pipeline("image-classification", model=SAFETY_MODEL_ID)` at startup (default `Falconsai/nsfw_image_detection`) on `SAFETY_DEVICE` (default `cpu`). The score is the `nsfw` label's score. Imports are lazy, as the Sana pipeline does.
- **`services/safety/stub_classifier.py`:** `StubClassifier(flag: bool)` returns 1.0 when `flag` is set and 0.0 otherwise.
- **Two classifier slots.** `main.py` builds an upload classifier and an output classifier. With a real backend, both slots hold the same local classifier instance. With the stub backend, `SAFETY_STUB_FLAG` (`none`, `outputs` or `all`) decides which stub flags: `outputs` flags only generated images, so the blocked-output and strike paths can be reached by hand with a normal photo. `all` flags uploads too.
- **`main.py`:**
  - with `MODEL_BACKEND=stub`, it uses the stub;
  - otherwise it builds the local classifier, and any exception during loading fails startup with "image classifier could not be loaded";
  - a `SAFETY_STUB_FLAG` other than `none` together with a non-stub backend is refused at startup.
- **Calls** run in `asyncio.to_thread`, because inference is CPU-bound.
- **One classifier instance is shared.** The worker processes one job at a time, but submit-time upload checks may run alongside it. A `threading.Lock` around `score` serialises inference, because Hugging Face pipelines aren't guaranteed thread-safe.

- **Alternative rejected: a third-party moderation API.** The user's decision: face-derived images must not leave the server.
- **Alternative rejected: running the classifier inside the generation pipeline.** It must also screen uploads, and it must apply to every backend.

### 3. Where the checks run in `submit`
The order becomes:
1. age and consent gate;
2. **pause check** (403 `generation_suspended`);
3. quota pre-check;
4. face count;
5. read and validate uploads;
6. **prompt screening**, for custom prompts only, after `_resolve_prompt` decides whether it's custom (400 `prompt_blocked`);
7. **upload screening**, each photo's bytes scored (400 `photo_blocked`);
8. reserve;
9. create the job and save the uploads.

- **Why the pause check comes early:** it's cheap and refuses before anything is read.
- **Why prompt screening comes before upload screening:** the term check is cheap, and the classifier is the expensive step, so it runs last before the reservation.
- **An upload classifier error** is a 503 `safety_unavailable`, a fail-closed refusal, and nothing is counted.

### 4. Output screening and strikes in the worker
`/images` is a `StaticFiles` mount over `<STORAGE_ROOT>/outputs/`, so any file there is fetchable by URL whatever the job's status. The pipeline therefore writes to a **staging path**, `<STORAGE_ROOT>/staging/<job_id>.png`, which is outside the mount. After `pipeline.run` returns:
1. Read the staged file and call `score` in a thread.
2. **Flagged:** delete the staged file, set `failed / content_blocked` with `finished_at`, refund the generation, and record a strike with `_call_safely(record_strike, user_id)`.
3. **Classifier exception:** delete the staged file, set `failed / safety_check_failed`, and refund. No strike.
4. **Safe:** move the staged file into `outputs/<job_id>.png` with `os.replace`, which is atomic on the same filesystem, then mark the job `succeeded` as today.

So no unchecked image is ever under `outputs/`.
- **Cleanup.** The `finally` block deletes any staged file left behind. The startup sweep deletes everything in `staging/`, which only a crash mid-job can leave behind.
- **Alternative rejected: replacing the static mount with an owner-checked image route.** It's the better long-term design (the existing "signed or authenticated image URLs" item in `todo.md`), but it changes how the app loads images and is out of scope here.

### 5. Storage: schema version 6, a new mixin
A new mixin, `repos/user_store_safety.py`.
- **Tables:**
  - `safety_strikes(id, user_id REFERENCES users ON DELETE CASCADE, created_at)`, indexed on `(user_id, created_at)`.
  - `reports(id, reporter_id REFERENCES users ON DELETE CASCADE, job_id, category, note, image_source CHECK IN ('server','device','none'), image_name, created_at, resolved_at NULL, outcome NULL)`, indexed on `(reporter_id, created_at)`.
- **Methods:** `record_strike`, `suspended_until(user_id, now, window, threshold) -> Optional[datetime]`, `add_report` (which checks the daily cap in the same transaction), `list_open_reports`, `resolve_report`, `expired_reports(now, max_age)`, `delete_report`.
- **`suspended_until`** finds the third-most-recent strike within the window and returns its time plus 24 hours, or None.
- **`_migrate`** adds both tables with `IF NOT EXISTS`, and `SCHEMA_VERSION = 6`.

### 6. Report images and their lifetime
- **Location:** `<STORAGE_ROOT>/reports/<report_id>.png`, outside `outputs/`, so the 24-hour sweep never sees them.
- **The server's copy:** `file_storage.copy_output_to_report(job_id, report_id)`, used when the job exists, belongs to the reporter, is `succeeded` and still has its output.
- **The device's copy:** used otherwise, after the existing upload checks (size and type). If no image comes with the report, it's recorded with source `none`.
- **Expiry:** `services/report_retention.py` (a separate module from `retention_service.py`) holds a pass that deletes reports older than `REPORT_RETENTION_DAYS` (default 30), and their image files. Errors are caught per report.
- **Account deletion:** the cascade removes the report rows, and the account-cleanup step deletes the image files of that reporter's reports, which are read before the user row is deleted. A crash between the two leaves orphan files, which the sweep removes as images with no row.

### 7. Reports API and operator CLI
- **`api/reports.py`:** `POST /reports` takes multipart `job_id`, `category`, `note?` and `image?`. It is an `async def`; the image copy and the database write run off the event loop.
- **Errors:** 400 `invalid_report`, 404 for another account's live job, 429 `too_many_reports`.
- **`scripts/reports.py`:** `list`, `show <id> --out <file>` and `resolve <id> --outcome <text>`. It uses `auth_db_path(Settings())` and the storage root, like `set_plan.py`.

### 8. Settings

| Setting | Default |
|---|---|
| `SAFETY_TERMS_FILE` | `./seed/safety/blocked_terms.txt` |
| `SAFETY_MODEL_ID` | `Falconsai/nsfw_image_detection` |
| `SAFETY_DEVICE` | `cpu` |
| `SAFETY_NSFW_THRESHOLD` | 0.7, from 0 to 1 |
| `SAFETY_STUB_FLAG` | `none` (`none`, `outputs` or `all`) |
| `STRIKE_LIMIT` | 3, at least 1 |
| `STRIKE_WINDOW_HOURS` | 24, at least 1 |
| `REPORTS_PER_DAY` | 20, at least 1 |
| `REPORT_RETENTION_DAYS` | 30, at least 1 |

The pause lasts `STRIKE_WINDOW_HOURS` from the third-most-recent strike.

### 9. App

**Errors and messages:**
- `api_errors.dart` adds `prompt_blocked`, `photo_blocked`, `generation_suspended` (with `suspended_until` read from the body), `too_many_reports`, `invalid_report`, `content_blocked` and `safety_unavailable`.
- `failure_messages.dart` adds `content_blocked`: "This image was blocked by our content rules and wasn't counted."
- `submit_flow.dart` shows SnackBars for `prompt_blocked`, `photo_blocked` and `safety_unavailable`, and a dialog for `generation_suspended`, with the time in local time.

**Reporting:**
- `features/report/report_sheet.dart` is a bottom sheet with the five category radios, a note field (max 500), and Send and Cancel buttons.
- It's opened from `ImageActionRow` (a new Report action) on the status success view and on the creation detail screen. Both pass the job id and the image bytes they already hold.
- The API client gains `submitReport(jobId, category, note, imageBytes)`.

Screen states:

| Screen | Loading | Empty / initial | Error | Success |
|---|---|---|---|---|
| Submit form (added behaviour) | Unchanged | Unchanged | `prompt_blocked`: SnackBar "Your prompt contains words we don't allow." `photo_blocked`: SnackBar "This photo can't be used. Choose another." `safety_unavailable`: "Checks are unavailable right now, try again." | Unchanged |
| Paused dialog | n/a | "Generating is paused until <local time> because recent results broke our content rules." with OK | n/a | Closing returns to the form with values kept |
| Status, failed with `content_blocked` | n/a | n/a | "This image was blocked by our content rules and wasn't counted." with New generation, and no image | n/a |
| Report sheet | Send spinner, controls disabled | No category: Send disabled | `too_many_reports`: "You've sent too many reports today. Try again tomorrow." Network: "Couldn't send the report. Try again." The category and note are kept in every error case | Sheet closes, SnackBar "Thanks, we'll review it." |

## Risks / Trade-offs

- **[What data is stored, and for how long]**
  - **Strikes:** user id and time. Rows older than the window are pruned on each `record_strike`, and they're deleted with the account.
  - **Reports:** reporter id, job id, category, note, image source, the image, the time, and the review outcome. Kept 30 days, then deleted with their image. Deleted with the reporter's account.
  - **Reported images are face-derived and kept longer than 24 hours.** The user chose this so reviewers can see what was reported. It goes in the privacy policy review already in `todo.md`.
  - **Classifier scores and matched terms are never stored.**
- **[Who can read it]**
  - Reports and their images: only the operator, through the CLI on the server. No HTTP endpoint lists or serves them.
  - Strikes: visible to the user only as the paused state with its end time.
- **[What is logged]** Safety events only: `prompt_blocked`, `photo_blocked`, `output_blocked`, `safety_check_failed`, `suspended`, `report_created`. Each carries the account id and the job or report id. Prompts, notes, scores and terms are never logged.
- **[Existing data and migration]** Schema version 6 adds two empty tables, idempotently. Existing jobs and accounts are unaffected. Rollback: the version-5 server ignores the new tables.
- **[False positives and negatives]**
  - A threshold of 0.7 on a general NSFW model will misfire sometimes, especially on swimwear or beach templates.
  - Output false positives are refunded, and strikes need 3 within 24 hours.
  - The term list will both over- and under-block.
  - → Both are settings, tuning is expected, and an item goes in `todo.md` to tune them against real outputs before launch.
- **[Failure and retry]**
  - A classifier error at upload gives 503 and counts nothing.
  - A classifier error on the output fails the job, refunds it and records no strike; the user retries.
  - The model failing to load at startup with a real backend stops the server, by design.
  - **The first start with a real backend downloads the model,** about 350 MB, into the Hugging Face cache. Production needs it pre-fetched or network access on first boot.
- **[Background tasks when a call raises]**
  - In the worker, `record_strike` and `refund` run through `_call_safely`, and the output check is inside the existing `try`. A failure fails the job and never stops the worker loop.
  - The sweep's report pass catches errors per report.
- **[Thread-safety of shared state]**
  - The classifier is shared between request threads and the worker thread, behind a `threading.Lock`.
  - Strike and report writes are single transactions under the store lock. The daily report cap is checked and written in the same transaction, so two concurrent reports can't exceed it.
- **[Performance]** CPU inference on a ViT model takes roughly 100–300 ms per image. Up to 4 uploads add up to about 1 second to submit, which is acceptable. A GPU device setting is available.
- **[Abuse]** Reports are capped at 20 a day per account, and images are limited to the existing 10 MB.

## Migration Plan

1. Deploy. Schema version 6 is created on start. With `MODEL_BACKEND=stub`, nothing else is needed.
2. For a real backend: install the `ml` group, pre-fetch `SAFETY_MODEL_ID`, and start. The server refuses to start if the classifier can't load.
3. Have the starter term list and the threshold reviewed and tuned before launch (tracked in `todo.md`).
4. Rollback: redeploy the previous version. The new tables and `reports/` folder are ignored, and can be deleted by hand.
