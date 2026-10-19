# Design

## Context

See `proposal.md` for the motivation and `specs/creation-history/spec.md` for the behaviour. The current app:

- **Submitting.** `features/common/submit_flow.dart` `submitAndOpenStatus` submits through `submitControllerProvider` and then `router.go('/status/$jobId')`. That's the only place that knows both the job id and the prompt or template used.
- **Status.** `GenerationStatusScreen` polls `getStatus` every 2 seconds and stops on a terminal state. On success, `resultImageBytesProvider` fetches the bytes once through `GenerationService.fetchImageBytes`, and Download and Share use those bytes through `ImageActions`. `GenerationJob` carries no prompt or template.
- **Session.** `Session` has `userId`. `SessionNotifier` has `signOut`, `deleteAccount` and `deleteAccountWithProvider`, which all end in `_clearLocalSession`.
- **Server.** It deletes result images 24 hours after a job finishes, and `GET /generations/{id}` answers 404 for unknown or expired jobs. The server is not changed.
- **Dependencies.** `path_provider` is already in `pubspec.lock` through other packages, but it isn't a direct dependency.

## Goals / Non-Goals

**Goals:**
- Never lose a result the user waited for, whether or not they stayed on the status screen.
- No new server state, and no images leaving the device except when the user downloads or shares one.
- Everything except the native backup exclusion can be tested with widget and unit tests using a temporary directory.

**Non-Goals:**
- Background checks while the app is closed (push or background fetch).
- Thumbnails, image compression or format conversion.
- Encrypting files beyond what the operating system's app sandbox provides.

## Decisions

### 1. Storage: one folder per account, a JSON index, files written atomically
The layout under `getApplicationSupportDirectory()` is `creations/<userId>/`:
- **`<jobId>.png`:** the bytes exactly as the server sent them.
- **`index.json`:** a list of `{jobId, label, finishedAt}`, newest first.
- **`pending.json`:** a list of `{jobId, label, submittedAt}`.

Every write goes to `<name>.tmp` and then renames over the target, so a crash never leaves a half-written index. The image file is written before the index entry that points at it. A crash in between leaves an orphan `.png`, which the next save for that account removes: any `.png` that isn't in the index.

`userId` is the server's ULID, so it's a safe folder name. `jobId` is a ULID as well.

- **Alternative rejected: SQLite (`sqflite`).** It's a new dependency and a schema to migrate, for at most 50 rows per account.
- **Alternative rejected: `shared_preferences` for the index.** It isn't meant for growing lists, and the image files still need a folder.
- **Alternative rejected: the caches folder.** iOS may empty it under storage pressure, so history would vanish unpredictably.

### 2. One store, with every operation serialised
`features/history/creation_store.dart` (`CreationStore`) owns the folder. Its methods are `list(userId)`, `save(userId, jobId, label, bytes, finishedAt)`, `delete(userId, jobId)`, `deleteAccount(userId)`, `remember(userId, jobId, label, submittedAt)`, `pending(userId)` and `forget(userId, jobId)`.

All of them run through one internal async queue, a chained `Future`, so the status screen's save and the catch-up's save of the same job can't interleave.
- `save` is idempotent per `jobId`: an existing entry is left alone.
- `save` also removes the pending entry, deletes orphan files, and evicts the oldest entries beyond 50, deleting their files.

The root folder comes in through the constructor, so tests use a temporary directory. The store is exposed through a Riverpod provider.

### 3. Remembering submissions and labelling them
After `submit` returns the job id, `submitAndOpenStatus` calls `store.remember(userId, jobId, label, now)` before navigating. The label is:
- the prompt text for a custom generation;
- the template title for a template generation, or the template id if no title is loaded.

The status screen and the catch-up both take the label from the pending entry. A job saved without one (for example, a status screen opened from an old route) gets an empty label, which the UI shows as "Creation".

### 4. Saving from the status screen
When the status notifier reaches `succeeded` and `resultImageBytesProvider` has the bytes, the screen calls `store.save(...)` once, using `finishedAt = now`. The bytes are already in memory, so there's no second download.
- **On any exception:** the screen shows a SnackBar saying "Couldn't save to My creations". The pending entry stays, so the catch-up retries while the server still has the image. The view itself doesn't change.

### 5. Catching up (`HistorySync`)
`features/history/history_sync.dart` runs from `initState` of the home screen and the My creations screen. One run at a time: a second call while a run is in flight returns the same future. For each pending entry of the signed-in account, in order:
1. If `submittedAt` is more than 24 hours ago, forget it.
2. Otherwise call `getStatus(jobId)`:
   - **`succeeded`:** `fetchImageBytes(result_url)`, then `save`.
   - **`failed`:** forget it.
   - **404:** forget it.
   - **Still queued or running:** keep it.
   - **Network error, timeout, 5xx, or an error fetching the image:** keep it, and stop the run (the device is probably offline).
   - **401:** stop the run. The existing 401 handling signs the user out.

The run never shows an error. When it saves something, the My creations grid refreshes through the store's change notifier.

- **Alternative rejected: keep polling after the user leaves the status screen.** That means timers outliving the screen, plus extra work when the app is backgrounded. Catching up on the next home visit covers the same need with less machinery.

