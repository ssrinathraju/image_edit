# Spec Delta

## Purpose

The mobile UI for creating and viewing AI-generated images. Lets a user select reference face photos, describe the scene they want, submit the request to the backend, and see the result when it is ready.

## ADDED Requirements

### Requirement: Select reference face photos

The app SHALL allow the user to pick between 1 and 4 photos from the device photo library as reference faces. The app SHALL prevent submission when no photos are selected and SHALL NOT allow more than 4 photos to be selected.

#### Scenario: User selects photos from gallery

- **WHEN** the user taps the add-photo control on the New Generation screen
- **THEN** the device photo picker opens and the user can select one or more photos
- **AND** selected photos appear as thumbnails on the screen

#### Scenario: Adding a fifth photo is blocked

- **WHEN** 4 photos are already selected and the user attempts to add another
- **THEN** the app does not open the picker and shows a message that the maximum is 4 photos

### Requirement: Enter a generation prompt

The app SHALL provide a text input for the generation prompt. The app SHALL disable the submit control when the prompt is empty and SHALL show a validation message when the prompt exceeds 500 characters.

#### Scenario: Empty prompt blocks submission

- **WHEN** the prompt field is empty
- **THEN** the submit button is disabled

#### Scenario: Overlong prompt shows validation message

- **WHEN** the prompt exceeds 500 characters
- **THEN** the app shows an inline validation message and disables the submit button

### Requirement: Submit a generation request

The app SHALL send the selected face photos and prompt to the backend when the user confirms submission. While the request is in flight the submit control SHALL be disabled to prevent duplicate submissions. On a successful submission the app SHALL navigate to the Generation Status screen.

#### Scenario: Successful submission navigates to status screen

- **WHEN** the user taps Submit with valid photos and a valid prompt
- **THEN** the app posts the request to the backend
- **AND** navigates to the Generation Status screen showing the new job id

#### Scenario: Submission failure shows error

- **WHEN** the backend returns an error or the network is unavailable
- **THEN** the app remains on the New Generation screen and shows a human-readable error message

### Requirement: Display live generation status

The app SHALL poll the backend for job status every 2 seconds while the job is in a non-terminal state and display the current status to the user. The app SHALL stop polling once the job reaches `succeeded` or `failed`.

#### Scenario: Queued or running job shows progress indicator

- **WHEN** the job status is `queued` or `running`
- **THEN** the app shows a progress indicator and the current status label

#### Scenario: Polling stops on terminal state

- **WHEN** the job status changes to `succeeded` or `failed`
- **THEN** the app stops polling and updates the UI to reflect the terminal state

### Requirement: Display the generated image on success

The app SHALL fetch and display the generated image when the job status is `succeeded`. The image SHALL be displayed at a size that fills the available screen width while maintaining its aspect ratio.

#### Scenario: Succeeded job shows the image

- **WHEN** the job status is `succeeded`
- **THEN** the app fetches the image from `result_url` and displays it on screen

### Requirement: Display a human-readable error on failure

The app SHALL display a descriptive error message and a button to start a new generation when the job status is `failed`.

#### Scenario: Failed job shows error and retry option

- **WHEN** the job status is `failed`
- **THEN** the app shows an error message
- **AND** provides a button to return to the New Generation screen

### Requirement: Navigate between screens

The app SHALL provide a way to navigate from the Generation Status screen back to the New Generation screen to start a fresh request.

#### Scenario: User starts a new generation from the status screen

- **WHEN** the user taps "New Generation" on the Generation Status screen
- **THEN** the app navigates back to the New Generation screen with all fields cleared
