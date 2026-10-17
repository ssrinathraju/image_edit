# Spec Delta

## MODIFIED Requirements

### Requirement: Deliver the generated image on success

The system SHALL serve the generated image bytes at the `result_url` returned for a succeeded job, with a `Content-Type` matching the stored image format (`image/png` by default), until the image expires. Once the retention period has passed the system SHALL respond with HTTP 404 for that URL.

#### Scenario: Fetching the result returns the image

- **WHEN** a client issues a GET to the `result_url` of a succeeded job
- **THEN** the response body is the generated image bytes
- **AND** the `Content-Type` header reflects the image format

#### Scenario: Expired result is no longer served

- **WHEN** a client issues a GET to the `result_url` of a job whose image is older than the retention period and has been swept
- **THEN** the system responds with HTTP 404

## ADDED Requirements

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
