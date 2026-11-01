# Tasks

Work on branch `feat/add-result-ready-banner`. Do not push to `main`. All work is in `app/` (plus `todo.md`), and the server is not changed. "Decision N" refers to `design.md`. Tests use fakes, fake time (`tester.pump` in widget tests, or `fake_async` added as a dev dependency with `flutter pub add --dev fake_async`, since today it is only transitive), and a temporary directory for the store.

## 1. Result-ready event

- [x] 1.1 Add `schemas/result_ready.dart` with `ResultReady {jobId, userId}` (value equality). Give `HistorySync` a broadcast `Stream<ResultReady> results` that emits once right after each successful `store.save` in the catch-up (Decision 1), and close it when `historySyncProvider` is disposed. Verify in `test/features/history/history_sync_test.dart`:
  - a succeeded entry emits one event with its job and account;
  - failed, 404, still running, more than 24 hours old, a network error, and an image-fetch error each emit nothing;
  - two concurrent `run` calls emit one event per saved job;
  - a throwing `store.save` emits nothing.

## 2. Foreground watcher

- [x] 2.1 Add `features/result_ready/result_watcher.dart`, following Decision 2:
  - it observes the app lifecycle and the session;
  - while the app is resumed and someone is signed in, it calls `run(userId)`, then re-arms a one-shot 5-second timer after the run completes (in a `finally`);
  - pause, inactive and sign-out cancel the timer, and a cancelled watcher never re-arms;
  - resume runs at once.

  Start it from `ImageEditApp`. Verify with `test/features/result_ready/result_watcher_test.dart` (fake `HistorySync`, fake time):
  - runs every 5 s while resumed and signed in;
  - no overlap when a run takes longer than 5 s;
  - no runs while paused, and a run on resume;
  - none after sign-out;
  - a run for the new account after switching accounts;
  - a throwing run still re-arms.

## 3. Presenter and banner

- [ ] 3.1 Add a root `scaffoldMessengerKey` to `MaterialApp.router` in `main.dart`, and add `features/result_ready/result_ready_presenter.dart` (Decision 3 and 5):
  - it listens to `HistorySync.results`;
  - it skips an event whose `userId` is not the signed-in account, or whose job matches the current location `/status/<jobId>`;
  - otherwise it shows a floating SnackBar, "Your image is ready", with View, for 4 seconds, with `persist` set to `MediaQuery.accessibleNavigationOf(context)` so screen-reader users keep it until acted on;
  - View calls `router.push('/creations/<jobId>')`;
  - an error while presenting is logged with the job id and error type only.

  Verify with `test/features/result_ready/result_ready_presenter_test.dart` (a widget test with the real router and a fake store):
  - an event on home shows the banner;
  - View opens the creation detail with the image, and Back returns home;
  - the banner is gone after 4 s;
  - with `MediaQueryData(accessibleNavigation: true)`, the banner is still shown after 4 s, and it goes away once View is tapped;
  - no banner on `/status/<sameJob>`, and a banner on `/status/<otherJob>`;
  - two events show two banners in order;
  - an event for another account shows nothing.
- [x] 3.2 End-to-end widget test in `test/features/result_ready/result_ready_flow_test.dart`. With a fake generation service: submit, go to the profile, and have the job turn `succeeded`. Within 5 s of fake time the creation is in the store and the banner is shown on the profile. Also check that a job turning `failed` shows no banner, and that staying on the status screen shows no banner while still saving once.

## 4. Consent spec follow-up

- [x] 4.1 Check that `test/features/consent/consent_flow_test.dart` covers the three account-ui scenarios ("Unknown version on opening", "Version changes to an unknown one while open", "Leaving submits nothing"). Add a test for any that is missing; do not change app code unless a test fails. Remove the "Spec follow-up" item under "From add-age-gate-and-face-consent" in `todo.md`. Verify with `flutter test test/features/consent/` and `git diff todo.md`.

## 5. Integration and hand-off

- [x] 5.1 Run `flutter analyze && flutter test` in `app/`. Verify zero analyzer warnings and that all tests pass. Run `openspec validate add-result-ready-banner --strict`. The server is unchanged: run `uv run pytest -q` in `server/` once, and record the md5 of `server/storage/app.db` before and after.
- [ ] 5.2 **Manual. iOS simulator and Android emulator**, against a local server in log mode on a temporary storage root:
  - Submit a generation, go back home before it finishes: the banner appears; View opens the creation; Back returns home.
  - Submit, open the profile: the banner appears on the profile.
  - Stay on the status screen until it finishes: no banner.
  - Submit two quickly and go home: two banners one after the other.
  - Submit, send the app to the background until it would have finished, and reopen: the banner appears within about 5 s.
  - Sign out while a job runs: no banner after sign-out.
  - A screen reader announces the banner text and View.

  This box stays unticked until someone runs every step on both platforms. Name any skipped step in the PR.
- [x] 5.3 Push `feat/add-result-ready-banner`. Verify with `git log origin/feat/add-result-ready-banner -1` that it matches the local HEAD.
