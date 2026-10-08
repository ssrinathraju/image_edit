# Proposal

## Why

The backend API is fully operational but there is no mobile client. This change creates the Flutter app in `app/` with a complete end-to-end generation flow — pick face photos, enter a prompt, submit, poll, and view the result — so the product can be used on iOS and Android.

## What Changes

- Replace the `app/.gitkeep` placeholder with a full Flutter project (`flutter create`).
- Add an API client layer that talks to the FastAPI backend (`POST /generations`, `GET /generations/{job_id}`, `GET /images/{job_id}.png`). Backend URL is configurable via a `.env`-style config (defaults to `http://localhost:8000`).
- **New Generation screen** — pick 1–4 face photos from the device gallery, enter a free-text prompt, validate locally (non-empty, ≤500 chars, 1–4 photos), submit to the backend, navigate to the status screen.
- **Generation Status screen** — poll job status every 2 seconds, show a progress indicator while running, display the generated image on success, show a human-readable error on failure. Allow retrying or starting a new generation.
- Simple two-screen navigation with a back button.
- No authentication UI (consistent with the current backend state).

## Capabilities

### New Capabilities

- `generation-flow-ui`: The mobile user interface for submitting a generation request and viewing its result. Covers face photo selection, prompt entry, submission, live status polling, and result display.

### Modified Capabilities

_(none — the backend API contract is unchanged)_

## Impact

- `app/` — entirely new Flutter project (Dart, Flutter 3.x).
- No changes to `server/`.
- New runtime dependencies in `app/pubspec.yaml`: `image_picker`, `dio`, `riverpod`/`flutter_riverpod`, `go_router`.
- `app/.gitignore` updated (Flutter-generated files, build artifacts).
