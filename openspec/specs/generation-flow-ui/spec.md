# generation-flow-ui Specification

## Purpose

The mobile UI for creating and viewing AI-generated images. Lets a user select reference face photos, describe the scene they want, submit the request to the backend, and see the result when it is ready.

## Requirements

### Requirement: Enter a generation prompt

In the custom flow, the app SHALL provide a multi-line prompt text area showing at least four lines, pre-filled with the search text the user entered on the home screen (if any). The app SHALL disable the Generate button while the prompt is blank and SHALL show an inline validation message when the prompt exceeds 500 characters.

#### Scenario: Search text pre-fills the prompt

- **WHEN** the user searches for "astronaut on mars" and taps "Create your own"
- **THEN** the custom screen opens with "astronaut on mars" in the prompt text area

#### Scenario: Empty prompt blocks submission

- **WHEN** the prompt text area is blank
- **THEN** the Generate button is disabled

#### Scenario: Overlong prompt shows validation message

- **WHEN** the prompt exceeds 500 characters
- **THEN** the app shows an inline validation message and disables the Generate button

### Requirement: Submit a generation request

The app SHALL send the chosen photo to the backend together with either the selected template's id (template flow) or the entered prompt (custom flow). While the request is in flight the Generate button SHALL be disabled. On success the app SHALL navigate to the Generation Status screen; on failure it SHALL stay on the current screen and show a human-readable error.

#### Scenario: Successful submission navigates to status screen

- **WHEN** the user taps Generate with a photo and either a template or a valid prompt
- **THEN** the app posts the request to the backend
- **AND** navigates to the Generation Status screen for the new job

#### Scenario: Template submission navigates to status screen

- **WHEN** the user has chosen a template and a photo and taps Generate
- **THEN** the app submits the template id and photo
- **AND** navigates to the Generation Status screen

#### Scenario: Custom submission navigates to status screen

- **WHEN** the user has entered a valid prompt and chosen a photo and taps Generate
- **THEN** the app submits the prompt and photo
- **AND** navigates to the Generation Status screen

#### Scenario: Submission failure shows error

- **WHEN** the backend returns an error or the network is unavailable
- **THEN** the app remains on the current screen and shows a human-readable error message

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

The app SHALL display a descriptive error message and a button to start a new generation when the job status is `failed`. The message SHALL be plain language chosen by the app from the job's error code and SHALL NOT show the raw code. For `pipeline_failed` it SHALL say that the image could not be created this time, that the generation was not counted, and that the user can try again. For any other or missing code it SHALL show a general message that something went wrong and the generation was not counted.

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

### Requirement: Navigate between screens

The app SHALL let the user return from the Generation Status screen to the home screen to start a new generation. Returning home SHALL discard the previous photo and prompt.

#### Scenario: User starts a new generation from the status screen

- **WHEN** the user taps "Home" on the Generation Status screen
- **THEN** the app shows the home screen with an empty search field and no photo selected

### Requirement: Provide a single reference photo

The app SHALL let the user provide exactly one reference photo per generation, either by taking a picture with the device camera or by choosing one from the photo library. The app SHALL show the chosen photo as a preview, SHALL let the user replace it, and SHALL prevent submission until a photo is chosen. If the camera is unavailable, the app SHALL still offer the photo library.

#### Scenario: User takes a picture with the camera

- **WHEN** the user chooses "Take photo" and captures a picture
- **THEN** the captured picture appears as the photo preview

#### Scenario: User picks a photo from the library

- **WHEN** the user chooses "Choose from library" and selects a photo
- **THEN** the selected photo appears as the photo preview

#### Scenario: Choosing another photo replaces the current one

- **WHEN** a photo is already chosen and the user picks a different one
- **THEN** only the newly chosen photo is shown and submitted

#### Scenario: Submission is blocked without a photo

- **WHEN** no photo has been chosen
- **THEN** the Generate button is disabled

### Requirement: Show trending templates on the home screen

The app SHALL open on a home screen that shows the template catalog as a grid of preview images with titles, in the order returned by the backend. While loading it SHALL show a progress indicator; if loading fails it SHALL show an error with a Retry button.

#### Scenario: Home screen shows templates

- **WHEN** the app launches and the backend returns templates
- **THEN** the home screen shows each template's preview and title in backend order

#### Scenario: Catalog load failure offers retry

- **WHEN** the template request fails
- **THEN** the home screen shows an error message and a Retry button that reloads the catalog

### Requirement: Search templates from the home screen

The app SHALL provide a search field on the home screen. As the user types, the app SHALL request matching templates from the backend, waiting until typing pauses for at least 300 ms, and SHALL show the results in the grid.

#### Scenario: Typing filters the grid

- **WHEN** the user types "beach" and pauses
- **THEN** the grid shows only the templates the backend returns for `q=beach`

### Requirement: Offer custom creation from the home screen

The app SHALL always show a "Create your own" entry on the home screen, including when a search is active and when the search returns no templates. Tapping it SHALL open the custom flow with the current search text pre-filled.

#### Scenario: Custom option shown when search has no results

- **WHEN** the user searches for text that matches no template
- **THEN** the screen shows an empty-results message and the "Create your own" entry

### Requirement: Start a generation from a template

Tapping a template SHALL open a template screen showing that template's preview and title, the photo picker, and a Generate button. The template screen SHALL NOT show or allow editing of a prompt.

#### Scenario: Template screen has no prompt field

- **WHEN** the user taps a template on the home screen
- **THEN** the template screen shows the preview, title, photo picker, and Generate button
- **AND** no prompt text field is shown

### Requirement: Retry a generation

When a generation has finished (succeeded or failed), the Generation Status screen SHALL offer a Retry action that submits the same photo and the same template or prompt as a new job and shows that new job's status.

#### Scenario: Retry starts a new job with the same inputs

- **WHEN** a generation has succeeded and the user taps Retry
- **THEN** the app submits a new job with the same photo and template or prompt
- **AND** the status screen tracks the new job

### Requirement: Download the generated image

When a generation has succeeded, the Generation Status screen SHALL offer a Download action that saves the generated image to the device photo library and confirms success. If the user denies photo library permission, the app SHALL explain that permission is needed.

#### Scenario: Download saves to the photo library

- **WHEN** the user taps Download on a succeeded generation and permission is granted
- **THEN** the image is saved to the photo library and the app shows a confirmation

#### Scenario: Permission denied is explained

- **WHEN** the user taps Download and denies photo library permission
- **THEN** the app shows a message that photo library access is required to save

### Requirement: Share the generated image

When a generation has succeeded, the Generation Status screen SHALL offer a Share action that opens the system share sheet with the generated image file attached.

#### Scenario: Share opens the system share sheet

- **WHEN** the user taps Share on a succeeded generation
- **THEN** the system share sheet opens with the generated image attached
