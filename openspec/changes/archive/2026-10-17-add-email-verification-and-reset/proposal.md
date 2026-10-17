# Proposal

## Why

Accounts today are an email and a password that nobody has proven they own. Two problems follow. A user who forgets their password has no way back into the account. Anyone can register throwaway addresses to get free daily generations and referral bonuses, which is the biggest risk recorded in the plans-and-referrals design and in `todo.md`. Proving email ownership with a short code fixes both, and it has to come before social sign-in and before any public launch.

## What Changes

- The server can send email. Plain-text email goes over SMTP when SMTP is configured. Otherwise the message, including the code, is written to the server log, so development and tests need no mail account.
- The system issues one-time 6-digit email codes, each for one account and one purpose. A code is valid for 15 minutes and is invalidated after 5 wrong tries. At most one email per account every 60 seconds and 5 per hour are sent. Codes are stored hashed.
- New accounts start with an **unverified** email. Registration still signs the user in, and it emails a verification code.
- New endpoints:
  - `POST /auth/verify-email` checks the code.
  - `POST /auth/verify-email/resend` sends a new code.
  - `POST /auth/password-reset/request` always answers 202, whether or not the email has an account.
  - `POST /auth/password-reset/confirm` sets a new password, signs out every session, and returns a fresh one.
- `email_verified` is added to the register, login and `GET /me` responses.
- **BREAKING (behaviour):** `POST /generations` refuses unverified accounts with 403 `email_not_verified`.
- **BREAKING (behaviour):** referral bonuses are paid when the new account verifies its email, not when it registers. An account that never verifies earns nothing for itself or its referrer.
- Accounts that already exist when this ships are treated as verified.
- In the app:
  - After registration the app opens a **Verify email** screen. It has a code field, Resend with a 60-second countdown, and a Later option.
  - Home shows a "Verify your email" banner while the email is unverified. A generation refused for an unverified email opens the Verify screen.
  - The sign-in screen gets **Forgot password?**, which leads to an email screen and then a code and new password screen.

Out of scope:
- Social sign-in. This is the next change.
- Changing the email address.
- Changing the password while signed in.
- Links in emails and deep links.
- HTML email templates.
- Choosing or configuring a production mail provider.
- Per-IP rate limiting.
- Deleting accounts that never verify.

## Capabilities

### New Capabilities
- `email-codes`: covers the one-time codes sent by email to prove that a user controls their address. It owns how codes are issued, how long they are valid, wrong-attempt and sending limits, delivery (SMTP or log), and how codes are protected at rest and in logs.

### Modified Capabilities
- `user-auth`:
  - New accounts start unverified and are emailed a code.
  - Responses report `email_verified`.
  - New verify, resend, password-reset request and password-reset confirm endpoints.
- `referrals`: "Reward both accounts" now pays when the new account verifies its email instead of at registration.
- `photo-generation`: submitting a generation requires a verified email.
- `account-ui`:
  - Registration leads to the Verify email screen.
  - New Verify email screen.
  - Home banner for unverified accounts.
  - The `email_not_verified` refusal opens verification.
  - New Forgot password flow.

## Impact

- **Server code:**
  - `configs/settings.py`: SMTP and email-code settings.
  - New `core/email_sender.py` interface, with SMTP and log implementations under `services/email/`.
  - New `services/email_code_service.py`.
  - `repos/user_store.py`: new column `email_verified`, new tables for codes and sends, migration to schema version 3, and referral payment moved to verification.
  - `services/auth_service.py`, `api/auth.py`, `schemas/user.py`, `services/generation_service.py` and `main.py`.
- **API:** four new endpoints, one new field on three responses, and new error codes `email_not_verified`, `invalid_code`, `code_expired`, `already_verified` and `too_many_requests`.
- **Data:** `app.db` is migrated in place on first start. Existing users become verified.
- **App code:**
  - `schemas/session.dart` and `schemas/account.dart`.
  - `core/api_client.dart` and `core/api_errors.dart`.
  - `router.dart`.
  - New screens under `features/auth/`.
  - `home_screen.dart` and `features/common/submit_flow.dart`.
- **Tests:** existing server tests that register through the API and then generate need a helper that verifies the account first.
- **Dependencies:** none new. SMTP uses Python's standard library `smtplib`.
- **Docs:** `server/README.md` gains the SMTP settings, the new endpoints and their errors, and how to read codes from the log in development.
