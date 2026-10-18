## MODIFIED Requirements

### Requirement: Delete an account

The system SHALL expose `DELETE /me` which, given a valid confirmation in the request body, permanently deletes the user, all of their sessions, all of their jobs, all generated images of those jobs, and all of their linked sign-in providers, and responds with HTTP 204. The confirmation SHALL be either the account's correct `password`, or a `provider` and a fresh provider `token` as described by the social-sign-in capability. With a wrong password or a rejected provider token the system SHALL respond with HTTP 403 and delete nothing.

#### Scenario: Deleting with the right password removes everything

- **WHEN** an authenticated user with a finished job calls `DELETE /me` with their password
- **THEN** the system responds with HTTP 204
- **AND** their token no longer authorizes requests
- **AND** logging in with their email returns 401
- **AND** their generated image is no longer served

#### Scenario: Wrong password deletes nothing

- **WHEN** an authenticated user calls `DELETE /me` with a wrong password
- **THEN** the system responds with HTTP 403 and the account remains usable

#### Scenario: Provider-only account deletes with a fresh provider token

- **WHEN** a user whose account has no password calls `DELETE /me` with `provider` `google` and a fresh Google token for their linked identity
- **THEN** the system responds with HTTP 204
- **AND** their token no longer authorizes requests
- **AND** signing in with that Google identity afterwards creates a new account

#### Scenario: Provider-only account cannot delete with a password

- **WHEN** a user whose account has no password calls `DELETE /me` with any `password`
- **THEN** the system responds with HTTP 403 and the account remains usable

### Requirement: Treat accounts from before verification as verified

Accounts that existed before email verification was introduced, and accounts that registered but never verified their email before registration codes were introduced, SHALL be treated as verified when the server first starts afterwards. They SHALL keep their password and be able to submit generations.

#### Scenario: Existing accounts are verified after the upgrade

- **WHEN** the server starts on a database whose accounts were created before email verification existed
- **THEN** each of those accounts can log in with its password and submit a generation

#### Scenario: Never-verified accounts are verified after the upgrade

- **WHEN** the server starts on a database holding an account that registered but never verified its email
- **THEN** that account can log in with its password and submit a generation

## ADDED Requirements

### Requirement: Start a registration

The system SHALL accept `POST /auth/register` with an `email`, a `password`, and an optional `referral_code`. It SHALL NOT create an account. It SHALL hold the registration as pending, email a registration code to that address as described by the email-codes capability, and respond with HTTP 202 and an empty body. Emails SHALL be matched case-insensitively and stored in lowercase. Passwords SHALL be between 8 and 128 characters. An unknown `referral_code` SHALL be rejected as described by the referrals capability. Registering the same email again SHALL replace the pending registration and its code. When a sending limit applies, the system SHALL respond with HTTP 429, error `too_many_requests`, and a `Retry-After` header, and keep the previous pending registration.

#### Scenario: Valid registration sends a code and creates no account

- **WHEN** a client posts a new email and a 12-character password to `POST /auth/register`
- **THEN** the system responds with HTTP 202 and no session
- **AND** a registration code is sent to that email
- **AND** logging in with that email and password returns 401

#### Scenario: Registering again replaces the pending registration

- **WHEN** a client registers an email, waits more than 60 seconds, and registers the same email with a different password
- **THEN** a new code is sent and the first code is rejected
- **AND** confirming with the new code creates the account with the second password

#### Scenario: Registering again too soon is refused

- **WHEN** a client registers the same email twice within 60 seconds
- **THEN** the second request gets HTTP 429, error `too_many_requests`, and a `Retry-After` header
- **AND** the first code is still accepted

#### Scenario: Duplicate email is rejected

- **WHEN** a client registers an email that already has an account, in any letter case
- **THEN** the system responds with HTTP 409 and error `email_taken`

#### Scenario: Invalid email or weak password is rejected

- **WHEN** a client registers with a malformed email or a password shorter than 8 characters
- **THEN** the system responds with HTTP 400 and error `invalid_credentials_format`
- **AND** no code is sent

#### Scenario: Unknown referral code is rejected

- **WHEN** a client registers with a valid email and password and a referral code that matches no account
- **THEN** the system responds with HTTP 400 and error `invalid_referral_code`
- **AND** no code is sent

### Requirement: Complete registration with the emailed code

The system SHALL expose `POST /auth/register/confirm`, without authentication, taking an `email`, a `code`, and the `password` the registration was made with. The system SHALL create the account only when the code matches the email's current registration code and the password matches the pending registration's password. It SHALL then create the account from the pending registration, with a verified email and the pending password and referral code, and respond with HTTP 201 and a body containing a session `token` and the user's `id` and `email`.

Failures:
- A wrong code SHALL get HTTP 400 with error `invalid_code`.
- A code that is expired, already used, invalidated, or was never issued for that email SHALL get HTTP 400 with error `code_expired`.
- A correct code with a password that does not match the pending registration SHALL get HTTP 409 with error `registration_changed`. The system SHALL then discard the pending registration and its code, and SHALL NOT create an account.
- When an account with that email was created after the registration was requested, the system SHALL respond with HTTP 409 and error `email_taken` and discard the pending registration.

#### Scenario: Correct code creates the account and signs in

- **WHEN** a client confirms a pending registration with the emailed code and the password it registered with
- **THEN** the system responds with HTTP 201 and a `token` that authorizes `GET /me`
- **AND** logging in with the registered email and password succeeds

#### Scenario: Someone else's re-registration cannot set the password

- **WHEN** a victim registers `una@example.com`, a third party registers the same email more than 60 seconds later with a different password, and the victim confirms with the newest emailed code and the victim's own password
- **THEN** the system responds with HTTP 409 and error `registration_changed`
- **AND** no account exists for that email
- **AND** confirming afterwards with the same code and the third party's password gets HTTP 400 with error `code_expired`

