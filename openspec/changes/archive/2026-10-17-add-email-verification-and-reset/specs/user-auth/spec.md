## ADDED Requirements

### Requirement: Start new accounts with an unverified email

The system SHALL create every account registered through `POST /auth/register` with an unverified email and SHALL email it a verification code as described by the email-codes capability. Registration SHALL still return a session as before.

#### Scenario: Registration sends a verification code

- **WHEN** a client registers a new email
- **THEN** the system responds with HTTP 201 and a session `token`
- **AND** a verification code is sent to that email
- **AND** `GET /me` with that token reports `email_verified` as false

### Requirement: Treat accounts from before verification as verified

Accounts that existed before email verification was introduced SHALL be treated as verified when the server first starts afterwards.

#### Scenario: Existing accounts are verified after the upgrade

- **WHEN** the server starts on a database whose accounts were created before email verification existed
- **THEN** `GET /me` for each of those accounts reports `email_verified` as true

### Requirement: Report email verification status

The responses of `POST /auth/register`, `POST /auth/login`, and `GET /me` SHALL include a boolean `email_verified` for the account.

#### Scenario: Login reports the status

- **WHEN** an unverified account logs in
- **THEN** the response contains `email_verified` set to false

#### Scenario: Verified account reports true

- **WHEN** a verified account calls `GET /me`
- **THEN** the response contains `email_verified` set to true

### Requirement: Verify the email with a code

The system SHALL expose `POST /auth/verify-email`, for authenticated requests, taking a `code`. When the code matches the account's current verification code, the system SHALL mark the email verified and respond with HTTP 200 and `email_verified` set to true. A wrong code SHALL get HTTP 400 with error `invalid_code`. A code that is expired, already used, invalidated, or never issued SHALL get HTTP 400 with error `code_expired`. An already verified account SHALL get HTTP 409 with error `already_verified`.

#### Scenario: Correct code verifies the email

- **WHEN** an unverified user posts the emailed code to `POST /auth/verify-email`
- **THEN** the system responds with HTTP 200 and `email_verified` true
- **AND** `GET /me` reports `email_verified` as true

#### Scenario: Wrong code is rejected

- **WHEN** an unverified user posts a code that does not match
- **THEN** the system responds with HTTP 400 and error `invalid_code`
- **AND** the email stays unverified

#### Scenario: Expired code is rejected

- **WHEN** an unverified user posts the correct code after it has expired
- **THEN** the system responds with HTTP 400 and error `code_expired`

#### Scenario: Already verified account is told so

- **WHEN** a verified user posts any code
- **THEN** the system responds with HTTP 409 and error `already_verified`

#### Scenario: Unauthenticated request is rejected

- **WHEN** a client posts a code with no valid session
- **THEN** the system responds with HTTP 401 and error `unauthorized`

### Requirement: Resend the verification code

The system SHALL expose `POST /auth/verify-email/resend`, for authenticated requests. For an unverified account within the sending limits it SHALL issue and email a new verification code and respond with HTTP 202. When a sending limit applies it SHALL respond with HTTP 429, error `too_many_requests`, and a `Retry-After` header giving the seconds until a code can next be sent. An already verified account SHALL get HTTP 409 with error `already_verified`.

#### Scenario: Resend issues a new code

- **WHEN** an unverified user calls resend more than 60 seconds after the last code email
- **THEN** the system responds with HTTP 202
- **AND** a new code is sent and the previous one is rejected

#### Scenario: Resend too soon is refused

- **WHEN** an unverified user calls resend 20 seconds after registering
- **THEN** the system responds with HTTP 429, error `too_many_requests`, and a `Retry-After` header of at most 40

#### Scenario: Verified account cannot resend

- **WHEN** a verified user calls resend
- **THEN** the system responds with HTTP 409 and error `already_verified`

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

### Requirement: Reset the password with a code

The system SHALL expose `POST /auth/password-reset/confirm`, without authentication, taking `email`, `code`, and `new_password`. A new password outside 8 to 128 characters SHALL get HTTP 400 with error `invalid_credentials_format`, and no attempt SHALL be counted against the code. When the code matches the account's current reset code, the system SHALL make all of the following take effect together:
- set the new password;
- revoke every session of the account;
- mark the email verified;
- clear the failed-login count for the email.

It SHALL then respond with HTTP 200 and a new session `token`, the user's `id` and `email`, and `email_verified` true. Every other failure (unknown email, wrong code, expired or invalidated code) SHALL get HTTP 400 with error `invalid_code` and the same message.

#### Scenario: Correct code sets the password and signs in

- **WHEN** a client confirms a reset with the emailed code and a new 12-character password
- **THEN** the system responds with HTTP 200 and a `token`
- **AND** logging in with the new password succeeds and with the old password returns 401

#### Scenario: All earlier sessions are revoked

- **WHEN** a user holding two sessions completes a password reset
- **THEN** neither earlier token authorizes `GET /me`
- **AND** the token returned by the reset does

#### Scenario: Reset verifies the email

- **WHEN** an unverified user completes a password reset
- **THEN** `GET /me` with the returned token reports `email_verified` as true

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
