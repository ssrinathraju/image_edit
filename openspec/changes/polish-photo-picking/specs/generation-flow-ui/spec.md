## MODIFIED Requirements

### Requirement: Download the generated image

When a generation has succeeded, the Generation Status screen SHALL offer a Download action that saves the generated image to the device photo library and confirms success. If the user denies photo library permission, the app SHALL explain that permission is needed and SHALL offer an Open Settings action that opens this app's page in the device settings.

#### Scenario: Download saves to the photo library

- **WHEN** the user taps Download on a succeeded generation and permission is granted
- **THEN** the image is saved to the photo library and the app shows a confirmation

#### Scenario: Permission denied is explained

- **WHEN** the user taps Download and denies photo library permission
- **THEN** the app shows a message that photo library access is required to save

#### Scenario: Open Settings after a denied download

- **WHEN** the download was refused for photo library permission and the user taps Open Settings
- **THEN** the device settings open on this app's page

## ADDED Requirements

### Requirement: Explain denied camera or photo access

When the device refuses camera access after the user chose "Take photo", the app SHALL show a dialog saying camera access is off and can be turned on in Settings, with the actions Open Settings, Choose from library, and Cancel. When the device refuses photo library access after the user chose "Choose from library", the app SHALL show a dialog saying photo access is off, with Open Settings and Cancel. Open Settings SHALL open this app's page in the device settings. Any other failure to open the camera or library SHALL keep the existing messages. The form's prompt and any photo already chosen SHALL be kept.

#### Scenario: Camera access denied

- **WHEN** the user chooses "Take photo" and the device refuses camera access
- **THEN** the app shows the camera dialog with Open Settings, Choose from library, and Cancel

#### Scenario: Choose from library instead

- **WHEN** the camera dialog is shown and the user taps Choose from library
- **THEN** the photo library opens

#### Scenario: Open Settings from the dialog

- **WHEN** the user taps Open Settings in either dialog
- **THEN** the device settings open on this app's page and the form keeps its prompt and photo

#### Scenario: Photo library access denied

- **WHEN** the user chooses "Choose from library" and the device refuses photo access
- **THEN** the app shows the photo dialog with Open Settings and Cancel

#### Scenario: Camera missing is not a permission problem

- **WHEN** the device has no camera or it fails to open for another reason
- **THEN** the app shows the existing message suggesting the photo library, not the Settings dialog

### Requirement: Restore a photo picked while Android closed the app

On Android, before opening the camera or photo library, the app SHALL remember on the device which form it was opened from (the template, or the custom form with its prompt) and which account is signed in. If Android closes the app while the camera or library is open and the user then picks or takes a photo, the next time the app starts and reaches the home screen for that same account it SHALL reopen that form with the photo selected and the prompt filled in, and SHALL say "We kept the photo you picked." Nothing SHALL be submitted. The remembered form SHALL be forgotten once used, when a pick completes normally, when the user signs out, or after one hour. A photo recovered without a matching remembered form, for another account, or after one hour SHALL be discarded.

#### Scenario: Photo restored into the template form

- **WHEN** a user opens the "golden-hour-beach" template, chooses "Take photo", Android closes the app, and the user takes a picture
- **THEN** after the app restarts and reaches home, the "golden-hour-beach" template screen opens with that picture selected and the message "We kept the photo you picked."
- **AND** no generation has been submitted

#### Scenario: Photo and prompt restored into the custom form

- **WHEN** a user types "astronaut on a beach" in the custom form, chooses "Choose from library", Android closes the app, and the user picks a photo
- **THEN** after the restart the custom form opens with "astronaut on a beach" and that photo

#### Scenario: Different account after restart

- **WHEN** the app restarts signed in to a different account than the one that started the pick
- **THEN** no form is reopened and the photo is discarded

#### Scenario: Too late

- **WHEN** the app restarts more than one hour after the pick was started
- **THEN** no form is reopened and the photo is discarded

#### Scenario: User cancelled the picker

- **WHEN** Android closed the app while the camera was open and the user cancelled without taking a picture
- **THEN** the app starts normally on home and the remembered form is forgotten

#### Scenario: Normal pick leaves nothing behind

- **WHEN** the user picks a photo and the app was not closed
- **THEN** the photo is shown as usual and the remembered form is forgotten
