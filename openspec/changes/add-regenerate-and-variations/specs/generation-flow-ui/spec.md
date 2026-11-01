## MODIFIED Requirements

### Requirement: Retry a generation

When a generation has finished (succeeded or failed), the Generation Status screen SHALL offer a Retry action that submits the same photo and the same template or prompt as a new job and shows that new job's status. The action SHALL read "More like this" after a success and "Try again" after a failure. It SHALL be offered only while the app still holds that generation's photo, which is while the app has not been restarted and no other generation has been submitted since. Each new job SHALL count as one generation, with the same limit, consent and safety checks as any other submission.

#### Scenario: Retry starts a new job with the same inputs

- **WHEN** a generation has succeeded and the user taps Retry
- **THEN** the app submits a new job with the same photo and template or prompt
- **AND** the status screen tracks the new job

#### Scenario: Labels follow the outcome

- **WHEN** a generation's status screen shows a success
- **THEN** the action reads "More like this"
- **AND** after a failure it reads "Try again"

#### Scenario: Each variation is a new creation

- **WHEN** the user taps "More like this" twice and both jobs succeed
- **THEN** My creations holds three creations with the same label

#### Scenario: Variation at the daily limit

- **WHEN** the user taps "More like this" with no generations left
- **THEN** the limit dialog is shown and no job is submitted

#### Scenario: Not offered without the photo

- **WHEN** a finished generation's status screen is opened after the app was restarted
- **THEN** neither "More like this" nor "Try again" is shown

## ADDED Requirements

### Requirement: Edit the prompt of a custom generation

When a custom-prompt generation has finished and the app still holds its photo, the status screen SHALL offer "Edit prompt". It SHALL open the custom generation form on top of the status screen with the same photo selected and the same prompt filled in, and SHALL submit nothing until the user submits the form. Back SHALL return to the status screen. Template generations SHALL NOT offer "Edit prompt".

#### Scenario: Edit prompt fills the form

- **WHEN** a generation from the prompt "astronaut on a beach" has finished and the user taps "Edit prompt"
- **THEN** the custom form shows the same photo and "astronaut on a beach"
- **AND** no job has been submitted

#### Scenario: Submitting the edited prompt

- **WHEN** the user changes the prompt to "astronaut on the moon" and submits
- **THEN** a new job is submitted with the same photo and the new prompt and its status screen opens

#### Scenario: Back returns to the result

- **WHEN** the user taps Back on the form opened by "Edit prompt"
- **THEN** the status screen of the earlier generation is shown again

#### Scenario: Template generation has no Edit prompt

- **WHEN** a template generation has finished
- **THEN** "Edit prompt" is not shown
