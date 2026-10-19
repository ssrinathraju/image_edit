# Tasks

Work on branch `feat/add-on-device-history`. Do not push to `main`. All work is in `app/`, and the server is not changed. "Decision N" refers to `design.md`. Tests use a temporary directory for the store and never touch a real device folder.

## 1. Dependency and model

- [x] 1.1 Add `path_provider` as a direct dependency (`flutter pub add path_provider`) and add `schemas/creation.dart` with `Creation {jobId, label, finishedAt}` and `PendingGeneration {jobId, label, submittedAt}`, each with JSON round-trip. Verify that `flutter pub get` succeeds and that `test/schemas/creation_test.dart` covers the round-trip, an empty label, and the timestamp format.

## 2. Creation store

- [x] 2.1 Add `features/history/creation_store.dart`, following Decisions 1 and 2:
  - a root folder injected through the constructor, with per-account folders;
  - atomic writes, with the `.tmp` file renamed over the target;
  - one serial operation queue;
  - `list`, `save` (idempotent per job, removes the pending entry, cleans orphan files, evicts beyond 50), `delete`, `remember`, `pending`, `forget`;
  - a change notifier.

  Verify that `test/features/history/creation_store_test.dart` covers each of the following:
  - save then list, newest first;
  - a second save of the same job being a no-op;
  - the 51st save evicting the oldest entry and its file;
  - accounts being isolated;
  - delete removing the entry and the file;
  - a half-written `.tmp` file being ignored;
  - an orphan `.png` being removed on the next save;
  - a corrupt `index.json` reading as empty;
  - two saves of the same job started together creating one entry;
  - `remember`, `pending` and `forget`;
  - save removing the pending entry.
- [x] 2.2 Add `deleteAccount(userId)` with the tombstone from Decision 6. Verify with tests in the same file:
  - the account's folder is gone and other accounts are untouched;
  - a tombstone left by a failed delete is finished the next time a store is created.

## 3. Backup exclusion

- [x] 3.1 Add the `BackupExclusion` interface with a method-channel implementation (`image_edit/backup`, `excludeFromBackup(path)`). The store calls it when it creates `creations/` and once at startup, and logs and ignores failures. Add the handler in `ios/Runner/AppDelegate.swift`, which sets `isExcludedFromBackup` on the URL. Verify:
  - the store test checks the fake is called with the `creations/` path and that a throwing fake doesn't break saving;
  - `flutter build ios --no-codesign --debug` succeeds.
- [ ] 3.2 Add `android/app/src/main/res/xml/backup_rules.xml` and `data_extraction_rules.xml`, each excluding `domain="file" path="creations/"`, the latter for both cloud backup and device transfer. Reference them from `AndroidManifest.xml` with `android:fullBackupContent` and `android:dataExtractionRules`. Verify that `flutter build apk --debug` succeeds and that the merged manifest contains both attributes.

## 4. Remember on submit, save on success

- [ ] 4.1 In `submit_flow.dart`, after the job id returns and before navigating, call `remember(userId, jobId, label, now)`. The label is the prompt for a custom generation, and the template title (or id) for a template (Decision 3). Verify that `test/features/common/submit_flow_test.dart` covers:
  - a custom prompt being remembered with its text;
  - a template being remembered with its title;
  - a failed submit remembering nothing.
- [ ] 4.2 On the status screen, once the job has succeeded and the bytes are loaded, call `save` once, with the label from the pending entry and an empty label if there is none (Decision 4). Show the "Couldn't save to My creations" SnackBar when the save throws. Verify that `test/features/generation_status/generation_status_screen_test.dart` covers:
  - success saving exactly once, even after a rebuild or reopening the screen;
  - a throwing store showing the SnackBar while the image, Download and Share stay visible;
  - a failed job saving nothing.

## 5. Catch up

- [ ] 5.1 Add `features/history/history_sync.dart`, following Decision 5: single-flight, running per pending entry in order, using the 24-hour cutoff, and stopping on a network error or 401. Verify that `test/features/history/history_sync_test.dart`, with a fake service and a fake clock, covers:
  - succeeded being saved;
  - failed being forgotten;
  - 404 being forgotten;
  - running being kept;
  - more than 24 hours being forgotten without a call;
  - a network error keeping the entry and stopping the run;
  - an image-fetch error keeping the entry;
  - two concurrent runs causing one set of calls;
  - no error ever reaching the caller.
- [ ] 5.2 Run `HistorySync` from `initState` of the home screen and the My creations screen. Verify that `test/features/home/home_screen_test.dart` covers home triggering a run and an offline run showing no error.

## 6. Account deletion

- [ ] 6.1 In `SessionNotifier.deleteAccount` and `deleteAccountWithProvider`, call `store.deleteAccount(userId)` after the server confirms and before `_clearLocalSession`. Log and continue if it throws, and leave `signOut` unchanged (Decision 6). Verify that `test/features/auth/session_notifier_test.dart` covers:
  - both delete paths removing the account's creations and pending entries;
  - a server failure deleting nothing locally;
  - a throwing local delete still signing out;
  - sign-out keeping the creations.

## 7. Screens

- [ ] 7.1 Add the routes `/creations` and `/creations/:jobId`, the home app-bar button "My creations", `features/history/creations_screen.dart` (the grid) and `features/history/creation_detail_screen.dart`, with the states in the Decision 8 table. Verify:
  - `test/features/history/creations_screen_test.dart` covers newest first, the empty state, a placeholder for a missing file, a cell opening the detail, and a creation saved by the catch-up appearing without leaving the screen;
  - `test/features/history/creation_detail_screen_test.dart` covers the image, label and date, an empty label shown as "Creation", Download and Share calling a fake `ImageActions` with the stored bytes, the permission-denied message, Delete with confirm, a cancelled delete, and "This image is no longer available" with Delete;
  - `test/router_test.dart` covers reaching both routes from home and going back, and that a signed-out user is redirected to sign-in.

## 8. Integration and hand-off

- [ ] 8.1 Run `flutter analyze && flutter test` in `app/`. Verify zero analyzer warnings and that all tests pass. Then run `openspec validate add-on-device-history --strict`. The server is unchanged: run `uv run pytest -q` in `server/` once to confirm, and record the md5 of `server/storage/app.db` before and after to show it was untouched.
- [ ] 8.2 **Manual. iOS simulator and Android emulator**, against a local server in log mode on a temporary storage root:
  - Generate from a prompt and wait: it appears in My creations with the prompt and date.
  - Generate from a template and go back to home before it finishes. A few seconds later, open My creations: it appears, labelled with the template.
  - Turn on airplane mode: the grid, the detail, Download and Share still work.
  - Delete a creation, both cancelling and confirming.
  - Sign out, then sign in as another account: the grid is empty. Sign back in to the first account: its creations are back.
  - Delete the first account, then register it again: My creations is empty.

  This box stays unticked until someone runs every step on both platforms. Name any skipped step in the PR.
- [ ] 8.3 **Manual. Backup exclusion.**
  - **iOS:** check in Xcode's device file browser or with `xattr` on the simulator's container that `Library/Application Support/creations` carries the backup-exclusion attribute.
  - **Android:** run `adb shell bmgr backupnow <package>` and confirm, from `adb logcat` or by restoring, that `files/creations/` isn't included.

  This box stays unticked until someone runs it.
- [ ] 8.4 Push `feat/add-on-device-history`. Verify with `git log origin/feat/add-on-device-history -1` that it matches the local HEAD.
