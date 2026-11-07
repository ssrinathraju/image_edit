# Design

## Context

`PhotoPickerField` calls `ImagePicker.pickImage` and stores the result in a per-form `selectedPhotoProvider` (`PhotoScope`). Any exception currently becomes a generic SnackBar. The forms are `TemplateScreen` (`/template/:id`) and `CustomGenerationScreen` (`/create?prompt=`). The custom form already accepts `initialPhoto` through the route's `extra`, for Edit prompt.

On Android, when the activity is killed during a pick, the result can only be read back after restart with `ImagePicker().retrieveLostData()`. That returns the file, or a `PlatformException` (for example `camera_access_denied`). Permission refusals surface as `PlatformException` codes `camera_access_denied` and `photo_access_denied`. The app already has a method channel, `image_edit/backup`, in `AppDelegate.swift`, with a matching Kotlin entry point.

## Decisions

### Decision 1: A pending-pick note in the app's private folder
`PendingPickStore` (`features/common/pending_pick_store.dart`) writes `pending_pick.json` in the application support folder, atomically (temp file, then rename). The note holds:
`{userId, kind: "template"|"custom", templateId?, prompt?, startedAt}`

- **When it's written:** only on Android, just before `pickImage`.
- **When it's deleted:** after any normal return from `pickImage`, whether picked, cancelled or failed; in `SessionNotifier._clearLocalSession`; and after use.
- **How long it lives:** one hour, a constant.
- **Backups:** the folder is the same app-support area, and the note is added to the existing backup exclusion rules.

**Rejected: in-memory state.** It doesn't survive the process being killed, which is the whole point.

**Rejected: `shared_preferences`.** It would add a dependency for one small file.

### Decision 2: Restore once, when home is first shown
`HomeScreen.initState` already starts the catch-up. It also calls `restoreLostPick()`, a one-shot that runs only on Android:
1. Read the note, then call `retrieveLostData()`.
2. If the note exists, is less than an hour old, its `userId` matches the signed-in account, and a file came back: `push` the form route. That's `/template/<id>`, or `/create?prompt=<encoded>` with the file as `extra`. The template screen gains an `initialPhoto` from `extra`, like the custom form.
3. In every other case (no file, no note, too old, another account, or an exception) drop everything, delete the note, and log only the outcome kind.

The restored form shows a SnackBar: "We kept the photo you picked."

**Rejected: reopening the form directly from the router at startup.** The router redirects through splash, the age gate and onboarding. Home is the first stable signed-in screen, so restoring there respects every gate.

### Decision 3: The denied dialogs
`PhotoPickerField` catches `PlatformException` codes `camera_access_denied` and `photo_access_denied` and shows an `AlertDialog`:
- **Camera:** "Camera access is off. Turn it on in Settings to take a photo, or choose one from your library." with Open Settings, Choose from library and Cancel. Choose from library runs the gallery pick.
- **Library:** "Photo access is off. Turn it on in Settings to choose a photo." with Open Settings and Cancel.

Any other exception keeps the existing SnackBars. The form's state is untouched, because the dialog sits on top.

**Rejected:** a SnackBar with an action. The user chose the dialog, because a SnackBar is easy to miss.

### Decision 4: The `image_edit/settings` channel
`services/app_settings.dart` provides `AppSettings.open()`, which invokes `open` on the channel. It's behind a provider so tests can use a fake.
- **iOS:** `UIApplication.shared.open(URL(string: UIApplication.openSettingsURLString)!)`.
- **Android:** an `Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts("package", packageName, null))` started from `MainActivity` with `FLAG_ACTIVITY_NEW_TASK`.

A failure to open is logged and shows "Could not open Settings."

**Rejected: `permission_handler`.** It brings a large API and native setup we don't use. The user chose the channel.

### Decision 5: Download gets the same action
In `image_action_row.dart`, the `permissionDenied` SnackBar gets a "Settings" action that calls `AppSettings.open()`. Its text stays the same. This one widget is used by both the status screen and My creations.

## Screens and states

| Screen | States |
|---|---|
| Photo picker (template and custom forms) | Picking. Picked. Cancelled (no change). Camera-denied dialog. Library-denied dialog. Other failure (the existing SnackBar). |
| Home on start (Android) | Normal. Restoring: the form opens over home with the photo and the "We kept the photo you picked." SnackBar. A discarded recovery shows nothing. |
| Template or custom form, restored | The photo is selected. The prompt is filled in (custom). Generate is enabled if the usual rules allow. Back returns home. |
| Status and creation detail, download denied | The existing SnackBar text, now with a Settings action. |

## Risks and trade-offs

- **Data stored:** the pending note holds the account id, a template id or the typed prompt, and a timestamp. It lives at most one hour, on the device only, is excluded from backups, and is deleted on sign-out. The recovered photo is the picker's cached file, the same place a normal pick uses.
- **Who can read it:** only this app, in its private folder.
- **Logging:**
  - restore outcomes are logged as kinds only: `restored`, `no_note`, `expired`, `other_account`, `no_file`, `error`;
  - the prompt, the ids and file paths are never logged;
  - Settings open failures are logged with the error type.
- **Migration:** none.
- **Failure and retry:**
  - a corrupt or unreadable note counts as absent and is deleted;
  - if `retrieveLostData` raises, the note is deleted;
  - the restore never blocks home, because it runs without being awaited and catches everything.
- **Background tasks:** the restore is a single unawaited future guarded by `mounted`. Its errors are caught and logged.
- **Thread-safety:** the note is written atomically on the UI isolate. Only one pick runs at a time, because the picker is modal.
- **Trade-off:** after a restore, Back goes to home, not to the screen under the form before the kill (for example the status screen after Edit prompt).
