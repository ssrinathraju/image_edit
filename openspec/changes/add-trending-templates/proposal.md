# Proposal

## Why

Today the app opens on a blank form that asks users to write a prompt from scratch, which is the hardest part of the product to get right. A browsable set of ready-made looks ("templates") lets a user get a good result by picking a style and adding one photo, while still leaving room for a custom prompt. This is the core loop we want before shipping the iOS and Android builds.

## What Changes

- New **home screen** that shows a grid of trending templates (preview image + title), a search bar, and a "Create your own" entry point.
- **Search** filters templates by title and tags; the results always include a "Create your own" option that carries the search text into the custom prompt.
- **Template flow**: pick a template → add one photo (camera or gallery) → generate. The template's prompt stays on the server; the app only sends `template_id`.
- **Custom flow**: expanded multi-line prompt text area (pre-filled with any search text) → add one photo → generate.
- **Result screen actions**: Retry (resubmit the same inputs as a new job), Download (save to the device photo library), and Share (system share sheet).
- New backend **template catalog**: `GET /templates` (with optional `q` search) returns templates sorted by a curated popularity score; preview images are served as static files. The catalog is seeded from a checked-in JSON file plus preview images.
- `POST /generations` accepts **either** `template_id` **or** `prompt` (exactly one). Unknown template ids are rejected.
- The app collects **one** photo per generation (the backend keeps accepting 1–4 faces, so this can be raised later without a server change).
- A one-off developer **script** generates the template preview images with the Sana pipeline so the seed images are original.
- **BREAKING (app only)**: the old "New Generation" screen is replaced by the home screen + custom flow. No external clients exist yet.

Out of scope: user accounts, usage-based "trending" ranking, favorites/history, admin UI for editing templates, and face conditioning. Note that until a face-conditioning change lands, the generated image follows the prompt but will not contain the user's face.

## Capabilities

### New Capabilities

- `template-catalog`: The server-side catalog of generation templates — listing, search, ordering by popularity, preview image delivery, and resolving a template id to its prompt.

### Modified Capabilities

- `photo-generation`: `POST /generations` accepts a `template_id` as an alternative to `prompt`, with exactly-one-of validation and rejection of unknown template ids.
- `generation-flow-ui`: Home screen with trending templates and search, template vs. custom flows, single photo from camera or gallery, and Retry/Download/Share on the result screen. Replaces the multi-photo New Generation screen.

## Impact

- **Server**: new `schemas/template.py`, `repos/template_catalog.py`, `services/template_service.py`, `api/templates.py`; changes to `api/generations.py` and `services/generation_service.py`; new static mount for preview images; new settings for the catalog location; seed data under `server/seed/templates/`; new script `server/scripts/generate_template_previews.py` (requires the `ml` dependency group, never run in CI).
- **App**: new `features/home/`, `features/template_detail/`, `features/custom_generation/`; reworked `features/generation_status/` (result actions); `api_client.dart` gains `listTemplates` and a `templateId` submit path; `router.dart` routes change.
- **App dependencies**: `share_plus` (share sheet), `gal` (save to photo library), `path_provider` (temp file for sharing). `image_picker` already present; camera source added.
- **Platform permissions**: iOS `NSCameraUsageDescription` and `NSPhotoLibraryAddUsageDescription`; Android `CAMERA`.
- **APIs**: additive `GET /templates`; `POST /generations` gains an optional field and a new 400 error code. Existing clients sending `prompt` keep working.
