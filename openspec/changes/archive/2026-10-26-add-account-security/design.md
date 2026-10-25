# Design

## Context

See `proposal.md` for the motivation and `specs/` for the behaviour. The current code:

- **Account deletion** already re-authenticates with a password (checked with the login throttle), or a provider token issued within 5 minutes for a linked identity (`AuthService.delete_account`, `_verify_provider_confirmation`).
- **Sessions** are rows of `(token_hash, user_id, …)`, and the password reset deletes all of a user's sessions.
- **Email codes** use `CodePurpose` (`registration`, `password_reset`), keyed by address. `issue_code` enforces the per-address limits, and `consume_code` checks codes. Emails go out through the background `deliver` with the log or SMTP sender.
- **Identities** are `identities(provider, subject, user_id, email, apple_refresh_token)`, unique per `(provider, subject)` and per `(user_id, provider)`. Apple revocation goes through `services/apple_revocation.py`.
- **The schema** is at version 6, after content safety, with the mixins in `repos/user_store_*.py`.

## Goals / Non-Goals

**Goals:**
- One re-authentication helper shared by deletion, password, email and unlink, so the rules can't drift apart.
- Every change commits atomically under the store lock. A change never leaves an account with no way to sign in.

**Non-Goals:**
- New kinds of sessions or devices.
- Undoing an email change from the notification email.

## Decisions

### 1. A shared re-authentication helper
`AuthService.reauthenticate(user, reauth: Reauth)`, where `Reauth` is `{password?: str, provider?: "google"|"apple", token?: str, nonce?: str}`. It's extracted from `delete_account`'s existing logic, and `delete_account` now calls it too.

**After the round-1 review (account takeover, B1).** The first version accepted a provider token from any account, and linking needed no re-authentication. So a stolen session could link the attacker's own Google, then use it to change the password or email. The rules are now:
- **The form is chosen by the account, not by the request.** An account with a password must give the password; a provider form from it is refused. An account without a password must use a provider.
- **The provider must already be linked.** It's checked against the identities that existed **before** the request. A link request re-authenticates first, so the identity being linked can never vouch for itself.
- **Linking requires re-authentication** like every other change.
- **Account deletion gets the same rule:** a password account can no longer delete with a provider token. This modifies social-sign-in's "Confirm account deletion with a provider". Deletion keeps its own error codes (`invalid_password`, `invalid_provider_token`).

- **Alternative rejected: ignoring identities linked during the current session.** It needs session-to-identity bookkeeping, and it still lets a stolen session add a provider for later use.
- **A password:** checked against the throttle first (429 `too_many_attempts`), then verified. A failure records a throttle failure.
- **No password:** the provider path, as for deletion.

Every failure raises 403 `reauth_failed`. Deletion keeps its existing error code (`invalid_password` / `invalid_provider_token`) to avoid changing its spec, through a parameter that maps the error.

### 2. Password set or change
`POST /me/password {new_password, reauth}`:
1. Validate the length.
2. Re-authenticate.
3. Hash the new password outside the lock.
4. In one store transaction, update `password_hash` and delete the user's sessions except the current token's hash.
5. Schedule a "password changed" email to the account's email.
6. Answer 204.

### 3. Email change
- **New table** `pending_email_changes(user_id PRIMARY KEY REFERENCES users ON DELETE CASCADE, new_email, created_at)`, in schema version 7.
- **`POST /me/email {new_email, reauth}`:**
  1. Validate the format, and that the address differs from the current one.
  2. Re-authenticate.
  3. Check that the address isn't taken (409).
  4. Under the lock, call `issue_code(new_email, EMAIL_CHANGE)`, which applies the limits, and upsert the pending row.
  5. Schedule the code email to the new address.
  6. Answer 202. When limited: 429 with `Retry-After`.
- **`POST /me/email/confirm {code}`**, in one transaction:
  1. Read the pending row (missing gives `code_expired`).
  2. `consume_code(new_email, EMAIL_CHANGE)`: `wrong` gives `invalid_code`, `expired` gives `code_expired`.
  3. If the address is taken now, delete the pending row and answer 409.
  4. Otherwise update `users.email`, delete the pending row, and delete other sessions.
  5. After the commit, schedule the notification to the old address.

  The UNIQUE constraint on `users.email` is the final guard against a race. An `IntegrityError` maps to 409.
- **Linked identities and the login throttle:** linked identities keep working, because sign-in matches by `(provider, subject)` first. The login throttle is keyed by email, so the old email's lockout state is left as is.
- **Pruning:** pending changes older than 24 hours are pruned with the other email rows (the existing `_prune_email_rows` pass).

### 4. Linking and unlinking
- **Linking:**
  - The request body carries the new provider's token plus a `reauth` (Decision 1). `reauthenticate` runs first, against the identities linked before the request, and nothing is linked if it fails.
  - The new provider's token is then verified exactly as at sign-in, and a new store method, `link_identity(user_id, identity)`, inserts the row.
  - An existing `(provider, subject)` on another user gives `provider_in_use`. An existing row for `(user_id, provider)` gives `provider_already_linked`.
  - Apple linking does the code exchange and stores the refresh token, as at sign-in.
  - No email check: re-authentication proves it's the account's owner, and the new token proves they own the provider identity.
- **Unlinking:**
  1. Re-authenticate.
  2. In one transaction, check that another method remains (`password_hash != ''`, or another identity row). If none does, answer 409 `last_sign_in_method`.
  3. Read the Apple refresh token, if any, then delete the identity row.
  4. After the commit, revoke the Apple token in the background (logged, never fatal).
