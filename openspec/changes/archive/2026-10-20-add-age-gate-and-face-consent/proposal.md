# Proposal

## Why

The app takes people's face photos and produces realistic edits of them. That makes it an adult-rated service in the app stores, and face photos count as biometric data under GDPR and US laws such as Illinois' BIPA. Today nothing checks a user's age, and nobody agrees to how their face photos are handled. Both are launch blockers, and they are easier to put in place before face conditioning makes the outputs realistic. Content safety (prompt and image screening, reporting) is the next, separate change.

## What Changes

- **Age gate (18+).** Registration requires a date of birth. A Google or Apple sign-in that would create a new account answers `age_required` until the app sends a date of birth. Under 18 is refused, and no account or pending registration is created. Existing accounts must confirm their age (`POST /me/age`) before generating. The date of birth itself is never stored, only that the age was confirmed and when.
- **Face-photo consent.**
  - A configured consent version (`"1"`).
  - `POST /me/consent` records acceptance of the current version, and `DELETE /me/consent` withdraws it.
  - `GET /me` reports `age_confirmed` and the consent state.
  - Raising the version asks everyone again.
- **Generation gate.** `POST /generations` answers 403 `age_not_confirmed` or `consent_required` before validating or counting anything.
- **App:**
  - **Registration:** a date-of-birth picker on the register screen.
  - **Provider sign-up:** a date-of-birth screen when the server answers `age_required`.
  - **Existing accounts:** a Confirm your age screen before home if the age isn't confirmed. Under 18 shows a blocked screen with Delete account and Sign out.
  - **Consent:** a consent screen before the first submission with a photo, and after a version change. It explains how photos and results are handled and links to the privacy policy.
  - **Profile:** a Face photo consent row with Withdraw.

Out of scope:
- content safety (the next change);
- ID or third-party age verification;
- parental consent;
- regional age rules;
- a history of past consent changes;
- the final legal wording of the consent text (the change ships placeholder copy for the user to have reviewed).

## Capabilities

### New Capabilities
- `age-and-consent`: covers the date-of-birth check and 18+ rule, never storing the date of birth, confirming an existing account's age, recording and withdrawing face-photo consent per version, the upgrade treatment of existing accounts, and reporting both on `/me`.

### Modified Capabilities
- `user-auth`: "Start a registration" requires a `date_of_birth` that passes the age check.
- `social-sign-in`: "Find, link, or create the account" creates a new account only with an adult `date_of_birth`, and otherwise answers `age_required` or `under_age`.
- `photo-generation`: new requirement that generating needs a confirmed age and the current consent.
- `account-ui`:
  - "Register with email and password" gains the date of birth;
  - new requirements for the provider date-of-birth screen, Confirm your age, the consent screen, and the profile's consent row.

## Impact

- **Server:**
  - `configs/settings.py` (`CONSENT_VERSION`);
  - new `core/age.py` (the pure age check);
  - `repos/user_store.py`: schema version 5, with `age_confirmed_at`, `consent_version` and `consent_at` columns;
  - `services/auth_service.py`, `services/generation_service.py`, `api/auth.py`, `schemas/user.py`;
  - `server/README.md`.
- **API:**
  - a new `date_of_birth` field on register and the provider endpoints;
  - new endpoints `POST /me/age`, `POST /me/consent` and `DELETE /me/consent`;
  - new `/me` fields;
  - new error codes `invalid_date_of_birth`, `under_age`, `age_required`, `age_already_confirmed`, `consent_version_mismatch`, `age_not_confirmed` and `consent_required`.
- **Data:** `app.db` is migrated in place. Existing accounts get no confirmed age and no consent, so they are asked on next use.
- **App:** `register_screen.dart`, `provider_buttons.dart`, new screens under `features/consent/`, `router.dart`, `features/common/submit_flow.dart`, `profile_screen.dart`, `core/api_client.dart`, `core/api_errors.dart`, and `schemas/account.dart`.
