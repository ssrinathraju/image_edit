## ADDED Requirements

### Requirement: Require a verified email to generate

The system SHALL refuse `POST /generations` from an account whose email is not verified with HTTP 403 and error `email_not_verified`, whatever else the request contains. A refused request SHALL NOT create a job and SHALL NOT count against the account's generations. Reading the status and image of existing jobs SHALL NOT require a verified email.

#### Scenario: Unverified account cannot submit

- **WHEN** an unverified user submits a valid generation request
- **THEN** the system responds with HTTP 403 and error `email_not_verified`
- **AND** no job is created and the user's remaining generations are unchanged

#### Scenario: Verification is checked before input validation

- **WHEN** an unverified user submits a request with no faces and no prompt
- **THEN** the system responds with HTTP 403 and error `email_not_verified`

#### Scenario: Verified account can submit

- **WHEN** a user verifies their email and then submits a valid generation request
- **THEN** the system responds with HTTP 202 and a job id
