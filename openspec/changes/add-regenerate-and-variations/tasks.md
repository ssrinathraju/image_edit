# Tasks

Work on branch `feat/add-regenerate-and-variations`. Do not push to `main`. All work is in `app/`, and the server is not changed. "Decision N" refers to `design.md`. Tests use fakes and a temporary directory for the store, and never a real device folder.

## 1. Record the source

- [x] 1.1 Add `CreationSource` (template with `templateId`, or prompt with `prompt`) and an optional `source` on `Creation` and `PendingGeneration` in `schemas/creation.dart`, with the JSON from Decision 4. Verify in `test/schemas/creation_test.dart`:
  - a round-trip of both kinds;
  - old JSON without `source` reads as null;
  - malformed `source` (an unknown kind, a missing id or prompt, a wrong type) reads as null and does not throw.
- [x] 1.2 Thread the source through the store, the submit flow and both save paths:
  - `CreationStore.remember` and `save` take an optional source;
  - `submit_flow` remembers the request's source;
  - the status screen and `HistorySync` copy it from the pending entry, with the status screen's `lastRequestProvider` fallback (Decision 4).

  Verify:
  - `creation_store_test.dart`: the source survives save and list, and an old-format `index.json` still lists;
  - `submit_flow_test.dart`: a template and a custom prompt are remembered with their sources;
  - `history_sync_test.dart`: a caught-up creation keeps its source;
  - `generation_status_screen_test.dart`: the watched save keeps the source.

## 2. Status screen actions

- [x] 2.1 In `_NavigationButtons`, label the held-request action "More like this" after success and "Try again" after failure, keeping today's behaviour and the in-flight disable. Verify in `generation_status_screen_test.dart`:
  - the label for a success and for a failure;
  - tapping submits the same photo and template or prompt and opens the new job's status;
  - no action after `lastRequestProvider` is cleared (as after a restart) or holds another job;
  - a quota refusal shows the limit dialog and submits nothing;
  - a double tap submits once.
- [x] 2.2 Add `initialPhoto` to `CustomGenerationScreen` (seeding `selectedPhotoProvider` in `initState`), and pass `state.extra` as an `XFile` in the `/create` route. Add "Edit prompt" for custom-prompt requests on the status screen (Decision 3). Verify:
  - `custom_generation_screen_test.dart`: the photo and prompt prefill, and nothing is submitted on open;
  - `generation_status_screen_test.dart`: Edit prompt is shown for a custom prompt and not for a template; tapping it opens the form prefilled; Back returns to the status screen; submitting an edited prompt opens a new status with the new prompt.

## 3. Make another

- [ ] 3.1 Add "Make another" to `CreationDetailScreen` when `source != null`, pushing `/template/<id>` or `/create?prompt=<encoded>` with no photo (Decision 5). Show it in the missing-file state too. Verify in `creation_detail_screen_test.dart` and `router_test.dart`:
  - template and custom creations open the right screen, prefilled, with no photo selected;
  - Back returns to the detail and nothing is submitted;
  - an older creation without a source has no Make another, and Download, Share and Delete still work;
  - a prompt with spaces, `&`, `#` and emoji round-trips through the URL;
  - a template the server no longer has shows "Could not load this template.".

## 4. Integration and hand-off

- [ ] 4.1 Run `flutter analyze && flutter test` in `app/`. Verify zero analyzer warnings and that all tests pass. Run `openspec validate add-regenerate-and-variations --strict`. The server is unchanged: run `uv run pytest -q` in `server/` once, and record the md5 of `server/storage/app.db` before and after.
- [ ] 4.2 **Manual. iOS simulator and Android emulator**, against a local server in log mode on a temporary storage root:
  - Generate from a template, then tap "More like this": a different image, and two creations with the same label.
  - Make a custom generation fail if possible (or use the stub), and check that "Try again" is shown.
  - On a custom result, tap Edit prompt: the photo and prompt are filled in. Change the prompt and submit: the new result.
  - Tap Home on a result: when you return to it from the result-ready banner or My creations, there is no More like this; Make another is offered instead.
  - From My creations, Make another on a template creation and on a custom creation: the right form, with no photo. Back returns. Pick a photo and submit: it works.
  - Use up the daily limit, then tap More like this: the limit dialog.
  - Open a creation saved before this change: no Make another.

  This box stays unticked until someone runs every step on both platforms. Name any skipped step in the PR.
- [ ] 4.3 Push `feat/add-regenerate-and-variations`. Verify with `git log origin/feat/add-regenerate-and-variations -1` that it matches the local HEAD.
