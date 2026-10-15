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
