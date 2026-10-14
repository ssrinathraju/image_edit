# Design

## Context

See `proposal.md` for motivation and `specs/` for the behavior contract.

Current state that shapes the approach:

- Server: `POST /generations` takes `prompt` (required form field) + `faces`; `services/generation_service.py` validates and writes the `Job` with its prompt; the worker runs the pipeline from `job.prompt`. The job store is injected through a `get_store` dependency overridden in `create_app`. Outputs are served by a `StaticFiles` mount at `/images`. Pillow is already a runtime dependency; there is no database.
- Uploaded faces are deleted once a job finishes, so the server cannot rerun a job by itself. Any retry must resend the photo.
- App: Riverpod + go_router + dio. The `/` route is the multi-photo `NewGenerationScreen`. `DioApiClient.getJobStatus` already turns the relative `result_url` into an absolute URL with `AppConfig.apiBaseUrl`. Uploads use `MultipartFile.fromBytes(await f.readAsBytes())` so they work on web too.
- Dev targets are Chrome and the iOS simulator. The simulator has no camera.

## Goals / Non-Goals

**Goals:**

- Keep the catalog in the repo, loaded once at startup, so templates can be reviewed in PRs and tested without a database.
- Make the template prompt resolve on the server at submit time, so the worker and pipelines stay unchanged.
- Share a single photo picker and submit controller between the template and custom flows.

**Non-Goals:**

- Hot-reloading the catalog or an admin API to edit it.
- Download/Share on the web build. Both actions are hidden when `kIsWeb`; mobile is the release target.
- Changing the server's 1–4 face limit.

## Decisions

### 1. Catalog is a checked-in JSON file plus preview images

Layout:

```
server/seed/templates/
  catalog.json
  previews/<template-id>.webp
```

`catalog.json` is a list of entries:

```json
{
  "id": "golden-hour-beach",
  "title": "Golden Hour Beach",
  "tags": ["beach", "sunset", "summer"],
  "popularity": 92,
  "preview": "golden-hour-beach.webp",
  "prompt": "..."
}
```

`id` must match `^[a-z0-9]+(-[a-z0-9]+)*$`. `popularity` is an int from 0 to 100. A new setting, `TEMPLATES_DIR` (default `./seed/templates`, resolved the same way as `STORAGE_ROOT`), points at the folder.

- **Why:** the catalog is small (tens of entries), changes rarely, and benefits from PR review. A JSON file has no new dependency and is trivially testable with a temp dir.
- **Alternatives:** SQLite (adds a migration story for no current benefit); YAML (needs a new dependency; JSON is enough); hardcoding in Python (mixes data with code).

### 2. Catalog loading and validation live in `repos/`

`repos/template_catalog.py` exposes `load_catalog(templates_dir: Path) -> TemplateCatalog`. It parses each entry into a Pydantic `Template` model (`schemas/template.py`), checks that ids are unique and every preview file exists, and raises `CatalogError` naming the bad entry. `TemplateCatalog` holds an immutable tuple sorted by `(-popularity, title)` and provides `get(id) -> Template | None` and `search(q: str | None) -> list[Template]` (case-insensitive substring match on title and tags; a blank `q` returns everything).

`create_app` calls `load_catalog` while it builds the app, not lazily, so a bad catalog makes startup fail (spec: *Validate the catalog at startup*). The catalog is exposed through a `get_catalog` dependency that `create_app` overrides, the same pattern as `get_store`.

- **Why in-memory search:** with fewer than ~200 entries, a linear scan is microseconds. Not worth an index.

### 3. Public listing shape hides the prompt

`api/templates.py` exposes `GET /templates?q=` and returns `list[TemplateSummary]`, where `TemplateSummary` is `{id, title, tags, preview_url}` with `preview_url = f"/template-previews/{preview}"`. A separate response model, rather than `exclude=`, guarantees the prompt can never be serialized by accident. `create_app` mounts `StaticFiles(directory=templates_dir / "previews")` at `/template-previews`.

`preview_url` stays relative, like `result_url`. The app resolves both against `apiBaseUrl` with one helper, `resolveUrl(path)`, which replaces `getResultImageUrl`.

