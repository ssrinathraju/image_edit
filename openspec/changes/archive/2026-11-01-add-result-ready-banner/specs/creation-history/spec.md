## MODIFIED Requirements

### Requirement: Catch up on generations finished while away

The app SHALL remember every generation the signed-in account submits. Whenever the home screen or the My creations screen opens, and every 5 seconds while the app is in the foreground with a signed-in account and at least one remembered generation not yet saved, the app SHALL check each remembered generation that has not been saved:
- one that has succeeded SHALL be saved as a creation;
- one that has failed, or that the server no longer knows, SHALL be forgotten;
- one still queued or running SHALL be checked again next time.

A remembered generation older than 24 hours SHALL be forgotten without a check. A network error during the check SHALL leave the generation remembered and SHALL NOT be shown as an error.

#### Scenario: Result finished after leaving the status screen

- **WHEN** a user submits a generation, goes back to the home screen before it finishes, and opens My creations after the server reports it succeeded
- **THEN** My creations contains that creation

#### Scenario: Failed generation is not added

- **WHEN** a remembered generation has failed by the time the home screen opens
- **THEN** no creation is added for it and it is no longer checked

#### Scenario: Generation the server no longer has is forgotten

- **WHEN** the server answers that a remembered generation does not exist
- **THEN** no creation is added and it is no longer checked

#### Scenario: Offline check keeps the generation remembered

- **WHEN** the home screen opens without network access while a generation is remembered
- **THEN** no error is shown
- **AND** the generation is checked again the next time the home screen opens with network access

#### Scenario: Old generations are forgotten

- **WHEN** a remembered generation was submitted more than 24 hours ago and was never saved
- **THEN** it is forgotten without contacting the server

#### Scenario: Result finished while the app is open on another screen

- **WHEN** a user submits a generation, leaves the status screen for the profile screen, and the server reports it succeeded
- **THEN** within 5 seconds of that, without the user opening home or My creations, the creation is saved

#### Scenario: No checks while the app is in the background

- **WHEN** the app moves to the background while a generation is remembered
- **THEN** the app makes no status checks until it returns to the foreground
- **AND** on returning to the foreground it checks again within 5 seconds

#### Scenario: No checks when nothing is remembered

- **WHEN** the signed-in account has no remembered generation that is unsaved
- **THEN** the app makes no periodic status checks
