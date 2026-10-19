# Proposal

## Why

A finished generation is only visible on the status screen, and only while the server keeps it (24 hours). If users leave the screen before the result arrives, or forget to download it, the image is gone. Users need a place to find what they made. Results show people's faces, so the user chose to keep them **on the device only**, which leaves the server's 24-hour deletion as it is. Long-term server history can come later if it is really needed.

## What Changes

- **Saving.** When a generation succeeds, the app saves the image to its own private storage on the device, with:
  - the prompt or template title;
  - the creation time;
  - the job id;
  - the signed-in account.
- **Catching up.** The app remembers every submitted job. When the home or My creations screen opens, it checks jobs that haven't finished:
  - **Succeeded:** the image is saved.
  - **Failed, or gone from the server:** the job is dropped.
  - **Still running:** it's checked again later, up to 24 hours after submission.
- **Scope.** Each account sees only its own creations. Signing out hides them, and signing in again shows them. Deleting the account removes its creations and pending jobs from the device.
- **Limit.** The newest 50 creations per account are kept, and older ones are removed automatically.
- **New UI:**
  - a **My creations** button on the home screen;
  - a **grid**, newest first;
  - a **detail screen** with the image, its label and date, and Download, Share and Delete (with confirmation).

  Download and Share use the saved copy, so they work offline.
- **Saving can't fail a generation.** If saving fails, the status screen still shows the result, with a short note that it couldn't be saved.
- **No backups.** Saved files are excluded from iCloud and Android backups.

Out of scope:
- server-side or long-term history;
- sync between devices;
- search and filters;
- Delete all;
- favourites and albums;
- backfilling results made before this change;
- thumbnails.

## Capabilities

### New Capabilities
- `creation-history`: the on-device record of a user's finished generations. It covers what is saved and when, catching up on generations finished while the app wasn't watching, per-account scoping, the 50-item limit, the My creations screens, and removal on account deletion.

### Modified Capabilities
- None. The server is unchanged. The existing status-screen, download and share requirements in `generation-flow-ui` still hold; this change adds behaviour around them.

## Impact

- **App:**
  - new `features/history/` (store, catch-up service, grid and detail screens) and `schemas/creation.dart`;
  - `features/common/submit_flow.dart` (remember the submitted job and its label);
  - `features/generation_status/` (save on success);
  - `features/home/home_screen.dart` (the My creations button);
  - `features/auth/session_notifier.dart` (delete on account deletion);
  - `router.dart`.
- **Dependencies:** `path_provider` becomes a direct dependency (it is already in the lock file through other packages).
- **Native:**
  - iOS: a small method channel in `AppDelegate.swift` that marks the history folder as excluded from backup.
  - Android: backup rules (`fullBackupContent` and `dataExtractionRules`) that exclude the history folder.
- **Server and API:** none.
