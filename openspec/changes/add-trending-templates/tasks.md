# Tasks

All work happens on branch `feat/add-trending-templates`. Do not push to `main`; open a PR at the end (group 9).

## 1. Server: template schema and catalog repo

- [ ] 1.1 Add `server/src/image_edit_server/schemas/template.py` with Pydantic models `Template` (`id` matching `^[a-z0-9]+(-[a-z0-9]+)*$`, `title`, `tags: list[str]`, `popularity: int` 0–100, `preview: str`, `prompt: str` ≤ `MAX_PROMPT_CHARS`) and `TemplateSummary` (`id`, `title`, `tags`, `preview_url`, with no prompt field); verify with `server/tests/schemas/test_template.py` covering a valid entry, a bad id, and out-of-range popularity
- [ ] 1.2 Add `TEMPLATES_DIR: str = "./seed/templates"` to `configs/settings.py`; verify `server/tests/configs/test_settings.py` asserts the default and the `IMAGE_EDIT_TEMPLATES_DIR` override
- [ ] 1.3 Add `server/src/image_edit_server/repos/template_catalog.py` with `CatalogError`, `TemplateCatalog` (`all()`, `get(id)`, `search(q)` — sorted by `(-popularity, title)`, case-insensitive substring on title and tags, blank `q` → all), and `load_catalog(templates_dir: Path)`, which rejects malformed JSON, duplicate ids, and missing preview files, naming the offending entry; verify with `server/tests/repos/test_template_catalog.py` (uses `tmp_path`) covering ordering, tie-break by title, tag search, case-insensitivity, blank query, no matches, duplicate id, missing preview, and malformed JSON

## 2. Server: seed catalog and preview script

- [ ] 2.1 Create `server/seed/templates/catalog.json` with the 12 entries from design.md Decision 10, writing each `prompt` as 1–2 descriptive sentences (≤ 300 chars) about a single person in that scene; verify `load_catalog` on it fails only on the missing previews (before 2.2)
- [ ] 2.2 Add `server/scripts/generate_template_previews.py` with `--placeholder` (Pillow-only 512×512 WebP, color derived from id, title drawn on it), default Sana mode (1024 → 512 WebP q80), `--force`, and `--only <id>`; it lazily imports the Sana pipeline so `--placeholder` runs without the `ml` group. Run `uv run python scripts/generate_template_previews.py --placeholder` from `server/` and verify 12 files appear in `server/seed/templates/previews/` and `load_catalog` now succeeds
- [ ] 2.3 Add `server/tests/scripts/test_generate_template_previews.py` that runs the placeholder mode against a temp catalog and asserts that one WebP per entry is created and that existing files are skipped without `--force`; verify `uv run pytest tests/scripts` passes
- [ ] 2.4 Confirm `.gitignore` does not exclude `server/seed/` and that previews are tracked (`git status` shows them); document the script (both modes and the `--group ml` requirement) in `server/README.md`

## 3. Server: templates API

- [ ] 3.1 Add `server/src/image_edit_server/services/template_service.py` (`list_templates(catalog, q) -> list[TemplateSummary]`, building `preview_url` as `/template-previews/<preview>`) and `api/templates.py` with `GET /templates?q=` plus a `get_catalog` dependency; verify `server/tests/api/test_templates.py` covers ordering, `q` filtering, blank `q`, empty results, and that no response item has a `prompt` key
- [ ] 3.2 In `main.py` `create_app`, load the catalog from `cfg.TEMPLATES_DIR` (fail fast on `CatalogError`), override `get_catalog`, include the templates router, and mount `StaticFiles` at `/template-previews`; let `create_app` accept the templates dir through `Settings` so tests can point it at a temp catalog. Verify a test fetches a `preview_url` and gets 200 with an image content type, and another test asserts `create_app` raises on a duplicate-id catalog
- [ ] 3.3 Update `server/tests/conftest.py` so every existing test builds the app against a small temp catalog (placeholder previews); verify the full `uv run pytest` passes

## 4. Server: template-based generation

- [ ] 4.1 Add `template_id: Optional[str] = None` to `schemas/job.py` `Job`; in `api/generations.py` make `prompt` optional and add the `template_id` form field; in `services/generation_service.submit` add the `catalog` parameter and the validation order from design.md Decision 4 (`invalid_template` for both fields given or an unknown id; neither given → `invalid_prompt`). Verify `server/tests/api/test_generations_submit.py` gains cases for: template accepted (202, job prompt equals the template prompt), unknown id → 400 `invalid_template`, both fields → 400 `invalid_template`, neither → 400 `invalid_prompt`; all existing submit tests still pass
- [ ] 4.2 Extend `server/tests/integration/test_generation_flow.py` with a template submission that polls to `succeeded` using the stub pipeline; verify it passes
- [ ] 4.3 Update `server/README.md` with `GET /templates` and the `template_id` field on `POST /generations` (including a curl example); verify the curl example works against a locally running server

## 5. App: dependencies, platform config, API client

