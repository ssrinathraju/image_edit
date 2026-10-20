# usage-quota Specification

## Purpose
Limits how many images an account can generate, so GPU cost is bounded and plans mean something. Defines plans, the daily allowance and when it resets, one-time bonus credits, and what happens to the count when a generation fails.

## Requirements

### Requirement: Assign each account a plan

The system SHALL keep exactly one plan on every account, either `free` or `premium`, and SHALL create new accounts on `free`. The plan SHALL only be changed by the operator through server-side tooling, never by a client request.

#### Scenario: New accounts start on the free plan

- **WHEN** a user registers
- **THEN** their plan is `free`

#### Scenario: Clients cannot change the plan

- **WHEN** an authenticated client sends a plan value to any endpoint
- **THEN** the account's plan is unchanged

### Requirement: Limit generations per day by plan

The system SHALL allow each account a daily allowance of generations determined by its plan: 3 for `free` and 30 for `premium`, both configurable. The allowance SHALL reset at 00:00 UTC. The count SHALL be stored durably, so restarting the server does not reset it.

#### Scenario: Free account can generate up to its allowance

- **WHEN** a free account submits 3 valid generations on the same UTC day
- **THEN** all three are accepted with HTTP 202

#### Scenario: Fourth free generation is refused

- **WHEN** a free account with no bonus credits has used its 3 generations today and submits another valid request
- **THEN** the system responds with HTTP 429 and error `quota_exceeded`
- **AND** no job is created

#### Scenario: Premium allowance is larger

- **WHEN** a premium account has used 3 generations today and submits another valid request
- **THEN** the request is accepted

#### Scenario: Allowance resets at midnight UTC

- **WHEN** an account used its full allowance before 00:00 UTC and submits a valid request after it
- **THEN** the request is accepted

#### Scenario: Restart does not reset the count

- **WHEN** an account has used its allowance and the server is restarted
- **THEN** the next valid request is still refused with `quota_exceeded`

### Requirement: Spend bonus credits after the daily allowance

The system SHALL hold a one-time, non-expiring bonus credit balance per account. A generation SHALL use the daily allowance first and SHALL spend one bonus credit only when the daily allowance is used up. Bonus credits SHALL NOT reset daily.

#### Scenario: Bonus credit covers a generation past the limit

- **WHEN** a free account has used its 3 daily generations and has 5 bonus credits and submits a valid request
- **THEN** the request is accepted
- **AND** the account then has 4 bonus credits

#### Scenario: Daily allowance is used before bonus credits

- **WHEN** an account with 5 bonus credits and unused daily allowance submits a valid request
- **THEN** its bonus credits are still 5

### Requirement: Count only accepted requests

The system SHALL consume allowance only when a request is accepted for processing. A request rejected for any other reason, including validation failures and authentication failures, SHALL NOT consume allowance. The check and the consumption SHALL be atomic, so concurrent requests cannot exceed the limit.

#### Scenario: Invalid request does not use a generation

- **WHEN** a free account with 3 generations left submits a request with an empty prompt and no photo
- **THEN** the system responds with HTTP 400
- **AND** the account still has 3 generations left

#### Scenario: Concurrent requests cannot exceed the limit

- **WHEN** a free account with 1 generation left submits two valid requests at the same time
- **THEN** exactly one is accepted and the other receives HTTP 429

### Requirement: Refund generations that fail

The system SHALL return the generation to the account, to the allowance or the bonus credits it was taken from, when its job ends in `failed`, and when the job was lost because the server restarted before it finished. A job that ends in `succeeded` SHALL NOT be refunded.

#### Scenario: Failed job is refunded

- **WHEN** a job that used a daily generation ends in `failed`
- **THEN** the account's remaining generations increase by one

#### Scenario: Failed job paid with a bonus credit returns the credit

- **WHEN** a job that spent a bonus credit ends in `failed`
- **THEN** the account's bonus credits increase by one

#### Scenario: Job lost to a restart is refunded

- **WHEN** a job that was queued or running when the server stopped was never finished
- **AND** the server starts again
- **THEN** the account's remaining generations increase by one

#### Scenario: Succeeded job is not refunded

- **WHEN** a job ends in `succeeded`
- **THEN** the account's remaining generations are unchanged

### Requirement: Report remaining generations

The system SHALL report, for the authenticated account, its plan, daily limit, generations used today, bonus credits, total remaining generations, the time of the next reset, and the daily limit of every plan, as part of `GET /me`.

#### Scenario: Usage is reported

- **WHEN** a free account has used 2 generations today and has 5 bonus credits and calls `GET /me`
- **THEN** the usage reports a daily limit of 3, 2 used, 5 bonus credits, and 6 remaining
- **AND** includes the next 00:00 UTC as the reset time and the daily limits of the free and premium plans

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
