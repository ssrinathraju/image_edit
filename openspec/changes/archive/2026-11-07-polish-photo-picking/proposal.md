# Proposal

## Why

There are two rough edges in photo picking, both listed in `todo.md` as the "Android release pass":
- **Lost photos.** On low-memory Android phones, the system often kills the app while the camera or photo picker is open. When the user returns, the app restarts on home and the photo they just took is lost.
- **Denied access.** When camera or photo access is denied, the app shows a generic message. Nothing helps the user turn access back on, and Download's existing "Allow it in Settings" message has no way to get there.

## What Changes

- **Restore after Android closes the app.** Before opening the camera or library on Android, the app writes a small private note on the device: which form (a template id, or the custom form with its current prompt), which account, and when.
  - After a restart, once the app reaches home for the same account, it uses `ImagePicker.retrieveLostData()` to get the photo back. It reopens that form with the photo and prompt filled in and shows "We kept the photo you picked." Nothing is submitted.
  - The note is removed once used, after a normal pick, on sign-out, or after one hour.
  - A photo with no matching note, for a different account, or that is too old is discarded.
- **Denied camera or photo access** shows a dialog with **Open Settings**. The camera dialog also offers Choose from library. Other picker failures keep today's messages.
- **Download's permission message** gets the same Open Settings action, on the status screen and in My creations.
- **Open Settings** uses a small method channel, `image_edit/settings`. On iOS it opens the app's Settings page; on Android, the app's details screen. No new package.

Out of scope:
- asking for permissions ahead of time;
- restoring the rest of the navigation stack;
- iOS lost-data recovery, which iOS doesn't need;
- the permission wording in Info.plist.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `generation-flow-ui`: "Download the generated image" adds Open Settings. Two requirements are added: the denied-access dialogs and Android photo restore.

## Impact

- **App only:**
  - `features/common/photo_picker_field.dart`;
  - new `features/common/pending_pick_store.dart` and `services/app_settings.dart`;
  - a restore hook where home first shows;
  - the template and custom forms, which accept a restored photo;
  - `image_action_row.dart`;
  - `MainActivity.kt` and `AppDelegate.swift`, for the settings channel;
  - tests.
- **Server:** unchanged.
- **Dependencies:** none new.
- **Data:** a single small JSON note in the app's private support folder, with a lifetime of at most one hour. It's excluded from backups, like `creations/`.
