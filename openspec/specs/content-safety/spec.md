# content-safety Specification

## Purpose
Keeps unsafe content out of the service. Covers screening prompts against a term list, screening uploaded photos and generated images with a classifier that runs on the server, pausing accounts that repeatedly produce blocked results, and letting users report results for review.

## Requirements

### Requirement: Screen custom prompts against a term list

The system SHALL refuse a `POST /generations` whose custom `prompt` contains a term from the configured blocked-term list. It SHALL respond with HTTP 400 and error `prompt_blocked`, SHALL NOT create a job or count a generation, and SHALL NOT echo the matched term or the prompt. Before matching, the prompt SHALL be normalised:
- letter case and accents are ignored;
- the common substitutions `0→o`, `1→i`, `3→e`, `4→a`, `5→s`, `7→t`, `@→a` and `$→s` are reversed;
- runs of characters that are not letters count as one separator.

A term SHALL match only as whole words, so a blocked term inside a longer harmless word does not match. Template prompts SHALL NOT be screened against the list.

#### Scenario: Blocked term is refused

- **WHEN** an account submits a custom prompt containing a term on the list
- **THEN** the system responds with HTTP 400 and error `prompt_blocked`
- **AND** no job is created and the remaining generations are unchanged

#### Scenario: Disguised term is still caught

- **WHEN** the list contains `nude` and the prompt contains `N-U-D-3` or `Nüde`
- **THEN** the system responds with HTTP 400 and error `prompt_blocked`

#### Scenario: Harmless word containing a term is allowed

- **WHEN** the list contains `ass` and the prompt is `a classic portrait in a grassy field`
- **THEN** the prompt is not blocked

#### Scenario: Template prompts are not screened

- **WHEN** an account starts a generation from a catalog template
- **THEN** the template's prompt is not checked against the list

### Requirement: Screen uploaded photos before queueing

The system SHALL check every uploaded reference photo with the image classifier after it has passed the existing image checks, before any job is created or generation counted. A photo whose score is at or above the configured threshold SHALL make the request fail with HTTP 400 and error `photo_blocked`. Nothing from the request SHALL be stored, and no generation SHALL be counted.

#### Scenario: Flagged photo is refused

- **WHEN** an account submits a photo that the classifier scores above the threshold
- **THEN** the system responds with HTTP 400 and error `photo_blocked`
- **AND** no job is created, no file is stored, and the remaining generations are unchanged

#### Scenario: Safe photo continues

- **WHEN** every uploaded photo scores below the threshold
- **THEN** the request continues to the generation as before

### Requirement: Screen generated images before delivery

After the pipeline writes an image, the system SHALL check it with the image classifier before the job becomes `succeeded`. A flagged image SHALL be deleted and never served. Its job SHALL become `failed` with error `content_blocked`, the generation SHALL be refunded, and a strike SHALL be recorded against the account. If the classifier itself fails, the image SHALL be deleted, the job SHALL become `failed` with error `safety_check_failed`, the generation SHALL be refunded, and no strike SHALL be recorded.

#### Scenario: Flagged result is never delivered

- **WHEN** a generated image scores above the threshold
- **THEN** the job is `failed` with error `content_blocked`
- **AND** `GET /images/{job_id}.png` responds with HTTP 404
- **AND** the account's remaining generations are restored
- **AND** one strike is recorded for the account

#### Scenario: Classifier failure fails closed

- **WHEN** the classifier raises an error while checking a generated image
- **THEN** the job is `failed` with error `safety_check_failed`, the image is not served, the generation is restored, and no strike is recorded

#### Scenario: Safe result is delivered

- **WHEN** a generated image scores below the threshold
- **THEN** the job is `succeeded` and the image is served as before

### Requirement: Pause accounts with repeated blocked results

When an account has 3 strikes (configurable) within the last 24 hours, the system SHALL refuse its `POST /generations` with HTTP 403, error `generation_suspended`, and a `suspended_until` time: 24 hours after the third-most-recent strike. This check SHALL run right after the age and consent checks, before any input is read or counted. Other endpoints SHALL be unaffected. Strikes older than 24 hours SHALL no longer count.

#### Scenario: Third strike pauses generating

- **WHEN** an account has had 3 results blocked in the last 24 hours and submits a valid request
- **THEN** the system responds with HTTP 403, error `generation_suspended`, and the time 24 hours after the third-most-recent strike
- **AND** `GET /me` and `GET /generations/{job_id}` still work