#### Scenario: Password is checked only after the code

- **WHEN** a client confirms with a wrong code and a wrong password
- **THEN** the system responds with HTTP 400 and error `invalid_code`
- **AND** the pending registration is kept

#### Scenario: Wrong code creates nothing

- **WHEN** a client confirms with a code that does not match
- **THEN** the system responds with HTTP 400 and error `invalid_code`
- **AND** no account exists for that email

#### Scenario: Expired code creates nothing

- **WHEN** a client confirms with the correct code after it has expired
- **THEN** the system responds with HTTP 400 and error `code_expired`
- **AND** no account exists for that email

#### Scenario: Email taken in the meantime

- **WHEN** a registration is pending for `ana@example.com`, an account for that email is then created through Google, and the client confirms the pending registration with its correct code
- **THEN** the system responds with HTTP 409 and error `email_taken`
- **AND** the Google-created account is unchanged

### Requirement: Reset a forgotten password with a code

The system SHALL expose `POST /auth/password-reset/confirm`, without authentication, taking `email`, `code`, and `new_password`. A new password outside 8 to 128 characters SHALL get HTTP 400 with error `invalid_credentials_format`, and no attempt SHALL be counted against the code. When the code matches the account's current reset code, the system SHALL make all of the following take effect together:
- set the new password;
- revoke every session of the account;
- clear the failed-login count for the email.

It SHALL then respond with HTTP 200 and a new session `token` and the user's `id` and `email`. Every other failure (unknown email, wrong code, expired or invalidated code) SHALL get HTTP 400 with error `invalid_code` and the same message.

#### Scenario: Correct code sets the password and signs in

- **WHEN** a client confirms a reset with the emailed code and a new 12-character password
- **THEN** the system responds with HTTP 200 and a `token`
- **AND** logging in with the new password succeeds and with the old password returns 401

#### Scenario: All earlier sessions are revoked

- **WHEN** a user holding two sessions completes a password reset
- **THEN** neither earlier token authorizes `GET /me`
- **AND** the token returned by the reset does

#### Scenario: Reset clears a login lockout

- **WHEN** an email is locked out after 5 failed logins and its owner completes a password reset
- **THEN** logging in with the new password succeeds immediately

#### Scenario: Failures are indistinguishable

- **WHEN** one client confirms with an unknown email, another with a wrong code, and another with an expired code
- **THEN** all three receive HTTP 400 with error `invalid_code` and the same message
- **AND** no password changes

#### Scenario: Weak new password does not use up an attempt

- **WHEN** a client confirms 5 times with the correct code and a 5-character new password
- **AND** then confirms with the correct code and a valid new password
- **THEN** each of the first 5 requests gets HTTP 400 with error `invalid_credentials_format`
- **AND** the last request succeeds

### Requirement: Accounts without a password

An account created through a sign-in provider SHALL have no password. Logging in to it with `POST /auth/login` SHALL fail with HTTP 401 and error `invalid_credentials`, exactly as for a wrong password. Completing a password reset on such an account SHALL give it a password, after which password login SHALL work.

#### Scenario: Password login on a provider-only account fails like a wrong password

- **WHEN** a client logs in with the email of an account created through Google and any password
- **THEN** the system responds with HTTP 401 and error `invalid_credentials` with the same message as a wrong password

#### Scenario: Password reset adds a password

- **WHEN** the owner of an account created through Google completes a password reset with a new password
- **THEN** logging in with that email and the new password succeeds
- **AND** signing in with Google still reaches the same account

### Requirement: Report sign-in methods

`GET /me` SHALL include `providers`, the list of sign-in providers linked to the account (`google`, `apple`), and `has_password`, whether the account has a password.

#### Scenario: Provider-only account

- **WHEN** a user whose account was created through Google calls `GET /me`
- **THEN** the response contains `providers` equal to `["google"]` and `has_password` false

#### Scenario: Password account

- **WHEN** a user who registered with email and password and never used a provider calls `GET /me`
- **THEN** the response contains an empty `providers` list and `has_password` true

## REMOVED Requirements

### Requirement: Register an account
**Reason**: Registration no longer creates an account or a session until the emailed code is confirmed.
**Migration**: Use "Start a registration" followed by "Complete registration with the emailed code".

### Requirement: Reset the password with a code
**Reason**: Every account is verified, so a reset no longer verifies the email and its response no longer carries `email_verified`.
**Migration**: Replaced by "Reset a forgotten password with a code": same endpoint and request, and the response drops `email_verified`.

### Requirement: Start new accounts with an unverified email
**Reason**: Accounts are now created only after the emailed code is confirmed, so an unverified account never exists. This also closes the hole where someone could register another person's email and keep access after the real owner linked Google or Apple.
**Migration**: Clients call `POST /auth/register` and then `POST /auth/register/confirm`. Existing unverified accounts are marked verified on upgrade.

### Requirement: Report email verification status
**Reason**: Every account has a verified email, so `email_verified` carries no information.
**Migration**: Register-confirm, login, password-reset confirm and `GET /me` responses no longer contain `email_verified`. Clients stop reading it.

### Requirement: Verify the email with a code
**Reason**: Replaced by "Complete registration with the emailed code". There is no account to verify after creation.
**Migration**: Use `POST /auth/register/confirm`. `POST /auth/verify-email` is removed.

### Requirement: Resend the verification code
**Reason**: Registering the same email again re-sends the registration code under the same limits.
**Migration**: Call `POST /auth/register` again. `POST /auth/verify-email/resend` is removed.
