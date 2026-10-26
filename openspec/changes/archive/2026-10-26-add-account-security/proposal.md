# Proposal

## Why

Once signed in, a user can't change their password (only reset it while signed out), can't change their email, and can't link Google or Apple to an account they made with a password, or remove one. These are table stakes for an app that holds people's face images. A provider-only account also has no way to add a password except through the reset flow.

## What Changes

- **Re-authentication** for every change: the current password, or a fresh Google or Apple sign-in for accounts without a password. This is the same rule account deletion already uses. Wrong passwords count toward the existing login lockout.
- **`POST /me/password`:** set or change the password. Other sessions are signed out (this device stays signed in), and the account's address gets a "password changed" email.
- **`POST /me/email` then `POST /me/email/confirm`:**
  - a code goes to the **new** address;
  - confirming changes the email and signs out other sessions;
  - the **old** address gets a "your email was changed" email with the new address and advice to reset the password if it wasn't them.
- **`POST /me/providers/{google|apple}`:** link a provider identity to the signed-in account.
- **`DELETE /me/providers/{provider}`:** unlink one, but never the last way to sign in (409 `last_sign_in_method`). Unlinking Apple revokes its token.
- **`email-codes`:** a third purpose, email change, counted in the same per-address limits.
- **App:** a profile section, "Sign-in & security", with Change or Set password, Change email (with a code screen), and Google and Apple rows (Apple on iOS only) with Link and Unlink. It includes re-authentication prompts and clear errors.

Out of scope:
- two-factor authentication;
- a list of active sessions;
- "sign out everywhere";
- changing the email of a sign-in provider's own account;
- merging two existing accounts.

## Capabilities

### New Capabilities
- `account-security`: covers re-authentication, setting and changing the password, changing the email with a code, linking and unlinking providers, notification emails, and keeping these changes private.

### Modified Capabilities
- `email-codes`: an email-change purpose, and the sending limits count all purposes together.
- `account-ui`: new requirements for the "Sign-in & security" profile section and its screens.

## Impact

- **Server:**
  - new `services/account_security_service.py`;
  - `api/me_security.py` (or additions in `api/auth.py`);
  - `repos/user_store_*` (a pending-email-change table, schema version 7; revoking other sessions; unlinking an identity);
  - `core/email_codes.py` (the new purpose);
  - `services/email_code_service.py` (the notification emails);
  - `schemas/user.py`;
  - `server/README.md`.
- **App:**
  - `core/api_client.dart` and `core/api_errors.dart`;
  - `features/profile/` (the security section, password and email screens, a re-authentication helper);
  - `router.dart`.
- **Data:** a `pending_email_changes` table. No change to existing rows.
