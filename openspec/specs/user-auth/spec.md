# user-auth Specification

## Purpose
Identifies who is calling the API. Provides email and password accounts, revocable login sessions, and account deletion, so that other capabilities can attribute work and data to a specific user.

## Requirements

### Requirement: Store passwords as salted hashes

The system SHALL store only a salted, slow hash of each password and SHALL NOT store, log, or return the plain password or its hash in any response.

#### Scenario: Password is not recoverable from storage

- **WHEN** an account has been registered with password `correct horse battery`
- **THEN** the stored user record does not contain that password text
- **AND** two accounts registered with the same password have different stored hashes

### Requirement: Log in

The system SHALL accept `POST /auth/login` with an `email` and `password` and, when they match an account, respond with HTTP 200 and a new session `token` plus the user's `id` and `email`. When either is wrong the system SHALL respond with HTTP 401 and the same error `invalid_credentials` for both an unknown email and a wrong password.

#### Scenario: Correct credentials return a session

- **WHEN** a client posts a registered email and its password to `POST /auth/login`
- **THEN** the system responds with HTTP 200 and a `token`

#### Scenario: Wrong password and unknown email are indistinguishable

- **WHEN** a client logs in with a registered email and a wrong password
- **AND** another client logs in with an email that has no account
- **THEN** both receive HTTP 401 with error `invalid_credentials` and the same message

### Requirement: Throttle repeated failed logins

The system SHALL reject further login attempts for an email with HTTP 429 and error `too_many_attempts` after 5 consecutive failed attempts, until 15 minutes have passed since the latest failure. A successful login SHALL reset the count.

#### Scenario: Sixth attempt is throttled

- **WHEN** a client fails to log in 5 times in a row for one email
- **AND** then submits the correct password
- **THEN** the system responds with HTTP 429 and error `too_many_attempts`

#### Scenario: Success resets the failure count

- **WHEN** a client fails twice and then logs in with the correct password
- **THEN** the login succeeds
- **AND** the next failed attempt counts as the first

### Requirement: Authenticate requests with a bearer token

The system SHALL treat a request as authenticated only when it carries `Authorization: Bearer <token>` for a session that exists, has not expired, and has not been revoked. Sessions SHALL expire 30 days after they are issued. Any other request to a protected endpoint SHALL receive HTTP 401 with error `unauthorized`.

#### Scenario: Missing or invalid token is rejected

- **WHEN** a client calls `GET /me` with no `Authorization` header, or with an unknown token
- **THEN** the system responds with HTTP 401 and error `unauthorized`

#### Scenario: Expired session is rejected

- **WHEN** a client calls `GET /me` with a token issued more than 30 days ago
- **THEN** the system responds with HTTP 401 and error `unauthorized`

### Requirement: Return the current user

The system SHALL expose `GET /me` which returns the authenticated user's `id`, `email`, and `created_at`, together with the account's plan, usage, and referral details, and SHALL NOT return any password material.

#### Scenario: Current user is returned

- **WHEN** an authenticated client calls `GET /me`
- **THEN** the system responds with HTTP 200 and the user's `id`, `email`, and `created_at`

#### Scenario: Plan, usage, and referral details are included

- **WHEN** an authenticated client calls `GET /me`
- **THEN** the response also contains the account's `plan`, its usage figures, and its referral code and progress

### Requirement: Log out

The system SHALL expose `POST /auth/logout` which revokes the session used for the request and responds with HTTP 204. A revoked token SHALL NOT authorize any further request. Other sessions of the same user SHALL remain valid.

#### Scenario: Logged-out token stops working

- **WHEN** an authenticated client calls `POST /auth/logout`
- **AND** then calls `GET /me` with the same token
- **THEN** the logout responds with HTTP 204 and the second call responds with HTTP 401

#### Scenario: Other sessions survive

- **WHEN** a user holds two sessions and logs one of them out
- **THEN** the other session's token still authorizes `GET /me`

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

### Requirement: Request a password reset

The system SHALL expose `POST /auth/password-reset/request`, without authentication, taking an `email`. A malformed email SHALL get HTTP 400 with error `invalid_credentials_format`. For any well-formed email the system SHALL respond with HTTP 202 and an identical body, whether or not an account exists. When an account exists and the sending limits allow, it SHALL issue and email a password reset code. Otherwise it SHALL send nothing.

#### Scenario: Registered email receives a code

- **WHEN** a client requests a reset for a registered email in different letter case
- **THEN** the system responds with HTTP 202
- **AND** a password reset code is sent to that account's email

#### Scenario: Unknown email looks the same

- **WHEN** a client requests a reset for an email with no account
- **THEN** the system responds with HTTP 202 and the same body as for a registered email
- **AND** no email is sent

#### Scenario: Limited request looks the same

- **WHEN** a client requests a reset for a registered email that was sent a code 10 seconds earlier
- **THEN** the system responds with HTTP 202 and the same body
- **AND** no email is sent

### Requirement: Start a registration

The system SHALL accept `POST /auth/register` with an `email`, a `password`, a `date_of_birth`, and an optional `referral_code`. The `date_of_birth` SHALL be checked as described by the age-and-consent capability before anything else is stored or sent. It SHALL NOT create an account. It SHALL hold the registration as pending, email a registration code to that address as described by the email-codes capability, and respond with HTTP 202 and an empty body. Emails SHALL be matched case-insensitively and stored in lowercase. Passwords SHALL be between 8 and 128 characters. An unknown `referral_code` SHALL be rejected as described by the referrals capability. Registering the same email again SHALL replace the pending registration and its code. When a sending limit applies, the system SHALL respond with HTTP 429, error `too_many_requests`, and a `Retry-After` header, and keep the previous pending registration.

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

#### Scenario: Under-18 registration is refused

- **WHEN** a client registers with a date of birth 17 years and 364 days before today
- **THEN** the system responds with HTTP 400 and error `under_age`
- **AND** no code is sent and no pending registration exists for that email

#### Scenario: Missing date of birth is refused

- **WHEN** a client registers without a `date_of_birth`
- **THEN** the system responds with an error and no code is sent

#### Scenario: Confirmed registration is age-confirmed

- **WHEN** a client registers with a date of birth exactly 18 years before today and confirms the emailed code
- **THEN** `GET /me` for the new account reports `age_confirmed` true

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