### 4. `template_id` resolves to a prompt at submit time

`POST /generations` changes `prompt` to `Annotated[str | None, Form()] = None` and adds `template_id: Annotated[str | None, Form()] = None`. `generation_service.submit` gains a `catalog` parameter and validates in this order:

1. Face count, then face images (unchanged).
2. If both `prompt` and `template_id` are given → 400 `invalid_template`.
3. If `template_id` is given → look it up; if it is unknown → 400 `invalid_template`; otherwise `prompt = template.prompt`.
4. Otherwise validate `prompt` as today. A missing prompt counts as empty, so sending neither field still returns `invalid_prompt`, as the existing spec says.

`Job` gains `template_id: str | None` for logging and debugging. The worker and pipelines are untouched because they already read `job.prompt`.

- **Alternatives:** resolving in the worker (spreads catalog access into a second layer, and an invalid id would only surface after the job was accepted with 202); sending the prompt to the app (the user chose to keep it server-side).

### 5. App routes and feature folders

| Route | Screen | Inputs |
|---|---|---|
| `/` | `HomeScreen` (`features/home/`) | — |
| `/template/:id` | `TemplateScreen` (`features/template_detail/`) | `TemplateSummary` passed through `extra`; if `extra` is missing (deep link or web reload), look it up from the home catalog provider |
| `/create?prompt=` | `CustomGenerationScreen` (`features/custom_generation/`) | initial prompt from the query parameter |
| `/status/:jobId` | `GenerationStatusScreen` (reworked) | — |

`features/new_generation/` is deleted. The shared pieces go in `features/common/`:

- `PhotoPickerField`: a preview tile plus a bottom sheet offering "Take photo" and "Choose from library". It calls `ImagePicker().pickImage(source, maxWidth: 2048, imageQuality: 90)`. Those limits keep uploads well under `MAX_UPLOAD_BYTES`, and on iOS they make the picker re-encode HEIC to JPEG, which the server accepts. If the camera throws or is unavailable (simulator), show a snackbar and leave the library option working.
- `GenerationRequest`: an immutable value object `{XFile photo, String? templateId, String? prompt}` with an assert that exactly one of `templateId`/`prompt` is set.
- `submitControllerProvider`: holds `isSubmitting`, calls `GenerationService.submit(request)`, and on success stores the request in `lastRequestProvider` and returns the `jobId`.

Moving from a screen to the status screen uses `context.go('/status/$jobId')`. Going home uses `context.go('/')`, which rebuilds the auto-dispose providers and clears the photo and prompt (spec: *Navigate between screens*).

### 6. Home search: debounce in the notifier, ignore stale responses

`HomeNotifier` (an `AsyncNotifier<List<TemplateSummary>>`) loads `GET /templates` on build. `setQuery(String q)` cancels any pending `Timer`, starts a new 300 ms timer, and then fetches `?q=`. Each fetch gets an increasing sequence number, and a response is applied only if it is the latest. That stops a slow earlier response from overwriting a newer one. The "Create your own" tile is rendered by the screen, not stored in state, so it shows in every state, including errors and empty results.

### 7. Retry resends the remembered request

`lastRequestProvider` is a plain `StateProvider<GenerationRequest?>` (not auto-dispose), so it survives the navigation to the status screen. Retry calls the same submit controller with that request and then calls `context.go('/status/$newJobId')`. If there is no remembered request (for example after a web reload), Retry is hidden.

- **Why client-side:** the server deletes faces after every job (an existing privacy requirement). A server-side "rerun" endpoint would have to keep the faces, which contradicts that requirement.

### 8. Download and Share

- Fetch the image bytes once through dio (`ResponseType.bytes`) when the user first taps Download or Share, and cache them in the status notifier.
- **Download:** use `gal` (`Gal.hasAccess` / `Gal.requestAccess`, then `Gal.putImageBytes`). On `GalException` with access denied, show the permission explanation. Chosen over `image_gallery_saver`, which is unmaintained, and over writing files ourselves, which would need platform channels.
- **Share:** use `share_plus` with an `XFile.fromData(bytes, mimeType: 'image/png', name: '<jobId>.png')`. On iPad the share sheet needs `sharePositionOrigin`; pass the Share button's render box rect. Use the API of whichever `share_plus` major version `flutter pub add` resolves, and do not pin an old major.
- Both buttons are hidden on web (`kIsWeb`).

