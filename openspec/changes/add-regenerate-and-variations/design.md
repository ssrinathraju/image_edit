# Design

## Context

- **Retry today:** the status screen's Retry (`_NavigationButtons`) appears only when `lastRequestProvider`, a single in-memory `{jobId, GenerationRequest}`, matches the screen's job. It calls `submitAndOpenStatus`, so the limit dialog, consent and safety refusals already apply.
- **Creations:** `Creation` and `PendingGeneration` hold only `{jobId, label, timestamp}`.
- **Forms:** the custom form takes `initialPrompt` from the `/create?prompt=` query. The photo lives in `selectedPhotoProvider`, which is auto-dispose. The template screen is `/template/:id`.
- **Server:** the Sana pipeline passes no generator or seed, so every run samples a fresh one.

## Goals and non-goals

**Goals:**
- clearer Retry wording, with each variation as a new creation;
- edit a custom prompt while the photo is in hand;
- start again from a saved creation without the app keeping the photo.

**Non-goals:**
- batches of images per job;
- a stored or user-visible seed;
- keeping input photos;
- server changes.

## Decisions

### Decision 1: "More like this" is the existing Retry, relabelled; no seed
The action and its code path stay the same, only the label depends on the job's status. Variations differ because the pipeline already samples a new seed per run.

**Rejected:** a server-chosen seed recorded per job and passed to `GenerationPipeline.run`. It changes the server, the pipeline interface and the stub, and nothing in the app would use it: no reproduce or "same seed, new prompt" feature is planned. Per CLAUDE.md §3, add it when such a feature is.

**Rejected:** several images per job. It changes the job model, safety, quota, the status screen and My creations. The user chose one image per tap.

### Decision 2: The photo is held only as long as it is today
"More like this", "Try again" and "Edit prompt" all use the `GenerationRequest` in `lastRequestProvider`, so they disappear:
- after a restart;
- once another generation is submitted;
- after Home, which clears it.

**Rejected:** keeping the photo per job on the device. It keeps face photos longer than one session, which goes against the consent text ("used for this generation only"). The user chose to pick the photo again for older results.

If the picker's file has gone (the OS cleaned its temp folder), the submit fails with the existing error SnackBar. Nothing crashes, and the user can pick again from the form.

### Decision 3: Edit prompt passes the photo through the route
"Edit prompt" calls `context.push('/create?prompt=<prompt>', extra: photo)`. `CustomGenerationScreen` gains `initialPhoto` and seeds `selectedPhotoProvider` from it in `initState`, as it already does for the prompt.

**Rejected:** writing `selectedPhotoProvider` before pushing. The provider is auto-dispose and has no listener until the form mounts, so the value can be dropped.

Because the route is pushed, Back returns to the status screen. Submitting from the form uses `router.go('/status/<new>')`, as today.

### Decision 4: Creations record a source, read leniently
A new value type, `CreationSource`, is either `{kind: "template", templateId}` or `{kind: "prompt", prompt}`, in `schemas/creation.dart`. It is an optional `source` field on both `Creation` and `PendingGeneration`:
- **JSON:** `"source": {"kind": "template", "templateId": "..."}`, or with `"kind": "prompt"` and `"prompt": "..."`.
- **Reading:** a missing, null or malformed `source` reads as null. Old `index.json` and pending entries keep working without a migration.
- **Writing:** `remember` takes the source from the `GenerationRequest`. Both save paths (the status screen and the catch-up) copy it from the pending entry.

If the pending entry is missing, the status screen builds the source from `lastRequestProvider` when that is the same job, and otherwise saves none.

**Rejected:** parsing the label to tell a prompt from a template. A template's label is its title, not its id, and a prompt can equal a title.

### Decision 5: Make another opens the form, never submits
`CreationDetailScreen` shows "Make another" when `source != null`:
- for a template, `context.push('/template/<id>')`;
- for a prompt, `context.push('/create?prompt=<encoded>')`.

Neither passes a photo, so the user picks one. The forms' existing submit flow handles consent, the limit and safety. The template screen's existing "Could not load this template." state covers a template that was removed.

## Screens and states

| Screen | States |
|---|---|
| Status screen, after success | Request held: "More like this", plus "Edit prompt" for a custom prompt, and Home. Not held: Home only. Submitting: the actions are disabled. |
| Status screen, after failure | Request held: "Try again", plus "Edit prompt" for a custom prompt, and Home. Not held: Home only. |
| Custom form, opened by Edit prompt | Photo and prompt prefilled; Submit enabled when the existing rules allow. A prompt of 500+ characters shows the existing error. Back returns to the status screen. |
| Creation detail | With a source: "Make another" next to Download, Share and Delete. Without a source (older creation): no Make another. Missing file: the existing "no longer available" state, with Make another still shown when there is a source, because the image is not needed to start again. |
| Template screen or custom form, opened by Make another | No photo selected; template or prompt prefilled. Template load error: the existing message. |

## Risks and trade-offs

- **Data stored:** the template id, or the prompt, in each on-device creation and pending entry. For custom generations the prompt was already stored as the label, so nothing new is exposed. It is kept and deleted with the creation: eviction beyond 50, Delete, and account deletion. It stays out of device backups like the rest of `creations/`.
- **Who can read it:** only this app, on this device, for this account's folder. Nothing goes to the server.
- **Logging:** no new log lines with the prompt or template id. Existing logs carry only job ids and error types.
- **Migration:** none needed. Old entries read with no source (Decision 4), and a test covers an old-format `index.json`.
- **Failure and retry:**
  - Every new submission goes through `submitAndOpenStatus`, which handles the limit, consent, a pause, safety refusals and network errors.
  - A deleted picker file surfaces as the existing submit error.
  - "More like this" is disabled while a submit is in flight, so a double tap can't spend two generations (existing `submitControllerProvider` guard).
- **Background tasks:** the catch-up copies the source as it copies the label. A malformed source never throws, and reads as null.
- **Shared state:** `lastRequestProvider` stays a single in-memory value on the UI isolate, and the store keeps its serial operation queue.
- **Quota cost:** each variation is a full generation. That is intended and shown by the existing limit dialog.
