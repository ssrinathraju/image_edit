## MODIFIED Requirements

### Requirement: Save a finished generation on the device

When a generation succeeds while its status screen is open, the app SHALL save the image to its private storage on the device. With it, the app SHALL record the job id, the signed-in account, the prompt or template title used, whether it came from a custom prompt (with that prompt) or a template (with its id), and the time the generation finished. The app SHALL save each job at most once.

#### Scenario: Watched generation is saved

- **WHEN** a user submits a generation with the prompt "astronaut on a beach" and waits on the status screen until it succeeds
- **THEN** My creations contains that image labelled "astronaut on a beach"

#### Scenario: Template generation is labelled with the template

- **WHEN** a user starts a generation from the "Golden Hour Beach" template and it succeeds
- **THEN** the saved creation is labelled "Golden Hour Beach"

#### Scenario: Reopening the status screen does not duplicate

- **WHEN** a succeeded generation's status screen is opened a second time
- **THEN** My creations still holds exactly one creation for that job

#### Scenario: Source is kept with the creation

- **WHEN** a generation from the "golden-hour-beach" template is saved, by its status screen or by the catch-up
- **THEN** the creation records that it came from the template "golden-hour-beach"

## ADDED Requirements

### Requirement: Make another from a creation

The creation detail screen SHALL offer "Make another" for a creation whose source is recorded. For a template creation it SHALL open that template's screen; for a custom creation it SHALL open the custom generation form with the prompt filled in. In both cases no photo SHALL be selected, because the app does not keep the photo, and nothing SHALL be submitted until the user picks a photo and submits. Back SHALL return to the creation detail. A creation saved before sources were recorded SHALL NOT offer "Make another".

#### Scenario: Make another from a template creation

- **WHEN** the user opens a creation made from the "golden-hour-beach" template and taps "Make another"
- **THEN** the "golden-hour-beach" template screen opens with no photo selected

#### Scenario: Make another from a custom creation

- **WHEN** the user opens a creation made from the prompt "astronaut on a beach" and taps "Make another"
- **THEN** the custom form opens with "astronaut on a beach" filled in and no photo selected

#### Scenario: Nothing is submitted until the user submits

- **WHEN** the user taps "Make another" and then Back without submitting
- **THEN** the creation detail is shown again and no job was submitted

#### Scenario: Older creation has no Make another

- **WHEN** the user opens a creation saved before this change
- **THEN** "Make another" is not shown and the image, Download, Share and Delete still work

#### Scenario: Template no longer available

- **WHEN** the user taps "Make another" on a creation whose template the server no longer has
- **THEN** the template screen shows its existing error state and nothing is submitted