- **A provider-only account** that unlinks its last provider is refused, so it can never be locked out.

### 5. Notification emails
`email_code_service` gains two plain-text messages, sent with the same `deliver` path (background, fail-safe):
- `password_changed(to)`: "Your password was changed. If this wasn't you, reset your password now."
- `email_changed(to_old, new_email)`: "Your account email was changed to <new>. If this wasn't you, contact us right away at <SUPPORT_EMAIL>."
  - **No reset advice.** After the change, a reset to the old address finds no account, and a reset to the new one reaches the attacker. So the notice points to support only. This was changed after the round-1 review (S1).
  - **New setting `SUPPORT_EMAIL`** (default `""`). The server refuses to start when `SMTP_HOST` is set and `SUPPORT_EMAIL` is empty. In log mode an empty value is allowed, and the notice then says "contact support right away".

Neither message contains a code or a token. Both are logged as events without the addresses.

### 6. API errors
| Error | Status | Code |
|---|---|---|
| Re-authentication failed | 403 | `reauth_failed` |
| Throttled | 429 | `too_many_attempts` |
| Bad email or password format | 400 | `invalid_credentials_format` |
| New email same as current | 400 | `invalid_credentials_format` |
| Email taken | 409 | `email_taken` |
| Code wrong or expired | 400 | `invalid_code` / `code_expired` |
| Code send limited | 429 + `Retry-After` | `too_many_requests` |
| Identity on another account | 409 | `provider_in_use` |
| Provider already on this account | 409 | `provider_already_linked` |
| Would remove the last method | 409 | `last_sign_in_method` |
| Provider not linked (unlink) | 404 | `not_found` |
| Bad provider token (link) | 401 | `invalid_provider_token` |

### 7. App
- **Profile section:** `features/profile/security_section.dart`, reading `hasPassword`, `providers` and the provider availability providers.
- **Re-authentication:** `features/profile/reauth.dart` shows a password dialog when `hasPassword`, otherwise runs the linked provider's sign-in (Apple on iOS if linked, else Google). It returns a `Reauth`, or null on cancel.
- **Screens:**
  - `change_password_screen.dart`: new password, then re-auth, then the call.
  - `change_email_screen.dart`: new email, then re-auth, then `POST /me/email`, then the code screen. The code screen reuses the Confirm registration screen's layout pattern, with Resend using the draft values.
  - Link and unlink act directly from the rows.
- **After success:** `accountProvider.refresh()`, and a SnackBar with the success text.
- **Routes:** `/profile/password` and `/profile/email` (plus the code step).

Screen states:

| Screen | Loading | Empty / initial | Error | Success |
|---|---|---|---|---|
| Security section | Hidden rows while the account loads | Rows per `hasPassword` and `providers` | Account load failure: the section is hidden | Rows reflect the current state |
| Change or Set password | Submit spinner | Fields empty, Submit disabled, inline short-password message | `reauth_failed`: "Password is incorrect" (or "Couldn't confirm with Google/Apple"). `too_many_attempts`: lockout message. Values kept | Back to profile, SnackBar "Password changed. Other devices were signed out." |
| Change email | Submit spinner | New email field, Submit disabled until valid | `email_taken`, `invalid_credentials_format`, `reauth_failed`, 429. Values kept | Code screen for the new address |
| Email code | Confirm and Resend spinners | 6 digits needed, Resend countdown | `invalid_code`, `code_expired` (points to Resend), `email_taken` (back to the Change email screen) | Profile shows the new email, SnackBar "Email changed. Other devices were signed out." |
| Link or Unlink | Row spinner | Linked / Not linked | `provider_in_use`, `provider_already_linked`, `last_sign_in_method`, `reauth_failed`. Cancel: nothing | The row updates |

## Risks / Trade-offs

- **[What data is stored, and for how long]**
  - A pending email change (user id, new address, time): until it's confirmed, replaced, pruned after 24 hours, or deleted with the account.
  - The email-change code follows the existing 15-minute rule.
  - Password hashes and identities as today. No history of old emails is kept.
- **[Who can read it]** Only the account, through `/me`. The pending address is never returned by `/me`; the app holds it from its own request.
- **[What is logged]** Events with user ids only: `password_changed`, `email_change_requested`, `email_changed`, `provider_linked`, `provider_unlinked`, `reauth_failed`. Never passwords, codes, tokens or addresses.
- **[Existing data and migration]** Schema version 7 adds one table, idempotently. Existing accounts are unaffected. Rollback: the version-6 server ignores the table.
- **[Account takeover]**
  - Every change needs re-authentication, other sessions are revoked on password and email changes, and the old address is told about an email change.
  - Residual risk: someone who knows the password can change the email. The notification gives the real owner warning, but after the change, reset codes go to the new address. → Accepted. Two-factor authentication is a later option. The notification includes a support contact.
- **[Failure and retry]**
  - A notification email failing to send is logged and doesn't roll back the change.
  - A failed Apple revocation on unlink is logged.
  - A confirm that races a registration of the same address gets a 409 from the UNIQUE constraint.
- **[Background tasks when a call raises]** Notification and revocation tasks go through the existing safe wrappers, which log and swallow errors.
- **[Thread-safety of shared state]** Each change is one transaction under `SqliteUserStore._lock`, including the last-method check and delete for unlinking, and the code consume plus email update for confirming. The login throttle is already lock-protected.
- **[Delete-account refactor]** Moving deletion onto the shared helper could change its behaviour. → Its existing tests must pass unchanged, and its error codes are kept.

## Migration Plan

Deploy the server and app (the endpoints are additive). Schema version 7 is created on start. Rollback is the previous version.
