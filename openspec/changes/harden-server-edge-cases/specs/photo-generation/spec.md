## ADDED Requirements

### Requirement: Expire finished job records

The system SHALL record when each job reaches `succeeded` or `failed`. Each retention sweep SHALL remove the record of every finished job that finished longer ago than the retention period, whether or not it has a generated image, so that `GET /generations/{job_id}` for it answers HTTP 404. Records of queued or running jobs SHALL NOT be removed.

#### Scenario: Old failed job disappears

- **WHEN** a job failed more than the retention period ago and a sweep runs
- **THEN** `GET /generations/{job_id}` for it responds with HTTP 404

#### Scenario: Recent failed job is kept

- **WHEN** a job failed less than the retention period ago and a sweep runs
- **THEN** `GET /generations/{job_id}` still reports it as `failed`

#### Scenario: Live jobs are never removed

- **WHEN** a job has been queued or running for longer than the retention period and a sweep runs
- **THEN** its record is kept
