# Spec Delta

## ADDED Requirements

### Requirement: Use configured model backend for inference

The system SHALL generate output images by running the prompt through the configured text-to-image model backend. The active backend SHALL be selected via the `MODEL_BACKEND` server configuration. When `MODEL_BACKEND` is `stub`, the server MAY return a placeholder image (for testing and CI); in any other configuration, the server SHALL run real model inference to produce the output image.

#### Scenario: Sana backend produces real inference output

- **WHEN** the server is started with `MODEL_BACKEND=sana`
- **AND** a generation job completes successfully
- **THEN** the output image is produced by running the prompt through the Sana text-to-image model

#### Scenario: Stub backend remains available for testing

- **WHEN** the server is started with `MODEL_BACKEND=stub`
- **AND** a generation job completes successfully
- **THEN** the output image is a placeholder and no model inference is performed
