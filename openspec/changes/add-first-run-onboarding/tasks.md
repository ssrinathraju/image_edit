# Tasks

Work on branch `feat/add-first-run-onboarding`. Do not push to `main`. All work is in `app/`; the server is not changed. "Decision N" refers to `design.md`. Tests use temporary directories or in-memory fakes only.

## 1. Seen record

- [ ] 1.1 Add `features/onboarding/onboarding_store.dart` (a marker file in the app support folder, `hasSeen` false on any error, `markSeen` never throws) and `onboardingSeenProvider` (Decisions 1 and 2). Verify that `test/features/onboarding/onboarding_store_test.dart` covers, on a temporary directory:
  - not seen by default;
  - seen after `markSeen`;
  - a read failure giving false;
  - a write failure not throwing and being logged;
  - the provider updating its state before the write completes.

## 2. Pages and routing

- [ ] 2.1 Add `OnboardingPages` with the three pages and their text, the indicator, Skip, Next and Get started (Decision 3). Verify that `test/features/onboarding/onboarding_pages_test.dart` covers:
  - each page's text;
  - Next and swiping back with the indicator following;
  - Skip on every page calling `onDone`;
  - Get started on the last page calling `onDone`, with Next not shown there.
- [ ] 2.2 Add the `/onboarding` and `/how-it-works` routes and the redirect order of Decision 2. Verify that `test/router_test.dart` covers:
  - a first signed-out launch landing on `/onboarding`, then `/login` after Skip;
  - a seen signed-out launch landing on `/login`;
  - a signed-in launch with an unseen record landing on `/` (or `/confirm-age` when that applies);
  - `/onboarding` while signed out and seen redirecting to `/login`;
  - an unreadable record showing onboarding;
  - a failed save still reaching `/login`.

## 3. Profile

- [ ] 3.1 Add the "How it works" row to `profile_screen.dart`, opening `/how-it-works`. Verify that `test/features/profile/profile_screen_test.dart` covers the row opening the pages, Get started and the back button returning to the profile while still signed in, and the record not being changed.

## 4. Integration and hand-off

- [ ] 4.1 Run `flutter analyze && flutter test` in `app/`, and verify zero analyzer warnings and all tests passing. The server is unchanged: run `uv run pytest -q` in `server/` once, and record the md5 of `server/storage/app.db` before and after to show it was untouched. Then run `openspec validate add-first-run-onboarding --strict`.
- [ ] 4.2 **Manual. iOS simulator:**
  - erase the app and install it fresh: onboarding shows; swipe through; Get started leads to sign-in;
  - quit and relaunch: sign-in shows directly;
  - sign in, open Profile, then How it works: the pages show and Get started returns to the profile;
  - delete and reinstall the app: onboarding shows again;
  - check the text wraps at the largest Dynamic Type size.

  This box stays unticked until someone runs it.
- [ ] 4.3 Push `feat/add-first-run-onboarding`. Verify with `git log origin/feat/add-first-run-onboarding -1` that it matches the local HEAD.
