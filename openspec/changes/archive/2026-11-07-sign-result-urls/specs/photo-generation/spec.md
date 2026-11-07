## MODIFIED Requirements

### Requirement: Deliver the generated image on success

The system SHALL serve the generated image bytes at the `result_url` returned for a succeeded job, with a `Content-Type` matching the stored image format (`image/png` by default), until the image expires. Once the retention period has passed the system SHALL respond with HTTP 404 for that URL.

Every `result_url` SHALL be signed: it SHALL carry an expiry time 15 minutes after it was issued and a signature over the job id and that expiry, made with a server-held secret. Each `GET /generations/{job_id}` for a succeeded job SHALL return a newly signed `result_url`. The system SHALL respond with HTTP 404, the same response as for an image that does not exist, to a request for a result image that has no signature, an expired signature, a signature that does not match, or a signature made for another job. Image responses SHALL tell clients and intermediaries not to keep the image beyond the URL's expiry.

#### Scenario: Fetching the result returns the image

- **WHEN** a client issues a GET to the `result_url` of a succeeded job
- **THEN** the response body is the generated image bytes
- **AND** the `Content-Type` header reflects the image format

#### Scenario: Expired result is no longer served

- **WHEN** a client issues a GET to the `result_url` of a job whose image is older than the retention period and has been swept
- **THEN** the system responds with HTTP 404

#### Scenario: Unsigned URL is refused

- **WHEN** a client requests `/images/{job_id}.png` of a succeeded job without the signature parameters
- **THEN** the system responds with HTTP 404

#### Scenario: Expired signed URL is refused

- **WHEN** a client requests a `result_url` 16 minutes after it was issued, while the image is still within retention
- **THEN** the system responds with HTTP 404

#### Scenario: Tampered or borrowed signature is refused

- **WHEN** a client changes the expiry of a `result_url`, or uses one job's signature with another job's id
- **THEN** the system responds with HTTP 404

#### Scenario: Each status call gives a fresh URL

- **WHEN** a client calls `GET /generations/{job_id}` for a succeeded job 20 minutes after an earlier call
- **THEN** the returned `result_url` has a later expiry than the earlier one
- **AND** fetching it returns the image

#### Scenario: Signed URL stops working once the image is swept

- **WHEN** a client requests a `result_url` that has not expired, after the retention sweep deleted the image
- **THEN** the system responds with HTTP 404
