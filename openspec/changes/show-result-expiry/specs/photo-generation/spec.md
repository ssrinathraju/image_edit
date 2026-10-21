## ADDED Requirements

### Requirement: Report when a result expires

For a `succeeded` job, `GET /generations/{job_id}` SHALL include `expires_at`: the time, in UTC as ISO 8601, at which the retention sweep may delete the generated image. That is the moment the image was written plus the configured retention period. For any other status, `expires_at` SHALL be null.

#### Scenario: Succeeded job reports its expiry

- **WHEN** a job succeeded and its image was written at 2026-10-22T10:00:00Z with a retention period of 24 hours
- **THEN** the status response contains `expires_at` equal to 2026-10-23T10:00:00Z

#### Scenario: Unfinished or failed job has no expiry

- **WHEN** a job is `queued`, `running`, or `failed`
- **THEN** the status response contains `expires_at` null

#### Scenario: Expiry follows the configured retention

- **WHEN** the retention period is configured to 48 hours and a job succeeds
- **THEN** its `expires_at` is 48 hours after its image was written
