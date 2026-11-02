## ADDED Requirements

### Requirement: Restrict template administration to admins

Every endpoint under `/admin/templates` SHALL require a signed-in account with the admin role. A request without a valid session SHALL get HTTP 401, as the other authenticated endpoints do. A signed-in account without the admin role SHALL get HTTP 403 with error `admin_required`, and nothing SHALL change.

#### Scenario: Non-admin is refused

- **WHEN** a signed-in account without the admin role calls `POST /admin/templates`
- **THEN** the response is HTTP 403 with error `admin_required`
- **AND** no template is created

#### Scenario: Signed-out request is refused

- **WHEN** a request without a session token calls `GET /admin/templates`
- **THEN** the response is HTTP 401

### Requirement: Grant the admin role only through operator tooling

The admin role SHALL be granted and removed only by the operator script `scripts/set_role.py --email <address> --role admin|user`. No HTTP endpoint SHALL grant or remove it. Every account SHALL start without it, and accounts that existed before this change SHALL be without it. Removing the role SHALL take effect on the account's next request.

#### Scenario: Script grants the role

- **WHEN** the operator runs `set_role.py --email ana@example.com --role admin` for an existing account
- **THEN** that account's next call to `GET /admin/templates` succeeds

#### Scenario: Unknown email

- **WHEN** the operator runs `set_role.py` for an email with no account
- **THEN** the script exits with a non-zero status, prints that no account was found, and changes nothing

#### Scenario: Removing the role

- **WHEN** the operator runs `set_role.py --role user` for an admin
- **THEN** that account's next admin request gets HTTP 403 with `admin_required`

### Requirement: List all templates for admins

`GET /admin/templates` SHALL return every stored template, retired ones included, in the public listing's order, followed by retired templates in the same order. Each item SHALL include `id`, `title`, `tags`, `popularity`, `prompt`, `preview_url`, `retired` (boolean) and `updated_at`.

#### Scenario: Admin listing includes retired templates and prompts

- **WHEN** an admin calls `GET /admin/templates` and one of 12 templates is retired
- **THEN** the response lists 12 items, with the retired one last and `retired: true`
- **AND** every item includes its `prompt`

### Requirement: Create a template

`POST /admin/templates` SHALL accept a multipart request with `id`, `title`, `tags` (comma-separated), `popularity`, `prompt` and a `preview` image file. On success it SHALL store the template, respond with HTTP 201 and the template as listed for admins, and the template SHALL appear in `GET /templates` from the next request on. The `id` SHALL be lower-case letters, digits and single hyphens, and SHALL never change after creation.

#### Scenario: Valid template is created and listed

- **WHEN** an admin posts `id=neon-city`, a title, tags `night, city`, popularity 60, a prompt and a valid PNG preview
- **THEN** the response is HTTP 201 with `id` "neon-city" and `retired: false`
- **AND** the next `GET /templates` includes "neon-city" in popularity order with tags `night` and `city`
- **AND** a generation with `template_id=neon-city` is accepted and runs with that prompt

#### Scenario: Duplicate id is refused

- **WHEN** an admin posts a template whose `id` already exists, retired or not
- **THEN** the response is HTTP 409 with error `template_exists`
- **AND** the existing template is unchanged

### Requirement: Edit a template

`PATCH /admin/templates/{id}` SHALL accept a multipart request with any of `title`, `tags`, `popularity`, `prompt` and `preview`, and SHALL change only the fields supplied. On success it SHALL respond with HTTP 200 and the updated template, and the change SHALL apply from the next request on. An `id` that does not exist SHALL get HTTP 404 with error `template_not_found`. A request with no fields SHALL get HTTP 400 with error `invalid_template_field`.

#### Scenario: Editing the prompt changes new jobs only

- **WHEN** an admin changes the prompt of "neon-city" while a job for it is running
- **THEN** the running job finishes with the old prompt
- **AND** the next generation for "neon-city" runs with the new prompt

#### Scenario: Editing the title only

