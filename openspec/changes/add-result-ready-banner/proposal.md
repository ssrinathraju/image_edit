# Proposal

## Why

A generation takes a while. Users who leave the status screen to look at templates or their profile get no sign that their image is ready. It is saved to My creations only the next time they open home or My creations. A short in-app banner closes that gap.

Push notifications (while the app is closed) are wanted later. They need Firebase Cloud Messaging and, on iOS, the Apple Developer membership. So this change builds the in-app part around a small "result ready" event and a single presenter, which a push handler can feed later without a rewrite.

The change also bundles a pending spec follow-up from add-age-gate-and-face-consent. The consent screen's "Update the app to continue" behaviour for an unknown consent version is already built and tested, but not written in the account-ui spec.

## What Changes

- **Foreground catch-up:** while the app is in the foreground with a signed-in account and at least one unsaved remembered generation, the existing catch-up runs every 5 seconds, not only when home or My creations opens. It makes no checks in the background or when nothing is remembered.
- **Result-ready event:** each creation the catch-up saves produces a `ResultReady` event (job id, account id).
- **Presenter:** one app-level presenter turns each event into a bottom banner, "Your image is ready", with View, shown for 6 seconds. Several are shown one after another. There is no banner on that generation's own status screen, after sign-out, or for failed or blocked jobs.
- **View:** opens `/creations/<jobId>` on top of the current screen.
- **account-ui spec:** an ADDED requirement for "Update the app to continue" (spec only; the app already behaves this way).
- **todo.md:** remove the "Spec follow-up" item.

Out of scope:
- push notifications, Firebase, APNs, and any server change;
- local OS notifications, and background polling while the app is closed;
- a banner for failed or blocked generations;
- sound, vibration, or a notification inbox or badge.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `creation-history`: the catch-up also runs every 5 seconds in the foreground while something is remembered.
- `generation-flow-ui`: a new requirement for the result-ready banner.
- `account-ui`: a new requirement for "Update the app to continue".

## Impact

- **App only:**
  - `features/history/history_sync.dart` (reports what it saved);
  - new `features/result_ready/` (event, foreground watcher, presenter);
  - `main.dart` and `router.dart` (a root `ScaffoldMessenger` key, and knowing the route in front);
  - tests mirrored under `app/test/`.
- **Server:** unchanged. The extra polling is at most one status call per remembered job every 5 seconds, and only while the app is open.
- **No new dependencies.**