#### Scenario: Pause ends by itself

- **WHEN** the oldest of those 3 strikes becomes more than 24 hours old
- **THEN** the next valid submission is accepted

#### Scenario: Two strikes do not pause

- **WHEN** an account has 2 strikes in the last 24 hours
- **THEN** its submissions are accepted

### Requirement: Accept reports of results

The system SHALL expose `POST /reports`, for authenticated requests, as multipart form data with:
- a `job_id`;
- a `category`, one of `sexual`, `minor`, `violence`, `hate` or `other`;
- an optional `note` of up to 500 characters;
- an optional `image`.

When the job's image still exists on the server and the job belongs to the reporter, the system SHALL keep a copy of the server's image with the report and ignore any uploaded image. Otherwise it SHALL keep the uploaded image, if it passes the existing image checks, and record that it came from the device. It SHALL store the reporter, the job id, the category, the note, the source of the image and the time, and SHALL respond with HTTP 201. A job id that belongs to another account's existing job SHALL get HTTP 404.

#### Scenario: Recent result is reported with the server's copy

- **WHEN** a user reports their own job whose image is still on the server, with category `violence`
- **THEN** the system responds with HTTP 201
- **AND** the stored report holds a copy of the server's image, marked as coming from the server

#### Scenario: Old creation is reported with the device's copy

- **WHEN** a user reports a job id whose server image has expired and uploads the image
- **THEN** the system responds with HTTP 201 and stores the uploaded image, marked as coming from the device

#### Scenario: Another account's job

- **WHEN** a user reports a job id that belongs to another account's existing job
- **THEN** the system responds with HTTP 404 and stores nothing

#### Scenario: Invalid category or note

- **WHEN** a report has an unknown category or a note longer than 500 characters
- **THEN** the system responds with HTTP 400 and error `invalid_report` and stores nothing

### Requirement: Limit reports per account

The system SHALL accept at most 20 (configurable) reports per account in any 24-hour window. Further reports SHALL get HTTP 429 with error `too_many_reports` and SHALL store nothing.

#### Scenario: Twenty-first report in a day is refused

- **WHEN** an account has sent 20 reports in the last 24 hours and sends another
- **THEN** the system responds with HTTP 429 and error `too_many_reports`

### Requirement: Keep reports for 30 days

The system SHALL delete each report and its image 30 days (configurable) after it was made, whether or not it was reviewed. Reported images SHALL NOT be deleted by the generated-image retention sweep. Deleting an account SHALL delete the reports it made and their images.

#### Scenario: Old report is removed

- **WHEN** a report is older than 30 days and the sweep runs
- **THEN** the report and its image are gone

#### Scenario: Reported image outlives the generation

- **WHEN** a job's generated image is deleted by the 24-hour retention sweep after it was reported
- **THEN** the report's copy of the image is still kept

#### Scenario: Reporter deletes their account

- **WHEN** a user who made reports deletes their account
- **THEN** their reports and the report images are deleted

### Requirement: Review reports with an operator tool

The system SHALL provide an operator command-line tool, run on the server, that lists open reports newest first, writes a report's image to a chosen file, and marks a report resolved with a short outcome. It SHALL never be reachable over HTTP.

#### Scenario: Operator resolves a report

- **WHEN** the operator lists reports, saves one report's image, and marks it resolved with outcome `removed`
- **THEN** the report no longer appears in the open list and records the outcome and time

### Requirement: Refuse to run a real model without the image classifier

When the configured model backend is anything other than `stub`, the server SHALL refuse to start unless the local image classifier loads successfully. With the `stub` backend it SHALL use a stub classifier, which scores everything as safe unless configured for testing to flag generated images only, or uploads and generated images.

#### Scenario: Real backend without the classifier

- **WHEN** the server starts with model backend `sana` and the classifier model cannot be loaded
- **THEN** the server refuses to start with an error naming the classifier

#### Scenario: Stub backend for development

- **WHEN** the server starts with model backend `stub`
- **THEN** it starts without loading any classifier model

### Requirement: Keep safety decisions private

The system SHALL NOT include classifier scores, the matched term, or the blocked prompt in any response. It SHALL log a safety decision with the event, the job or request, and the account id only, never the prompt text or the score.

#### Scenario: Refusals carry no detail

- **WHEN** a prompt is refused with `prompt_blocked`
- **THEN** the response body is the fixed refusal and does not contain the prompt or the matched term
- **AND** the server log has the event and account id but not the prompt
