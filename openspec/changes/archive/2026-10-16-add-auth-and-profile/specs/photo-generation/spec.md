# Spec Delta

## REMOVED Requirements

### Requirement: Expose endpoints without authentication (transitional)

**Reason**: Authentication is now implemented. The transitional exception existed only until accounts were available.
**Migration**: Clients must obtain a session through `POST /auth/register` or `POST /auth/login` and send it as `Authorization: Bearer <token>`. See "Require authentication for generation endpoints".

## ADDED Requirements

### Requirement: Require authentication for generation endpoints

The system SHALL require an authenticated session for `POST /generations` and `GET /generations/{job_id}`, and SHALL respond with HTTP 401 and error `unauthorized` when the request has no valid session. No job SHALL be created for an unauthenticated request.

#### Scenario: Unauthenticated submission is rejected

- **WHEN** a client posts a valid request to `POST /generations` with no `Authorization` header
- **THEN** the system responds with HTTP 401
- **AND** no job is created

#### Scenario: Unauthenticated status request is rejected

- **WHEN** a client calls `GET /generations/{job_id}` with no `Authorization` header
- **THEN** the system responds with HTTP 401

### Requirement: Scope jobs to their owner

The system SHALL associate each job with the user who submitted it and SHALL make the job and its status visible only to that user. Requesting a job that exists but belongs to another user SHALL be indistinguishable from requesting an unknown job: HTTP 404.

#### Scenario: Owner can read their job

- **WHEN** a user submits a job and then calls `GET /generations/{job_id}` with their own session
- **THEN** the system responds with HTTP 200 and the job's status

#### Scenario: Another user cannot read the job

- **WHEN** a second authenticated user calls `GET /generations/{job_id}` for the first user's job
- **THEN** the system responds with HTTP 404