- **WHEN** an admin sends only a new `title` for "neon-city"
- **THEN** `GET /templates` shows the new title with the same tags, popularity and `preview_url`

#### Scenario: Unknown id

- **WHEN** an admin patches `/admin/templates/does-not-exist`
- **THEN** the response is HTTP 404 with error `template_not_found`

### Requirement: Retire and restore a template

`POST /admin/templates/{id}/retire` SHALL mark a template retired, and `POST /admin/templates/{id}/restore` SHALL clear that mark. Both SHALL respond with HTTP 200 and the template, and SHALL succeed without change when the template is already in that state. Nothing about the template SHALL be deleted. An unknown `id` SHALL get HTTP 404 with error `template_not_found`.

#### Scenario: Retire then restore

- **WHEN** an admin retires "neon-city" and later restores it
- **THEN** it is missing from `GET /templates` in between, and listed again afterwards with the same title, tags, popularity, prompt and preview

#### Scenario: Retiring twice

- **WHEN** an admin retires a template that is already retired
- **THEN** the response is HTTP 200 and the template is still retired

### Requirement: Validate template fields

On create and edit, the system SHALL refuse a field that breaks these rules, with HTTP 400, error `invalid_template_field` and the field's name, and SHALL change nothing:
- `id`: 1 to 64 characters, lower-case letters, digits and single hyphens;
- `title`: 1 to 60 characters after trimming;
- `tags`: at most 10, each 1 to 30 characters after trimming, stored in lower case, with duplicates removed;
- `popularity`: a whole number from 0 to 100;
- `prompt`: 1 to 500 characters after trimming.

#### Scenario: Popularity out of range

- **WHEN** an admin creates a template with popularity 150
- **THEN** the response is HTTP 400 with error `invalid_template_field` naming `popularity`
- **AND** no template is created

#### Scenario: Too many tags

- **WHEN** an admin edits a template with 11 tags
- **THEN** the response is HTTP 400 naming `tags` and the template is unchanged

### Requirement: Screen template text with the blocked-term list

On create and edit, the system SHALL check the title, every tag and the prompt against the same blocked-term rules used for user prompts. If any is blocked, it SHALL respond with HTTP 400, error `template_text_blocked` and the field's name, and SHALL change nothing.

#### Scenario: Blocked prompt is refused

- **WHEN** an admin creates a template whose prompt contains a blocked term
- **THEN** the response is HTTP 400 with error `template_text_blocked` naming `prompt`
- **AND** no template is created

#### Scenario: Blocked tag is refused on edit

- **WHEN** an admin edits a template's tags to include a blocked term
- **THEN** the response is HTTP 400 naming `tags` and the template is unchanged

### Requirement: Validate and normalise the preview image

On create, and on an edit that supplies one, the preview SHALL be a PNG, JPEG or WebP file of at most 2 MB that decodes as an image. The system SHALL store it as a 512×512 WebP, cropped to a centred square. A preview that is missing on create, too large, or not a decodable PNG, JPEG or WebP SHALL be refused with HTTP 400 and error `invalid_preview`, and nothing SHALL change.

#### Scenario: Valid preview is normalised

- **WHEN** an admin creates a template with a 1200×800 JPEG preview
- **THEN** the template's `preview_url` serves a 512×512 WebP image

#### Scenario: Oversized preview is refused

- **WHEN** an admin uploads a 3 MB preview
- **THEN** the response is HTTP 400 with error `invalid_preview`
- **AND** the template and its current preview are unchanged

#### Scenario: Non-image file is refused

- **WHEN** an admin uploads a text file named `preview.png`
- **THEN** the response is HTTP 400 with error `invalid_preview`

### Requirement: Record every template change

Every successful create, edit, retire and restore SHALL write one log line naming the action, the template id and the admin's account id. The line SHALL NOT include the prompt, title, tags, or the admin's email address.

#### Scenario: Change is logged without its text

- **WHEN** an admin edits the prompt of "neon-city"
- **THEN** one log line records the edit, "neon-city" and the admin's account id
- **AND** it does not contain the old or new prompt