Platform config: iOS `Info.plist` gets `NSCameraUsageDescription` and `NSPhotoLibraryAddUsageDescription`; Android `AndroidManifest.xml` gets `android.permission.CAMERA`. `gal` needs no extra Android permission on API 29+.

### 9. Preview generation script

`server/scripts/generate_template_previews.py`:

- `--placeholder`: Pillow only, no ML. It writes a 512×512 WebP for each template that is missing a preview: a solid color derived from the id with the title drawn on it. This mode lets the catalog validate in CI and in tests before real previews exist.
- Default mode: builds `SanaPipeline(Settings())` and runs each template prompt at 1024×1024 into a temp PNG. It then downsizes to 512×512 WebP (quality 80) in `previews/`. It skips templates that already have a preview unless `--force` is passed, and `--only <id>` regenerates a single one.
- Run with `uv run --group ml python scripts/generate_template_previews.py`. CI never runs it.

Order of work: commit placeholder previews first so everything is testable. Real previews are generated locally and committed in the same PR before review if time allows; otherwise they go in a follow-up commit on the branch. At 4 steps on CPU each image takes about 3–5 minutes, so the 12-entry seed takes about 1 hour.

### 10. Initial seed catalog

There are 12 entries. Prompts are written for Sana and describe one person, so face conditioning can slot in later without rewriting them. Titles and tags:

| id | title | tags | popularity |
|---|---|---|---|
| golden-hour-beach | Golden Hour Beach | beach, sunset, summer | 95 |
| neon-city-night | Neon City Night | city, night, neon, cyberpunk | 90 |
| studio-headshot | Studio Headshot | professional, portrait, linkedin | 88 |
| snowy-mountain-peak | Snowy Mountain Peak | mountain, snow, adventure | 82 |
| vintage-film-portrait | Vintage Film Portrait | retro, film, 70s | 80 |
| astronaut-on-mars | Astronaut on Mars | space, mars, sci-fi | 78 |
| watercolor-painting | Watercolor Painting | art, painting, watercolor | 75 |
| royal-portrait | Royal Portrait | classic, painting, royalty | 72 |
| cozy-coffee-shop | Cozy Coffee Shop | cafe, cozy, lifestyle | 70 |
| anime-hero | Anime Hero | anime, illustration, hero | 68 |
| desert-safari | Desert Safari | desert, travel, adventure | 64 |
| rainy-tokyo-street | Rainy Tokyo Street | city, rain, japan, night | 60 |

The implementer writes each prompt as one or two descriptive sentences of up to 300 characters, following the title.

## Risks / Trade-offs

- [Outputs won't contain the user's face until face conditioning lands] → The proposal states it explicitly, and the template screen copy says "Your photo will be used as reference" rather than promising a likeness. Face conditioning is the next change.
- [Preview binaries grow the repo] → 512×512 WebP at quality 80 is about 30–60 KB each, so about 0.6 MB for 12. Acceptable. Revisit if the catalog grows past about 100.
- [Changing the catalog needs a server redeploy] → Accepted for now; the non-goals rule out an admin UI.
- [HEIC or oversized photos rejected by the server] → The picker uses `maxWidth`/`imageQuality` so it re-encodes. The implementer must confirm the multipart part's content type is `image/jpeg`/`image/png` (set `contentType` explicitly from `XFile.mimeType` or the extension if dio sends `application/octet-stream`).
- [Stale search responses overwrite newer ones] → A sequence-number guard (Decision 6).
- [Retry unavailable after an app restart] → Retry is hidden when there is no remembered request; the user can start again from home.
- [Camera missing on simulator] → Handled by catching the error and keeping the library option (Decision 5).

## Migration Plan

No data migration. Deploy order: the server first (the endpoints are additive, and `prompt`-only submissions keep working), then the app. Rollback means reverting the PR. The old app still works against the new server.
