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

## ADDED Requirements

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

