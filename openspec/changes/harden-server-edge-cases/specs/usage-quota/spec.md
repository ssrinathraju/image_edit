## ADDED Requirements

### Requirement: Refuse an exhausted account before reading uploads

When an account has no generations left (daily allowance and bonus credits both used), the system SHALL answer `POST /generations` with HTTP 429 and error `quota_exceeded` before reading or decoding any uploaded image. An account with generations left SHALL still have its generation reserved only after the request has passed validation, so that an invalid request uses nothing and concurrent requests cannot exceed the limit.

#### Scenario: Exhausted account is refused without reading the upload

- **WHEN** a free account that has used its 3 generations and has no bonus credits submits a request with a reference image
- **THEN** the system responds with HTTP 429 and error `quota_exceeded`
- **AND** the uploaded image is not read or decoded

#### Scenario: Invalid request still uses nothing

- **WHEN** a free account with 1 generation left submits a request with an invalid image
- **THEN** the system responds with HTTP 400
- **AND** the account still has 1 generation left

#### Scenario: Last generation cannot be taken twice

- **WHEN** a free account with 1 generation left submits two valid requests at the same time
- **THEN** exactly one is accepted and the other receives HTTP 429

### Requirement: Treat an unknown plan as free

When an account's stored plan is neither `free` nor `premium`, the system SHALL treat it as `free` for the daily limit and SHALL report it as `free` in `GET /me`, and SHALL log a warning naming the account id and not the stored value. No request SHALL fail because of an unknown plan.

#### Scenario: Corrupted plan falls back to free

- **WHEN** an account's stored plan is `gold`
- **THEN** `GET /me` responds with HTTP 200 and reports plan `free` with the free daily limit
- **AND** submitting a generation uses the free daily limit
- **AND** a warning is logged with the account id
