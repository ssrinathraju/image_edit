## MODIFIED Requirements

### Requirement: Display a human-readable error on failure

The app SHALL display a descriptive error message and a button to start a new generation when the job status is `failed`. The message SHALL be plain language chosen by the app from the job's error code and SHALL NOT show the raw code. For `pipeline_failed` it SHALL say that the image could not be created this time, that the generation was not counted, and that the user can try again. For any other or missing code it SHALL show a general message that something went wrong and the generation was not counted.

#### Scenario: Failed job shows error and retry option

- **WHEN** the job status is `failed`
- **THEN** the app shows an error message
- **AND** provides a button to return to the New Generation screen

#### Scenario: Pipeline failure reads as plain language

- **WHEN** the job status is `failed` with error `pipeline_failed`
- **THEN** the app says the image could not be created this time, that the generation was not counted, and that the user can try again
- **AND** the text `pipeline_failed` is not shown

#### Scenario: Unknown error code gets the general message

- **WHEN** the job status is `failed` with an error code the app does not know, or with no error code
- **THEN** the app shows the general message and not the code

