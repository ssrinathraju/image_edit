# Design

## Context

See `proposal.md` for the motivation and `specs/` for the behaviour. The current app:

- **Startup.** `main.dart` loads `.env` and runs `ImageEditApp` with `routerProvider`. The router starts at `/splash`, and its `redirect` sends a loading or erroring session to `/splash`, a signed-out user to `/login` (unless they are already on a signed-out page), and a signed-in user through the age gate to `/`.
- **Device storage.** `flutter_secure_storage` holds the session, and `path_provider` is a direct dependency. My creations stores files under the app support folder.
- **Profile.** The profile screen already has rows for help, legal pages, consent, log out and delete.

## Goals / Non-Goals

**Goals:**
- Onboarding appears exactly when the spec says, and never traps or blocks the user.
- No new dependency and no server change.

**Non-Goals:**
- Changing the sign-in, consent or age flows.
- A reusable tour framework.

## Decisions

### 1. The "seen" record is a marker file
`features/onboarding/onboarding_store.dart` (`OnboardingStore`) provides `hasSeen()` and `markSeen()`. The marker is `<appSupport>/onboarding_seen`, created empty, and its presence means "seen".
- **`hasSeen()`** returns false on any exception, which gives the spec's "unreadable means show".
- **`markSeen()`** catches and logs any exception and never throws, which gives "unsavable means continue".

It's exposed through a Riverpod provider, so tests use an in-memory fake.

- **Alternative rejected: `flutter_secure_storage`.** The iOS Keychain survives uninstalling, so onboarding wouldn't come back after a reinstall, against the spec.
- **Alternative rejected: `shared_preferences`.** It's a new dependency for one boolean.

### 2. Loading the record and the router redirect
`onboardingSeenProvider` is an `AsyncNotifier<bool>` that loads `hasSeen()` once at startup and exposes `markSeen()`, which sets the state to true and then calls the store. The router listens to it, as it does for the session and account.

The redirect gets this order:
1. **The session is loading or errored:** `/splash`, as today.
2. **Signed out, and onboarding still loading:** `/splash`.
3. **Signed out, and not seen:** `/onboarding`. That is the only signed-out page allowed until it's seen.
4. **Signed out, and seen:** today's signed-out rules. `/onboarding` reached while signed out but already seen redirects to `/login`.
5. **Signed in:** today's rules. `/onboarding` itself isn't used signed in; the profile uses `/how-it-works` (Decision 3).

A launch with a saved session never consults the record (steps 1 and 5), which gives "a signed-in launch is not interrupted".

### 3. One pages widget, two routes
`OnboardingPages({required VoidCallback onDone})` contains:
- a `PageView` of three `_OnboardingPage`s, each with a Material icon, a title and a body;
- a dot indicator;
- Skip, at the top right of every page;
- Next, which becomes Get started on the last page.

It's used by two routes:
- **`/onboarding` (first launch):** `onDone` calls `markSeen()`, and the redirect then moves to `/login`.
- **`/how-it-works` (signed in, from the profile row):** `onDone` pops back to the profile. The app bar's back button also returns. It never changes the record.

**Page text:**
- **How it works:** "Pick a trending template or describe your own scene, add a photo of yourself, and we'll create a new image of you."
- **Your privacy:** "Your photo is used only for that image and then deleted. Results are saved on this device, and our copy is deleted after 24 hours."
- **The rules:** "You must be 18 or older. Only upload photos of yourself or of people who agreed. Unsafe content is blocked."

The text lives in one Dart file, ready for localisation later.

Screen states:

| Screen | Loading | Empty / initial | Error | Success |
|---|---|---|---|---|
| Launch | Splash while the session and the onboarding record load | n/a | Record unreadable: onboarding is shown | Not seen: page 1. Seen: sign-in |
| Onboarding pages | n/a | Page 1, indicator on the first dot, Skip and Next | Record save fails: logged, and sign-in is shown anyway | Skip or Get started: sign-in (first launch) or profile (how it works) |
| Profile "How it works" row | n/a | Always shown when signed in | n/a | Opens the pages |

## Risks / Trade-offs

- **[What data is stored, and for how long]** One empty marker file in the app's support folder, kept until the app is uninstalled. No personal data. It is per device, not per account.
- **[Who can read it]** Only the app, inside its sandbox.
- **[What is logged]** Only a failure to read or save the record, as the event name and exception type.
- **[Existing data and migration]** Existing installs have no marker, so **current users see onboarding once after the update**, but only when they're signed out at launch. A signed-in launch skips it. → Accepted: they would see it the next time they sign out, which is harmless.
- **[Failure and retry]** See Decision 1: it fails open toward showing onboarding when reading, and toward continuing when writing.
- **[Background tasks when a call raises]** None are added.
- **[Thread-safety of shared state]** One isolate. `markSeen` updates the provider's state before the async file write, so the redirect never shows the pages twice in a row.
- **[Copy accuracy]** The privacy and rules text promises behaviour the server and app enforce today: deleting the photo, saving results on the device, deleting the server copy after 24 hours, 18+, consent and screening. If retention changes, this text must change with it. → Noted in the design. The 24 hours is hard-coded copy, because the app doesn't know the server's setting before sign-in.

## Migration Plan

Ship it as a normal app update. No server change. Rollback is the previous app version, and a leftover marker file is harmless.
