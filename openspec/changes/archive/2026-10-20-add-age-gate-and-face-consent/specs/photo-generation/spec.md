## ADDED Requirements

### Requirement: Require a confirmed age and current consent to generate

The system SHALL refuse `POST /generations` from an account whose age is not confirmed with HTTP 403 and error `age_not_confirmed`. It SHALL refuse one whose accepted consent version is not the current version with HTTP 403 and error `consent_required`. Both checks SHALL happen before the request's faces, prompt or template are validated, and before any generation is counted. A refused request SHALL NOT create a job, store an uploaded face, or count against the account's generations. When both apply, `age_not_confirmed` SHALL be returned.

#### Scenario: Unconfirmed age is refused first

- **WHEN** an account without a confirmed age and without consent submits a valid generation request
- **THEN** the system responds with HTTP 403 and error `age_not_confirmed`
- **AND** no job is created and the remaining generations are unchanged

#### Scenario: Missing consent is refused

- **WHEN** an account with a confirmed age that never accepted consent submits a generation
- **THEN** the system responds with HTTP 403 and error `consent_required`
- **AND** no uploaded face is stored

#### Scenario: Outdated consent is refused

- **WHEN** the current version is "2" and the account accepted version "1"
- **THEN** a submission gets HTTP 403 and error `consent_required`

#### Scenario: Checks come before input validation

- **WHEN** an account without consent submits a request with no faces and no prompt
- **THEN** the system responds with HTTP 403 and error `consent_required`

#### Scenario: Confirmed and consenting account can generate

- **WHEN** an account with a confirmed age and the current consent submits a valid request
- **THEN** the system responds with HTTP 202 and a job id
