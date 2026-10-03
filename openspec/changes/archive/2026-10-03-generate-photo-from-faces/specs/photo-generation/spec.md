# Spec Delta

## Purpose

Accepts one or more reference face images plus a text prompt and produces a composed image that preserves the identities of those faces. The capability owns the generation request contract, the asynchronous job lifecycle, input validation, and the retention of uploaded reference images.

## ADDED Requirements

### Requirement: Submit a generation job

The system SHALL accept a `POST /generations` request carrying between 1 and 4 reference face images (multipart form field `faces`) and a non-empty `prompt` string. On a valid request, the system SHALL enqueue a new generation job and respond with HTTP 202 and a body containing a `job_id` string that uniquely identifies the job.

#### Scenario: Valid submission is accepted

- **WHEN** a client posts 2 reference images and a 50-character prompt to `POST /generations`
- **THEN** the system responds with HTTP 202 and a body containing a `job_id`
- **AND** the job is enqueued for processing

### Requirement: Reject requests with an invalid face count

The system SHALL reject requests that carry zero reference faces or more than four reference faces with HTTP 400 and a descriptive error message. The job SHALL NOT be enqueued.

#### Scenario: Zero faces are rejected

- **WHEN** a client posts `POST /generations` with no `faces` field and any prompt
- **THEN** the system responds with HTTP 400
- **AND** no job is created

#### Scenario: More than four faces are rejected

- **WHEN** a client posts `POST /generations` with 5 face images and any prompt
- **THEN** the system responds with HTTP 400
- **AND** no job is created

### Requirement: Reject invalid reference images

The system SHALL reject any `faces` upload whose MIME type is not an accepted image type (`image/jpeg`, `image/png`, `image/webp`) or whose byte size exceeds the configured per-file maximum. Rejection SHALL return HTTP 400 and SHALL NOT create a job.

#### Scenario: Non-image file is rejected

- **WHEN** a client submits a reference upload with `Content-Type: text/plain`
- **THEN** the system responds with HTTP 400
- **AND** no job is created

#### Scenario: Oversized image is rejected

- **WHEN** a client submits a reference image larger than the configured maximum
- **THEN** the system responds with HTTP 400
- **AND** no job is created

### Requirement: Reject invalid prompts

The system SHALL reject requests whose `prompt` is empty or exceeds the configured maximum character length. Rejection SHALL return HTTP 400 and SHALL NOT create a job.

#### Scenario: Empty prompt is rejected

- **WHEN** a client posts `POST /generations` with a valid face image and an empty `prompt`
- **THEN** the system responds with HTTP 400

#### Scenario: Overlong prompt is rejected

- **WHEN** a client posts `POST /generations` with a prompt longer than the configured maximum
- **THEN** the system responds with HTTP 400

### Requirement: Report job lifecycle status

The system SHALL expose `GET /generations/{job_id}` which returns the current status of a known job as one of `queued`, `running`, `succeeded`, or `failed`. When the job has `succeeded`, the response SHALL include a `result_url` pointing to the generated image. When the job has `failed`, the response SHALL include a short machine-readable `error` code.

#### Scenario: Queued job reports queued

- **WHEN** a client gets a job that has been enqueued but not started
- **THEN** the response status is `queued`

#### Scenario: Running job reports running

- **WHEN** a client gets a job whose pipeline is currently executing
- **THEN** the response status is `running`

#### Scenario: Succeeded job returns a result URL

- **WHEN** a client gets a job whose pipeline has completed successfully
- **THEN** the response status is `succeeded`
- **AND** the response includes a `result_url`

#### Scenario: Failed job returns an error code

- **WHEN** a client gets a job whose pipeline raised an unrecoverable error
- **THEN** the response status is `failed`
- **AND** the response includes an `error` field

### Requirement: Unknown job id returns 404

The system SHALL return HTTP 404 for any `GET /generations/{job_id}` where the job id is not recognized.

#### Scenario: Unknown job id

- **WHEN** a client gets a job id that was never issued
- **THEN** the system responds with HTTP 404

### Requirement: Deliver the generated image on success

The system SHALL serve the generated image bytes at the `result_url` returned for a succeeded job, with a `Content-Type` matching the stored image format (`image/png` by default).

#### Scenario: Fetching the result returns the image

- **WHEN** a client issues a GET to the `result_url` of a succeeded job
- **THEN** the response body is the generated image bytes
- **AND** the `Content-Type` header reflects the image format

### Requirement: Discard reference faces after terminal state

The system SHALL delete all uploaded reference face files associated with a job once that job reaches a terminal state (`succeeded` or `failed`). Reference faces SHALL NOT be retained beyond job completion.

#### Scenario: Reference files are purged on completion

- **WHEN** a job reaches `succeeded` or `failed`
- **THEN** all reference face files uploaded with that job are deleted from storage

### Requirement: Expose endpoints without authentication (transitional)

The system SHALL accept `POST /generations` and `GET /generations/{job_id}` requests without any authentication credentials in this change. This is transitional: authentication MUST be added by a subsequent change before the endpoints are exposed outside a trusted local network. The spec records this constraint so that the gap is not forgotten.

#### Scenario: Unauthenticated request is accepted

- **WHEN** a client posts a valid request to `POST /generations` with no `Authorization` header and no API key
- **THEN** the system accepts the request and returns HTTP 202
