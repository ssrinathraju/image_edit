# user-auth Specification

## Purpose
Identifies who is calling the API. Provides email and password accounts, revocable login sessions, and account deletion, so that other capabilities can attribute work and data to a specific user.

## Requirements

### Requirement: Register an account

The system SHALL accept `POST /auth/register` with an `email`, a `password`, and an optional `referral_code`, create the account, and respond with HTTP 201 and a body containing a session `token` and the user's `id` and `email`. Emails SHALL be matched case-insensitively and stored in lowercase. Passwords SHALL be between 8 and 128 characters. An unknown `referral_code` SHALL be rejected as described by the referrals capability.

#### Scenario: Valid registration creates an account and a session

- **WHEN** a client posts a new email and a 12-character password to `POST /auth/register`
- **THEN** the system responds with HTTP 201 and a body containing `token`, `id`, and `email`
- **AND** that token authorizes `GET /me`

#### Scenario: Duplicate email is rejected

- **WHEN** a client registers an email that already has an account, in any letter case
- **THEN** the system responds with HTTP 409 and error `email_taken`

#### Scenario: Invalid email or weak password is rejected

- **WHEN** a client registers with a malformed email or a password shorter than 8 characters
- **THEN** the system responds with HTTP 400 and error `invalid_credentials_format`
- **AND** no account is created

#### Scenario: Unknown referral code is rejected

- **WHEN** a client registers with a valid email and password and a referral code that matches no account
- **THEN** the system responds with HTTP 400 and error `invalid_referral_code`
- **AND** no account is created

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

The system SHALL expose `DELETE /me` which, given the correct `password` in the request body, permanently deletes the user, all of their sessions, all of their jobs, and all generated images of those jobs, and responds with HTTP 204. With a wrong password the system SHALL respond with HTTP 403 and delete nothing.

#### Scenario: Deleting with the right password removes everything

- **WHEN** an authenticated user with a finished job calls `DELETE /me` with their password
- **THEN** the system responds with HTTP 204
- **AND** their token no longer authorizes requests
- **AND** logging in with their email returns 401
- **AND** their generated image is no longer served

#### Scenario: Wrong password deletes nothing

- **WHEN** an authenticated user calls `DELETE /me` with a wrong password
- **THEN** the system responds with HTTP 403 and the account remains usable

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
