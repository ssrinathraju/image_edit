# Proposal

## Why

A new user lands straight on a sign-in screen with no idea what the app does, how their face photos are handled, or what the rules are. A short first-run introduction explains the app and makes the privacy promise visible before anyone creates an account. It is the smallest of the optional v1 features, it is app-only, and it needs no outside setup.

## What Changes

- **First launch on a device:** three onboarding pages appear before the sign-in screen:
  - how it works;
  - your privacy (the photo is used once and deleted, results are saved on the device, the server copy is deleted after 24 hours);
  - the rules (18+, only yourself or people who agreed, unsafe content is blocked).
- **Navigation:** swipe or tap Next, with a page indicator. Skip on every page, and Get started on the last.
- **Seen once:** the "seen" record is kept on the device, so onboarding appears once per install and again after a reinstall. A launch that restores a saved session never shows it.
- **Profile:** a "How it works" row reopens the pages, and they return to the profile when finished.
- **Never in the way:** if the record can't be read, onboarding shows; if it can't be saved, the app carries on to sign-in.

Out of scope:
- per-account onboarding;
- illustrations or animations beyond icons;
- localisation;
- analytics on onboarding completion;
- the other optional v1 features (the ready banner, regenerate and variations, account extras, template management). Each will be its own change.

## Capabilities

### New Capabilities
- `onboarding`: covers the first-run pages, their content, skipping and finishing, reopening from the profile, and the on-device "seen" record.

### Modified Capabilities
- `account-ui`: "Require sign-in to use the app" now shows onboarding before sign-in on the first launch.

## Impact

- **App:**
  - new `features/onboarding/` (the pages, the screen, the seen-record store);
  - `router.dart` (an `/onboarding` route and the first-launch redirect);
  - `features/profile/profile_screen.dart` (the "How it works" row).
- **Server:** none.
- **Dependencies:** none. The record is a small file in the app support folder, through the existing `path_provider`.
