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

The system SHALL serve each template's preview image at its `preview_url` with a `Content-Type` matching the image format. When a template's preview image is replaced, its `preview_url` SHALL change, so a client never shows the old image under the new URL.

#### Scenario: Fetching a preview returns the image

- **WHEN** a client issues a GET to a template's `preview_url`
- **THEN** the response is HTTP 200 with the preview image bytes and an image `Content-Type`

#### Scenario: Replacing a preview changes its URL

- **WHEN** an admin replaces a template's preview image
- **THEN** the next `GET /templates` gives that template a different `preview_url`
- **AND** fetching the new URL returns the new image

### Requirement: Validate the catalog at startup

The system SHALL load the template catalog from its configured source when it starts. If the catalog is malformed, contains duplicate ids, or references a preview image that does not exist, the system SHALL fail to start and report which entry is invalid. The configured source SHALL be the seed catalog only the first time the server starts with a database that has never been seeded; after that it SHALL be the templates stored by the server, and the seed catalog SHALL be ignored, even if every template has been retired.

#### Scenario: Duplicate template id prevents startup

- **WHEN** the configured catalog contains two templates with the same `id`
- **THEN** the server fails to start
- **AND** the error identifies the duplicated id

#### Scenario: First start imports the seed catalog

- **WHEN** the server starts with a database that has never been seeded and a valid seed catalog of 12 templates
- **THEN** `GET /templates` lists those 12 templates with their titles, tags and popularity
- **AND** their preview images are served

#### Scenario: Later starts ignore the seed catalog

- **WHEN** the server has been seeded, an admin has added a template, and the server restarts after the seed file was edited
- **THEN** `GET /templates` lists the stored templates, including the added one, and not the edited seed

#### Scenario: Stored template with a missing preview prevents startup

- **WHEN** a stored template's preview file has been deleted from the storage root
- **THEN** the server fails to start
- **AND** the error identifies that template's id

### Requirement: Hide retired templates

A retired template SHALL NOT appear in `GET /templates`, with or without `q`. Restoring it SHALL make it appear again in its popularity order.

#### Scenario: Retired template is not listed

- **WHEN** an admin retires the template "golden-hour-beach"
- **THEN** `GET /templates` and `GET /templates?q=beach` no longer include it

#### Scenario: Restored template is listed again

- **WHEN** an admin restores a retired template
- **THEN** `GET /templates` includes it again in popularity order