- [ ] 5.1 Run `flutter pub add share_plus gal path_provider` in `app/`; add `NSCameraUsageDescription` and `NSPhotoLibraryAddUsageDescription` to `app/ios/Runner/Info.plist` and `android.permission.CAMERA` to `app/android/app/src/main/AndroidManifest.xml`; verify `flutter pub get` and `flutter analyze` pass
- [ ] 5.2 Add `app/lib/schemas/template.dart` (`TemplateSummary` with `fromJson`) and `app/lib/features/common/generation_request.dart` (`GenerationRequest {XFile photo, String? templateId, String? prompt}`, asserting exactly one of the two); verify with `app/test/schemas/template_test.dart`
- [ ] 5.3 In `app/lib/core/api_client.dart`: add `listTemplates({String? q})`, which resolves each `preview_url` with a new `resolveUrl(path)` that replaces `getResultImageUrl`; change `submitGeneration` to take a `GenerationRequest` and send either `template_id` or `prompt` with a single `faces` part whose `contentType` is set explicitly (`image/jpeg` or `image/png` from `XFile.mimeType`/extension); add `fetchImageBytes(url)` (dio `ResponseType.bytes`). Update `GenerationService` to match. Verify `app/test/services/generation_service_test.dart` is updated and passes, and add `app/test/core/api_client_test.dart` that uses a dio `HttpClientAdapter` fake to assert the multipart fields and content type for both request kinds

## 6. App: shared photo picker and submit controller

- [ ] 6.1 Add `app/lib/features/common/photo_picker_field.dart` (preview tile + bottom sheet with "Take photo" / "Choose from library", `maxWidth: 2048, imageQuality: 90`, camera errors → snackbar, library still works, tap the preview to replace); verify a widget test `app/test/features/common/photo_picker_field_test.dart` shows the empty state, then the preview after a fake picker returns a file (inject the picker through a provider)
- [ ] 6.2 Add `app/lib/features/common/submit_controller.dart` (`submitControllerProvider` with `isSubmitting` state, plus `lastRequestProvider` as a non-auto-dispose `StateProvider<GenerationRequest?>`); on success it stores the request and returns the job id, and on failure it rethrows with `isSubmitting` reset; verify `app/test/features/common/submit_controller_test.dart` covers success, which stores the last request, and failure, which resets the flag

## 7. App: home, template, and custom screens

- [ ] 7.1 Add `app/lib/features/home/home_notifier.dart` (loads on build, `setQuery` with a 300 ms debounce and a sequence-number guard against stale responses, `retry()`); verify `app/test/features/home/home_notifier_test.dart` uses `fakeAsync` with a fake client to assert debounce (one request after rapid typing), that a stale response is ignored, and the error → retry path
- [ ] 7.2 Add `app/lib/features/home/home_screen.dart` (search field, template grid of preview + title, an always-visible "Create your own" tile, loading/error-with-Retry/empty-results states); tapping a template goes to `/template/:id` with `extra`, and "Create your own" goes to `/create?prompt=<search text>`; verify with a widget test covering the grid, the empty-results state still showing "Create your own", and the error state Retry button
- [ ] 7.3 Add `app/lib/features/template_detail/template_screen.dart` (preview, title, the "Your photo will be used as reference" note, `PhotoPickerField`, Generate button disabled until a photo is chosen, no prompt field; fall back to the home catalog when `extra` is missing); on Generate it submits a `GenerationRequest(templateId)` and calls `context.go('/status/$jobId')`, or shows an error snackbar on failure; verify with a widget test asserting there is no `TextField` and Generate is disabled without a photo
- [ ] 7.4 Add `app/lib/features/custom_generation/custom_generation_screen.dart` (multi-line `TextField` with `minLines: 4`, pre-filled from the `prompt` query param, 500-char inline validation, `PhotoPickerField`, Generate disabled while the prompt is blank, the prompt is over 500 chars, or no photo is chosen); verify with a widget test covering the pre-fill, blank → disabled, and >500 → the validation message
- [ ] 7.5 Delete `app/lib/features/new_generation/` and its tests; update `app/lib/router.dart` with the routes from design.md Decision 5; verify `flutter analyze` is clean and `flutter test` passes

## 8. App: status screen actions

- [ ] 8.1 Rework `generation_status_screen.dart`: on a terminal state show Retry (hidden when `lastRequestProvider` is null; it resubmits and calls `context.go` to the new job) and Home (`context.go('/')`); on success also show Download and Share (both hidden when `kIsWeb`); fetch the image bytes once and cache them in the status notifier. Verify with a widget test covering which buttons appear for succeeded, failed, and web
- [ ] 8.2 Implement Download with `gal` (check or request access, `putImageBytes`, success snackbar, permission-denied message) and Share with `share_plus` (`XFile.fromData`, PNG mime type, `sharePositionOrigin` from the button's render box); wrap both behind a small `ImageActions` interface provided through Riverpod so the widget test can fake them; verify a widget test that tapping each calls the fake with the cached bytes

## 9. Integration and PR

- [ ] 9.1 Run `uv run pytest` in `server/` and `flutter analyze && flutter test` in `app/`; verify all pass with zero analyzer warnings
- [ ] 9.2 With the stub server running and the app on the iOS simulator: home grid loads with placeholder previews → search "beach" filters → empty search shows "Create your own" → template flow with a library photo reaches a succeeded result → Retry starts a new job → Share opens the sheet → Download saves to Photos → Home clears state → custom flow with pre-filled search text succeeds. Record the outcome in the PR description
- [ ] 9.3 Run `openspec validate add-trending-templates --strict` and fix any issues; then push the branch and open a PR to `main` with a summary, test plan, and screenshots from 9.2; verify the PR URL is returned
