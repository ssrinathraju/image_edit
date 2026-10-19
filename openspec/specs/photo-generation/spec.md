# photo-generation Specification

## Purpose

Accepts one or more reference face images plus a text prompt and produces a composed image that preserves the identities of those faces. The capability owns the generation request contract, the asynchronous job lifecycle, input validation, and the retention of uploaded reference images.

## Requirements

### Requirement: Submit a generation job

The system SHALL accept a `POST /generations` request carrying between 1 and 4 reference face images (multipart form field `faces`) and exactly one of: a non-empty `prompt` string, or a `template_id` naming a template in the catalog. On a valid request, the system SHALL enqueue a new generation job and respond with HTTP 202 and a body containing a `job_id` string that uniquely identifies the job. For a `template_id` request, the job SHALL run with that template's prompt.

#### Scenario: Valid submission is accepted

- **WHEN** a client posts 2 reference images and a 50-character prompt to `POST /generations`
- **THEN** the system responds with HTTP 202 and a body containing a `job_id`
- **AND** the job is enqueued for processing

#### Scenario: Template submission is accepted

- **WHEN** a client posts 1 reference image and the `template_id` of an existing template, with no `prompt`
- **THEN** the system responds with HTTP 202 and a body containing a `job_id`
- **AND** the job is processed using that template's prompt

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

The system SHALL reject requests that supply a `prompt` which is empty or exceeds the configured maximum character length. Rejection SHALL return HTTP 400 and SHALL NOT create a job. This check applies only when the request uses `prompt` rather than `template_id`.

#### Scenario: Empty prompt is rejected

- **WHEN** a client posts `POST /generations` with a valid face image, no `template_id`, and an empty `prompt`
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

The system SHALL serve the generated image bytes at the `result_url` returned for a succeeded job, with a `Content-Type` matching the stored image format (`image/png` by default), until the image expires. Once the retention period has passed the system SHALL respond with HTTP 404 for that URL.

#### Scenario: Fetching the result returns the image

- **WHEN** a client issues a GET to the `result_url` of a succeeded job
- **THEN** the response body is the generated image bytes
- **AND** the `Content-Type` header reflects the image format

#### Scenario: Expired result is no longer served

- **WHEN** a client issues a GET to the `result_url` of a job whose image is older than the retention period and has been swept
- **THEN** the system responds with HTTP 404

### Requirement: Discard reference faces after terminal state

The system SHALL delete all uploaded reference face files associated with a job once that job reaches a terminal state (`succeeded` or `failed`). Reference faces SHALL NOT be retained beyond job completion.

#### Scenario: Reference files are purged on completion

- **WHEN** a job reaches `succeeded` or `failed`
- **THEN** all reference face files uploaded with that job are deleted from storage

### Requirement: Use configured model backend for inference

The system SHALL generate output images by running the prompt through the configured text-to-image model backend. The active backend SHALL be selected via the `MODEL_BACKEND` server configuration. When `MODEL_BACKEND` is `stub`, the server MAY return a placeholder image (for testing and CI); in any other configuration, the server SHALL run real model inference to produce the output image.

#### Scenario: Sana backend produces real inference output

- **WHEN** the server is started with `MODEL_BACKEND=sana`
- **AND** a generation job completes successfully
- **THEN** the output image is produced by running the prompt through the Sana text-to-image model

#### Scenario: Stub backend remains available for testing

- **WHEN** the server is started with `MODEL_BACKEND=stub`
- **AND** a generation job completes successfully
- **THEN** the output image is a placeholder and no model inference is performed

### Requirement: Reject invalid template selection

The system SHALL reject a `POST /generations` request with HTTP 400 and error code `invalid_template` when it supplies both `prompt` and `template_id`, or when `template_id` does not name a template in the catalog. No job SHALL be created.

#### Scenario: Unknown template id is rejected

- **WHEN** a client posts a valid face image with `template_id=does-not-exist`
- **THEN** the system responds with HTTP 400 and error `invalid_template`
- **AND** no job is created

#### Scenario: Prompt and template together are rejected

- **WHEN** a client posts a valid face image with both a `prompt` and a valid `template_id`
- **THEN** the system responds with HTTP 400 and error `invalid_template`
- **AND** no job is created

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

### Requirement: Expire generated images after the retention period

The system SHALL delete a generated image once it has existed for longer than the configured retention period (default 24 hours, measured from when the image was written) and SHALL remove the job record that produced it, so that a status request for that job answers HTTP 404. Expiry SHALL be checked when the server starts, before any request is served, and again at a configured interval (default every 10 minutes). Images younger than the retention period SHALL NOT be deleted. Files in the output folder that are not generated images SHALL NOT be deleted.

#### Scenario: Old image is deleted and its job disappears

- **WHEN** a generated image is older than the retention period and a sweep runs
- **THEN** the image file is deleted
- **AND** `GET /generations/{job_id}` for its job responds with HTTP 404

#### Scenario: Recent image is kept

- **WHEN** a generated image is younger than the retention period and a sweep runs
- **THEN** the image is still served and its job is still reported as succeeded

#### Scenario: Images from earlier server runs are removed too

- **WHEN** the server starts and the output folder contains images older than the retention period that no job refers to
- **THEN** those images are deleted before the first request is served

#### Scenario: Unrelated files are left alone

- **WHEN** a sweep runs and the output folder contains a file that is not a PNG image
- **THEN** that file is not deleted

### Requirement: Remove reference faces left behind by an interrupted run

The system SHALL delete the uploaded reference faces of any job that no longer exists, such as a job lost when the server restarted. This SHALL happen when the server starts and on every later sweep. The reference faces of jobs that are queued or running SHALL NOT be deleted.

#### Scenario: Restart removes leftover faces

- **WHEN** the server starts and the input folder holds faces for a job that is not known to the server
- **THEN** those faces are deleted before the first request is served

#### Scenario: Faces of a running job are kept

- **WHEN** a sweep runs while a job is queued or running
- **THEN** that job's reference faces are not deleted

### Requirement: Reject an invalid retention configuration

The system SHALL refuse to start when the image retention period is shorter than 1 hour or the sweep interval is shorter than 1 minute, and SHALL name the offending setting.

#### Scenario: Too-short retention stops startup

- **WHEN** the retention period is configured as 0 hours
- **THEN** the server fails to start
- **AND** the error names the retention setting

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
