## Purpose

Keeps a private, on-device record of the images a user has generated, so they can find, download, share or delete past results after the server has discarded them.

## ADDED Requirements

### Requirement: Save a finished generation on the device

When a generation succeeds while its status screen is open, the app SHALL save the image to its private storage on the device. With it, the app SHALL record the job id, the signed-in account, the prompt or template title used, and the time the generation finished. The app SHALL save each job at most once.

#### Scenario: Watched generation is saved

- **WHEN** a user submits a generation with the prompt "astronaut on a beach" and waits on the status screen until it succeeds
- **THEN** My creations contains that image labelled "astronaut on a beach"

#### Scenario: Template generation is labelled with the template

- **WHEN** a user starts a generation from the "Golden Hour Beach" template and it succeeds
- **THEN** the saved creation is labelled "Golden Hour Beach"

#### Scenario: Reopening the status screen does not duplicate

- **WHEN** a succeeded generation's status screen is opened a second time
- **THEN** My creations still holds exactly one creation for that job

### Requirement: Keep the result visible when saving fails

A failure to save a creation SHALL NOT change what the status screen shows for the generation. The app SHALL show a short message that the image could not be saved to My creations, and Download and Share on the status screen SHALL keep working.

#### Scenario: Storage error does not hide the result

- **WHEN** a generation succeeds and writing the image to the device fails
- **THEN** the status screen shows the generated image with Download and Share
- **AND** a message says it could not be saved to My creations

### Requirement: Catch up on generations finished while away

The app SHALL remember every generation the signed-in account submits. Whenever the home screen or the My creations screen opens, the app SHALL check each remembered generation that has not been saved:
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

### Requirement: Show only the signed-in account's creations

My creations SHALL show only the creations saved for the signed-in account. Signing out SHALL NOT delete any creation. Signing in to the same account again SHALL show its creations again.

#### Scenario: Another account on the same device sees nothing of the first

- **WHEN** account A has 3 creations, signs out, and account B signs in on the same device
- **THEN** My creations for B is empty

#### Scenario: Creations return after signing in again

- **WHEN** account A signs out and later signs in again on the same device
- **THEN** My creations shows A's 3 creations

### Requirement: Keep the newest 50 creations

The app SHALL keep at most 50 creations per account on the device. When saving a creation would exceed 50, the app SHALL delete the oldest creation of that account, including its image file.

#### Scenario: Fifty-first creation removes the oldest

- **WHEN** an account has 50 creations and a new generation is saved
- **THEN** the account still has 50 creations
- **AND** the oldest one and its image file are gone

### Requirement: Remove creations with the account

When the user deletes their account from the app, the app SHALL delete that account's creations, their image files, and its remembered generations from the device.

#### Scenario: Deleted account leaves nothing on the device

- **WHEN** a user with creations deletes their account
- **THEN** no creation, image file, or remembered generation of that account remains on the device

### Requirement: Keep creations out of device backups

The app SHALL exclude the stored creations from iCloud backups on iOS and from Android cloud backups and device transfers.

#### Scenario: Backup excludes creations

- **WHEN** the device is backed up and restored to a new phone
- **THEN** My creations on the new phone is empty

### Requirement: Open My creations from the home screen

The home screen SHALL provide a My creations control that opens the My creations screen, and the My creations screen SHALL provide a way back to the home screen.

#### Scenario: My creations is reachable and returnable

- **WHEN** the user taps My creations on the home screen
- **THEN** the My creations screen is shown
- **AND** the user can return to the home screen from it

### Requirement: Show creations as a grid

The My creations screen SHALL show the signed-in account's creations as a grid of images, newest first. With no creations it SHALL show a message that creations will appear there.

#### Scenario: Newest creation is first

- **WHEN** an account has creations finished on Monday and on Tuesday
- **THEN** the Tuesday creation appears before the Monday creation

#### Scenario: Empty state

- **WHEN** an account has no creations
- **THEN** the screen shows "Your creations will appear here"

### Requirement: View a creation

Tapping a creation SHALL open a detail screen that shows the image at full width with its aspect ratio kept, its label, and the date it was finished, read from the device without contacting the server.

#### Scenario: Detail shows image, label and date

- **WHEN** the user taps a creation labelled "astronaut on a beach"
- **THEN** the detail screen shows the image, "astronaut on a beach", and its date

#### Scenario: Detail works offline

- **WHEN** the device has no network access and the user opens a creation
- **THEN** the image is shown

### Requirement: Download and share a creation

The detail screen SHALL offer Download, which saves the stored image to the device photo library with the same confirmation and permission message as the status screen, and Share, which opens the system share sheet with the stored image attached. Both SHALL work without network access.

#### Scenario: Download from history

- **WHEN** the user taps Download on a creation and photo library permission is granted
- **THEN** the image is saved to the photo library and the app confirms it

#### Scenario: Share from history offline

- **WHEN** the device has no network access and the user taps Share on a creation
- **THEN** the system share sheet opens with the image attached

### Requirement: Delete a creation

The detail screen SHALL offer Delete, which asks for confirmation and then removes the creation and its image file from the device and returns to the grid. Cancelling SHALL change nothing.

#### Scenario: Confirmed delete removes the creation

- **WHEN** the user taps Delete on a creation and confirms
- **THEN** the grid is shown without that creation and its image file is gone

#### Scenario: Cancelled delete keeps the creation

- **WHEN** the user taps Delete and cancels
- **THEN** the creation is still shown

### Requirement: Recover from a missing or unreadable creation

If a creation's image file is missing or cannot be read, the grid SHALL show a placeholder for it, and the detail screen SHALL say the image is unavailable and still offer Delete.

#### Scenario: Missing file shows a placeholder

- **WHEN** a creation's image file has been removed outside the app
- **THEN** the grid shows a placeholder in its place
- **AND** opening it says the image is unavailable and offers Delete
