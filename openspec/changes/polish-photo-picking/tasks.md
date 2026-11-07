# Tasks

Work on branch `feat/polish-photo-picking`. Do not push to `main`. All work is in `app/`; the server is not changed. "Decision N" refers to `design.md`. Tests use fakes for `ImagePicker`, `AppSettings` and the platform (Android or iOS), and a temporary folder for the note.

## 1. Settings channel

- [x] 1.1 Add `services/app_settings.dart` (provider, `open()`, channel `image_edit/settings`) and the native handlers in `AppDelegate.swift` and `MainActivity.kt` (Decision 4). Verify that:
  - `test/services/app_settings_test.dart` checks the channel call with a mock handler, and that a channel error is logged and reported as failure;
  - `flutter build ios --no-codesign --debug` succeeds;
  - `flutter build apk --debug` succeeds.

## 2. Denied dialogs and Download

- [x] 2.1 Add the camera and library denied dialogs to `PhotoPickerField` (Decision 3). Verify that `test/features/common/photo_picker_field_test.dart` covers:
  - `camera_access_denied` shows the camera dialog with three actions;
  - Choose from library calls the gallery pick;
  - Open Settings calls the fake `AppSettings.open`;
  - `photo_access_denied` shows the library dialog;
  - another `PlatformException` code, or a non-platform error, still shows the existing SnackBars;
  - the form's prompt is kept.
- [x] 2.2 Add a Settings action to Download's permission-denied SnackBar (Decision 5). Verify in `test/features/common/image_action_row_test.dart` (or the existing status and creation-detail tests) that the action appears and calls `open`, and that "Could not open Settings." appears when `open` fails.

## 3. Restore after Android closes the app

- [x] 3.1 Add `PendingPickStore` (Decision 1). Write the note before an Android pick, delete it after any return and in `_clearLocalSession`, and add the file to the backup exclusion. Verify in `test/features/common/pending_pick_store_test.dart`:
  - write and read round trips, and the write is atomic;
  - a corrupt file reads as absent;
  - an old note is reported expired at 61 minutes;
  - the picker test shows the note is written on Android and not on iOS, and deleted after pick, cancel and failure;
  - the session test shows sign-out deletes it.
- [x] 3.2 Add `restoreLostPick()` on home's first show. Let the template screen accept `initialPhoto` through `extra`. Show the SnackBar on the restored form (Decision 2). Verify with `test/features/common/lost_pick_restore_test.dart` (fake picker returning `LostDataResponse`, fake clock, fake platform). It covers every restore scenario in the delta:
  - template restored;
  - custom form restored with its prompt;
  - another account;
  - more than one hour old;
  - cancelled (no file);
  - a normal pick leaves no note;
  - `retrieveLostData` throwing.

  In each case check the route opened (or none), the photo, the prompt, the SnackBar, that no submission was made, and that the note is deleted. Also check that iOS never calls `retrieveLostData`.

## 4. Integration and hand-off

- [x] 4.1 Run `flutter analyze && flutter test` in `app/`. Verify zero issues and all tests passing, with counts. Run `openspec validate polish-photo-picking --strict`. Remove the "Android release pass" item from `todo.md`.
- [ ] 4.2 **Manual. Android emulator and iOS simulator**, with a local server:
  - **Android:** turn on Developer options → "Don't keep activities". Open a template, choose Take photo, take a picture: the template reopens with it and "We kept the photo you picked." Repeat with the custom form and a prompt, using the library.
  - **Both platforms:** deny camera access, then tap Take photo. The dialog appears. Open Settings lands on the app's page, and Choose from library works.
  - **Both platforms:** deny photo access, then Download a result. Tap Settings in the message; it opens the app's page.

  This box stays unticked until someone runs it. It's part of the user's combined manual pass.
- [ ] 4.3 Push `feat/polish-photo-picking`. Verify with `git ls-remote` that the remote matches the local HEAD.
