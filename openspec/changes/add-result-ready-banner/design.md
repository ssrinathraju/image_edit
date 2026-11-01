# Design

## Context

Today a result is saved in one of two ways:
- by its status screen, which polls every 2 seconds while open;
- by `HistorySync`, the catch-up, which runs only when home or My creations opens. It is single-flight per account and never throws.

Nothing tells the user that a generation they walked away from has finished. Push notifications are wanted later, but they need Firebase Cloud Messaging and the Apple Developer membership, so this change is in-app only. It is shaped so that push can feed the same path later.

## Goals and non-goals

**Goals:**
- a banner on any in-app screen when a result is saved by the catch-up;
- one event type and one presenter that a later push handler reuses;
- write the existing "Update the app to continue" behaviour into the account-ui spec.

**Non-goals:**
- push, local OS notifications, and background work while the app is closed;
- banners for failed or blocked jobs;
- any server change.

## Decisions

### Decision 1: The event means "saved on this device", emitted by `HistorySync`
`HistorySync` gains a broadcast `Stream<ResultReady>`. `ResultReady` is a plain value, `{jobId, userId}`, in `schemas/result_ready.dart`. The catch-up adds one event right after `store.save` succeeds for an entry. Joined runs share one run, so each save gives exactly one event, whoever triggered the run.

**Rejected:** emitting when the status call first reports `succeeded`. The image might then fail to download, and View would open nothing. Emitting on save means View always has bytes to show, offline too.

**Rejected:** returning the saved ids from `run()`. Callers that join a run would each get the list and show duplicate banners.

**Later, for push:** a push handler runs the catch-up for the account named in the message. The save then emits the same event, so the presenter and the View navigation stay as they are.

### Decision 2: A foreground watcher drives the catch-up every 5 seconds
`ResultWatcher`, in `features/result_ready/result_watcher.dart`, is an app-level object that observes `AppLifecycleState` and the session:
- While the app is resumed and someone is signed in, it calls `HistorySync.run(userId)`, then schedules the next call 5 seconds after that run completes. A one-shot `Timer` is re-armed after each run, so runs never overlap and a slow network never stacks calls.
- On pause, inactive or sign-out it cancels the timer.
- On resume it runs at once and re-arms.

When the account has nothing remembered, `run` reads the local pending list, finds it empty, and makes no server call. So "no checks when nothing is remembered" costs one small file read every 5 seconds.

**Rejected:** listening to the store's change notifier to start and stop the timer. It is more state for the same effect: the empty-list read is cheap.

**Rejected:** reusing the status screen's 2-second notifier per job. That would mean a provider per job kept alive across screens, a second polling path that does the same job as the catch-up.

The interval is 5 seconds rather than 2 because the user is not watching the job. It caps the extra server load at one status call per remembered job every 5 seconds, and only while the app is open.

### Decision 3: One concrete presenter, no interface
`ResultReadyPresenter` subscribes to the event stream, using the root `ScaffoldMessenger` key that is set on `MaterialApp.router`. For each event it shows a `SnackBar`: "Your image is ready", with a View action, lasting 6 seconds, floating. The messenger's own queue shows several banners one after another.

It shows nothing in these cases:
- the event's `userId` is not the signed-in account;
- the router's current location is `/status/<that jobId>`.

View calls `router.push('/creations/<jobId>')`, so Back returns to the screen the user was on.

A push source later feeds the same stream (Decision 1), so there is still only one presenter. By CLAUDE.md §3, no interface is added for a second implementation that isn't planned.

**Rejected:** a `MaterialBanner` at the top of the screen. It stays until dismissed, needs manual queueing, and would cover app bars.

**Rejected:** an overlay package. It adds a dependency for what a SnackBar already does.

### Decision 4: View opens the saved creation, not the status screen
`/creations/:jobId` works offline and needs no server call. The status screen would fetch the job again and could hit the 24-hour expiry. Because the event is emitted only after the save (Decision 1), the creation always exists when View is tapped, unless the user deleted it in between. In that case the detail screen's existing "This image is no longer available" state covers it.

### Decision 5: Status-screen suppression uses the current route
The status screen saves its own result through `store.save` directly, not through `HistorySync`, so it never emits an event. But the watcher can save a job first while its status screen is open. The presenter therefore also skips an event whose job matches the route in front. Saving is idempotent per job, so the status screen's own save is then a no-op and its note still reads "saved".

### Decision 6: The consent follow-up is spec only
The consent screen already watches the account. It shows "Update the app to continue", with no Accept, when `consentTextFor(version)` is null, and `test/features/consent/consent_flow_test.dart` covers both opening on an unknown version and the version changing while the screen is open. This change only adds the requirement and checks that those tests match its scenarios. It adds a test only if the "Leaving submits nothing" scenario is not covered yet.

## Screens and states

| Screen | States |
|---|---|
| Result-ready banner (any signed-in screen) | Hidden: no event, the event is for that job's own status screen, or the account differs. Shown: text plus View for 6 s. Queued: the next banner shows when the current one ends or is dismissed. Tapped: opens the creation detail. |
| Creation detail, opened from View | The existing states: loaded; missing ("This image is no longer available" with Delete). |
| Consent screen with an unknown version | "Update the app to continue", with no Accept; Back counts as declining. |

## Risks and trade-offs

- **Data stored:** nothing new. Events live only in memory and are dropped when the app process ends. Creations are saved exactly as today.
- **Who can read it:** the banner shows no label or prompt, only fixed text, so a glance at the screen reveals nothing about the image. Only the signed-in account's events are shown.
- **Logging:** the watcher logs only lifecycle transitions and failures, with the job id and error type. It never logs labels, prompts, email addresses or image data, which matches the existing `HistorySync` logs.
- **Migration:** none, and no server change.
- **Failure and retry:**
  - A network error stops that run (existing behaviour) and the next tick retries in 5 seconds.
  - A 401 is handled by the session as today, and sign-out stops the watcher.
  - The run never throws.
  - If the presenter throws (for example, no messenger is mounted yet), the error is caught and logged per event. The creation is already saved, so only the banner is lost.
- **Background tasks:** the timer callback awaits `run`, which never throws, and the re-arm happens in a `finally`. A failed run cannot stop the loop, and a cancelled timer is never re-armed after pause or sign-out (guarded by a state check).
- **Shared state:** Dart runs these on one isolate. `HistorySync`'s per-account single-flight map already prevents concurrent runs; the watcher's timer is its only mutable state; the broadcast stream is closed when its provider is disposed.
- **Battery and server load:** polling happens only in the foreground, at most one status call per remembered job every 5 seconds. Remembered jobs are forgotten once saved, failed, unknown, or after 24 hours.
- **Trade-off:** nothing tells the user while the app is in the background or closed.
  - A result that finishes in the background is saved by the run on resume, and its banner shows then.
  - If the app was killed, the save and the banner happen at the next home visit.

  Both are acceptable until push exists.
