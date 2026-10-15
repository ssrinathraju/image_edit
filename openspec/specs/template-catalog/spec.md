# template-catalog Specification

## Purpose
Provides the curated catalog of generation templates that clients browse and search. Each template pairs a public title, tags, and preview image with a server-held prompt, so users can get a good result by choosing a style instead of writing a prompt.

## Requirements

### Requirement: List templates ordered by popularity

The system SHALL expose `GET /templates` returning a JSON array of templates. Each item SHALL include `id`, `title`, `tags` (array of strings), and `preview_url`. Items SHALL be ordered by descending popularity score, with ties broken by `title` ascending.

#### Scenario: Listing returns templates in popularity order

- **WHEN** a client calls `GET /templates` with no query parameters
- **AND** the catalog contains templates with popularity 90, 50, and 70
- **THEN** the response is HTTP 200 and lists them in the order 90, 70, 50
- **AND** every item contains `id`, `title`, `tags`, and `preview_url`

### Requirement: Search templates by text

The system SHALL accept an optional `q` query parameter on `GET /templates`. When `q` is non-blank, the response SHALL contain only templates whose title or any tag contains `q` as a case-insensitive substring, in the same order as the unfiltered listing. A blank `q` SHALL behave as if it were absent.

#### Scenario: Search matches on tag, case-insensitively

- **WHEN** a client calls `GET /templates?q=BEACH`
- **AND** one template has the tag `beach` and another has neither title nor tag containing `beach`
- **THEN** the response contains only the template tagged `beach`

#### Scenario: Search with no matches returns an empty list

- **WHEN** a client calls `GET /templates?q=zzzz` and no template matches
- **THEN** the response is HTTP 200 with an empty array

### Requirement: Keep template prompts server-side

The system SHALL NOT include a template's prompt text in any `GET /templates` response. Prompt text SHALL only be used by the server when running a generation for that template.

#### Scenario: Listing omits prompts

- **WHEN** a client calls `GET /templates`
- **THEN** no item in the response contains a `prompt` field or the prompt text

### Requirement: Serve template preview images

The system SHALL serve each template's preview image at its `preview_url` with a `Content-Type` matching the image format.

#### Scenario: Fetching a preview returns the image

- **WHEN** a client issues a GET to a template's `preview_url`
- **THEN** the response is HTTP 200 with the preview image bytes and an image `Content-Type`

### Requirement: Validate the catalog at startup

The system SHALL load the template catalog from its configured source when it starts. If the catalog is malformed, contains duplicate ids, or references a preview image that does not exist, the system SHALL fail to start and report which entry is invalid.

#### Scenario: Duplicate template id prevents startup

- **WHEN** the configured catalog contains two templates with the same `id`
- **THEN** the server fails to start
- **AND** the error identifies the duplicated id