### 6. Scope and account deletion
- **Scope.** The store is always called with the signed-in session's `userId`. With no session, nothing is shown.
- **Sign-out.** It deletes nothing.
- **Account deletion.** `deleteAccount` and `deleteAccountWithProvider` call `store.deleteAccount(userId)` after the server confirms the deletion and before `_clearLocalSession`. That removes the account's whole folder. If the local delete throws, it's logged and sign-out still completes. The next time the store is created, it deletes folders listed in a `deleted.json` tombstone written before the attempt, so a crash can't leave the files behind.

### 7. Excluding creations from backups
- **iOS.** A method channel `image_edit/backup`, with the method `excludeFromBackup(path)` in `AppDelegate.swift`, sets `URLResourceValues.isExcludedFromBackup = true` on `creations/`. The store calls it whenever it creates that folder, and once at app start (it's idempotent). A failure is logged and ignored.
- **Android.**
  - `res/xml/backup_rules.xml` is referenced by `android:fullBackupContent` for Android 11 and lower. It holds `<exclude domain="file" path="creations/"/>`, because `getApplicationSupportDirectory` maps to `files/`.
  - `res/xml/data_extraction_rules.xml` is referenced by `android:dataExtractionRules` for Android 12 and higher. It excludes the same path for both cloud backup and device transfer.
- **Tests.** In Dart, the channel sits behind a small `BackupExclusion` interface so tests use a fake. The real exclusion can only be checked by hand (task 7.2).

- **Alternative rejected: allowing backups.** It would copy face images into the user's cloud account, which goes against the device-only decision.

### 8. Screens and routes
- **Routes:** `/creations` (grid) and `/creations/:jobId` (detail).
- **Home:** an app-bar icon button with the tooltip "My creations".
- **Grid:** `GridView` with 3 columns, each cell `Image.file(..., cacheWidth: 300)` with `errorBuilder` showing a placeholder.
- **Detail:**
  - the image `Image.file` at full width;
  - the label (or "Creation") and the date in the device locale;
  - **Download:** `ImageActions.saveToLibrary` with bytes read from the file;
  - **Share:** `ImageActions.share` with the same bytes;
  - **Delete:** a confirmation dialog, then `store.delete` and pop.

Screen states:

| Screen | Loading | Empty | Error | Success |
|---|---|---|---|---|
| My creations grid | Spinner while the index is read (the first time only) | "Your creations will appear here" | Index unreadable: treated as empty and logged. A cell whose file is missing or unreadable shows a placeholder | Grid, newest first. A background catch-up adds new cells as they're saved |
| Creation detail | Spinner while the file is read | n/a | File missing or unreadable: "This image is no longer available", with Delete. Photo permission denied on Download: the same message as the status screen. Share failure: SnackBar | Image, label and date, with Download, Share and Delete |
| Status screen (added behaviour) | unchanged | unchanged | Save failed: SnackBar "Couldn't save to My creations"; the view is unchanged | unchanged, and the creation is saved quietly |
| Home (added behaviour) | unchanged | unchanged | The catch-up never shows errors | The My creations button is always visible when signed in |

## Risks / Trade-offs

- **[What data is stored, and for how long]**
  - On the device: up to 50 images per account, roughly 1–3 MB each at 1024×1024 PNG, so up to about 150 MB per account. Each has an index entry with the job id, the label (the prompt the user typed, or a template title) and the time it finished.
  - Pending entries hold the job id, label and submission time for at most 24 hours.
  - All of it stays until the user deletes a creation, it's evicted beyond 50, the account is deleted from the app, or the app is uninstalled.
  - **Nothing new is stored on the server.**
- **[Who can read it]**
  - Only this app, inside the operating system's app sandbox. Files use the default data protection: on iOS, readable after the first unlock following a reboot.
  - Anyone holding the unlocked phone who signs in to the same account sees its creations. A different account on the same phone does not, because the UI is scoped by `userId`. The files are not encrypted from each other inside the sandbox, which is accepted for a per-device feature.
  - Excluded from cloud backups.
- **[What is logged]** Only failure events: the event name, the job id and the exception type. Never prompts, image bytes or file paths that contain a user id.
- **[Existing data and migration]** None. History starts empty on update, and results from before the update aren't backfilled. Uninstalling the app removes everything.
- **[Failure and retry]**
  - **Save fails on the status screen:** a SnackBar, and the pending entry stays for the catch-up.
  - **Catch-up network failure:** the run stops quietly and retries on the next home or My creations visit.
  - **Image gone from the server after 24 hours:** a 404 forgets the job, so that result is lost. This is the accepted limit of device-only history when the user doesn't open the app within 24 hours.
  - **Disk full:** the save fails as above. Eviction only runs after a successful save.
- **[Background tasks when a call raises]** The catch-up runs in the foreground from screen `initState`. It catches every exception per job, logs it, and never lets one end the app or show an error. Being on a single-flight future, a crash in one run can't wedge later runs: the future completes, with an error that is caught.
- **[Thread-safety of shared state]** Dart runs this on one isolate, but async gaps can interleave. Every store operation goes through one serial queue (Decision 2), and `save` is idempotent per job id. So a status-screen save and a catch-up save of the same job create one entry. Index files are replaced by atomic rename.
- **[Storage use]** Up to about 150 MB per account, and more if several accounts use one phone. → The limit of 50 per account bounds it. Thumbnails or compression can be added later if users complain.
- **[Native code]** The iOS method channel and the Android backup rules are new native touch points, which unit tests can't verify. → Manual task 7.2 checks the backup exclusion.

## Migration Plan

Ship it as a normal app update. There are no server changes and no data migration. Rollback is shipping the previous app version: the `creations/` folder stays unused on disk until it's uninstalled or a later version reads it again.
