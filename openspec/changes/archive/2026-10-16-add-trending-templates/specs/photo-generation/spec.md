# Spec Delta

## MODIFIED Requirements

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

### Requirement: Reject invalid prompts

The system SHALL reject requests that supply a `prompt` which is empty or exceeds the configured maximum character length. Rejection SHALL return HTTP 400 and SHALL NOT create a job. This check applies only when the request uses `prompt` rather than `template_id`.

#### Scenario: Empty prompt is rejected

- **WHEN** a client posts `POST /generations` with a valid face image, no `template_id`, and an empty `prompt`
- **THEN** the system responds with HTTP 400

#### Scenario: Overlong prompt is rejected

- **WHEN** a client posts `POST /generations` with a prompt longer than the configured maximum
- **THEN** the system responds with HTTP 400

## ADDED Requirements

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
