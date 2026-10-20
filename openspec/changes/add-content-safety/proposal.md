# Proposal

## Why

The app turns user prompts and face photos into realistic images, and nothing today stops sexual, violent or hateful content. Both app stores require moderation and a way to report AI-generated content, and this has to be in place before face conditioning makes the outputs realistic. The user chose a classifier that runs on our own server, so face-derived images never leave it. Third-party moderation APIs are ruled out.

## What Changes

- **Prompt screening.** Custom prompts are checked against a configurable blocked-term list, after normalising letter case, accents, common letter swaps (`0→o`, `@→a`, …) and separators, matching whole words only. A match gets 400 `prompt_blocked`, and nothing is created or counted. Template prompts are trusted.
- **Upload screening.** Each uploaded photo is scored by a local NSFW image classifier before the job is queued. A flagged photo gets 400 `photo_blocked`, and nothing is stored or counted.
- **Output screening.** Each generated image is scored before the job succeeds.
  - **Flagged:** the image is deleted and never served, the job fails with `content_blocked`, the generation is refunded, and a **strike** is recorded.
  - **The classifier errors:** the check fails closed. The job fails with `safety_check_failed`, the generation is refunded, and no strike is recorded.
- **Strikes.** An account with 3 strikes in 24 hours can't generate until 24 hours after the third-most-recent strike. It gets 403 `generation_suspended` with `suspended_until`. Everything else keeps working.
- **Reports.** `POST /reports` takes a job id, a category, an optional note and an optional image. It keeps the server's copy of the image if that still exists, otherwise the app's uploaded copy. The limit is 20 reports a day. Reports and their images are kept for 30 days, survive the 24-hour image sweep, and are deleted with the reporter's account. An operator CLI lists, exports and resolves them.
- **Enforcement.** With any model backend other than `stub`, the server refuses to start unless the classifier loads. The stub backend uses a stub classifier, which can be set to flag generated images only, or everything, for testing.
- **App:**
  - plain messages for `prompt_blocked`, `photo_blocked` and `content_blocked`;
  - a paused-account dialog showing when the pause ends;
  - a Report action on the status screen and on My creations' detail screen, with categories and an optional note.

Out of scope:
- an admin web UI;
- automatic actions on reports;
- appeals;
- a text classifier for prompts;
- third-party moderation;
- screening template preview images;
- age estimation from photos;
- face-swap or deepfake detection.

## Capabilities

### New Capabilities
- `content-safety`: covers prompt screening, upload and output screening with a local classifier, strikes and pauses, reports and how long they're kept, the operator review tool, startup enforcement, and keeping safety decisions private.

### Modified Capabilities
- `generation-flow-ui`:
  - "Display a human-readable error on failure" gains the `content_blocked` message;
  - new requirements for blocked prompt and photo messages, the paused-account dialog, and reporting from the status screen.
- `creation-history`: a new requirement for reporting a creation, sending its stored image.

## Impact

- **Server:**
  - new `core/safety.py` (the term matcher and the classifier protocol);
  - new `services/safety/` (the local and stub classifiers, and the report service);
  - `services/generation_service.py` (the pause check, prompt screening, upload screening);
  - `services/worker.py` (output screening and strikes);
  - `services/retention_service.py` (report expiry);
  - new `repos/user_store_safety.py` (strikes and reports tables, schema version 6);
  - `repos/file_storage.py` (a `reports/` folder);
  - `api/reports.py`;
  - `configs/settings.py`;
  - `main.py` (classifier wiring and startup enforcement);
  - new `scripts/reports.py`;
  - `seed/safety/blocked_terms.txt`;
  - `server/README.md`.
- **Dependencies:** the classifier uses `transformers` and `torch` from the existing optional `ml` group. Nothing is added to the default install, and tests use fakes. The default model is `Falconsai/nsfw_image_detection` (ViT, Apache-2.0). It's downloaded into the Hugging Face cache on first start with a real backend, and never committed to the repo.
- **App:** `core/api_client.dart`, `core/api_errors.dart`, `features/generation_status/failure_messages.dart`, `features/common/submit_flow.dart`, a new `features/report/report_sheet.dart`, the status and creation detail screens.
- **Data:** schema version 6 adds two tables. Report images go under `<STORAGE_ROOT>/reports/`.
