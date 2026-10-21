## MODIFIED Requirements

### Requirement: Display a human-readable error on failure

The app SHALL display a descriptive error message and a button to start a new generation when the job status is `failed`. The message SHALL be plain language chosen by the app from the job's error code and SHALL NOT show the raw code. For `pipeline_failed` it SHALL say that the image could not be created this time, that the generation was not counted, and that the user can try again. For `content_blocked` it SHALL say that the image was blocked by the content rules and the generation was not counted. For any other or missing code it SHALL show a general message that something went wrong and the generation was not counted.

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

#### Scenario: Blocked result reads as a content-rules message

- **WHEN** the job status is `failed` with error `content_blocked`
- **THEN** the app says the image was blocked by the content rules and was not counted
- **AND** no image is shown

## ADDED Requirements

### Requirement: Explain a blocked prompt or photo

When a submission is refused with `prompt_blocked`, the form SHALL stay open with the entered values and say the prompt contains words that are not allowed. When it is refused with `photo_blocked`, the form SHALL stay open and say the photo can't be used and to choose another.

#### Scenario: Blocked prompt keeps the form

- **WHEN** the server refuses a submission with `prompt_blocked`
- **THEN** the form shows the same prompt and photo and says the prompt contains words that are not allowed

#### Scenario: Blocked photo asks for another

- **WHEN** the server refuses a submission with `photo_blocked`
- **THEN** the form stays open and says the photo can't be used and to choose another

### Requirement: Explain a paused account

When a submission is refused with `generation_suspended`, the app SHALL show a dialog saying generating is paused until the given time, in the device's local time, because recent results broke the content rules. The form values SHALL be kept, and browsing, My creations, Download and Share SHALL keep working.

#### Scenario: Paused account sees when it ends

- **WHEN** the server refuses a submission with `generation_suspended` and an end time
- **THEN** the app shows a dialog with that end time in local time
- **AND** closing it returns to the form with the values kept

### Requirement: Report a result from the status screen

When a generation has succeeded, the status screen SHALL offer Report. Report SHALL open a sheet with a required category (Sexual content, Involves a minor, Violence or gore, Hateful content, Other) and an optional note of up to 500 characters. Send SHALL submit the report with the app's copy of the image and the job id, then confirm with "Thanks, we'll review it." A refusal for sending too many reports SHALL be shown, and cancelling SHALL send nothing.

#### Scenario: Report is sent with a category

- **WHEN** the user taps Report on a succeeded result, chooses Violence or gore, and taps Send
- **THEN** the app sends the report with the job id, the category, and the image
- **AND** shows "Thanks, we'll review it."

#### Scenario: Category is required

- **WHEN** the report sheet is open and no category is chosen
- **THEN** Send is disabled

#### Scenario: Too many reports

- **WHEN** the server refuses a report with `too_many_reports`
- **THEN** the sheet says the user has sent too many reports today and to try again tomorrow

