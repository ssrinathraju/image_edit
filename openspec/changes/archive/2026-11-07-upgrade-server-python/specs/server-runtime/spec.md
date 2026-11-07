## ADDED Requirements

### Requirement: Require Python 3.11 or later

The server package SHALL declare that it requires Python 3.11 or later, and the repository SHALL pin Python 3.11 as the version used to create the server's environment. Creating the environment with an older Python SHALL fail before anything is installed. The full server test suite SHALL pass on Python 3.11.

#### Scenario: Environment is created with Python 3.11

- **WHEN** a developer runs `uv sync` in `server/` on a machine where uv can provide Python 3.11
- **THEN** the environment's interpreter reports version 3.11
- **AND** `uv run pytest -q` passes

#### Scenario: Older Python is refused

- **WHEN** someone tries to install the server package with Python 3.9
- **THEN** the install fails, naming the required Python version

### Requirement: Refuse oversized whole-number form values without a server error

When a client sends a whole-number form field longer than the field allows (for example a template `popularity` of several thousand digits), the server SHALL answer with the field's normal validation error and SHALL NOT answer HTTP 500, on the Python version the server requires.

#### Scenario: Very long popularity on Python 3.11

- **WHEN** an admin creates a template with a `popularity` of 5000 digits, on Python 3.11
- **THEN** the response is HTTP 400 with error `invalid_template_field` naming `popularity`
