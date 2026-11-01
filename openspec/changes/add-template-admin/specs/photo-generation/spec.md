## MODIFIED Requirements

### Requirement: Reject invalid template selection

The system SHALL reject a `POST /generations` request with HTTP 400 and error code `invalid_template` when it supplies both `prompt` and `template_id`, or when `template_id` does not name a template in the catalog. A retired template SHALL count as not in the catalog. No job SHALL be created. A job accepted before its template was retired or edited SHALL finish with the prompt it was accepted with.

#### Scenario: Unknown template id is rejected

- **WHEN** a client posts a valid face image with `template_id=does-not-exist`
- **THEN** the system responds with HTTP 400 and error `invalid_template`
- **AND** no job is created

#### Scenario: Prompt and template together are rejected

- **WHEN** a client posts a valid face image with both a `prompt` and a valid `template_id`
- **THEN** the system responds with HTTP 400 and error `invalid_template`
- **AND** no job is created

#### Scenario: Retired template is rejected

- **WHEN** a client posts a valid face image with the `template_id` of a retired template
- **THEN** the system responds with HTTP 400 and error `invalid_template`
- **AND** no job is created

#### Scenario: Running job is unaffected by retirement

- **WHEN** a job for a template is running and an admin retires that template
- **THEN** the job finishes and its result is delivered as usual
