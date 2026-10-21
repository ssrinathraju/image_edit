## ADDED Requirements

### Requirement: Say how long the server keeps the result

When a generation has succeeded and the status response carries `expires_at`, the status screen SHALL show a note below the image, with the time shown as a date and time in the device's local time zone:
- once the image has been saved to My creations, it SHALL read "Saved to My creations on this device. Our copy is deleted on <date, time>.";
- if saving to My creations failed, it SHALL instead read "Not saved on this device. Download or share it before <date, time>, when it's deleted.";
- while the save is still in progress, or when `expires_at` is missing, no note SHALL be shown.

#### Scenario: Saved result shows the reassuring note

- **WHEN** a generation succeeds with `expires_at` and the image is saved to My creations
- **THEN** the status screen shows "Saved to My creations on this device. Our copy is deleted on" followed by the expiry in local date and time

#### Scenario: Unsaved result shows the warning

- **WHEN** a generation succeeds with `expires_at` and saving to My creations fails
- **THEN** the status screen shows "Not saved on this device. Download or share it before" followed by the expiry in local date and time, and "when it's deleted."

#### Scenario: No expiry, no note

- **WHEN** a generation succeeds and the status response has no `expires_at`
- **THEN** no expiry note is shown and the image, Download, Share, and Report are shown as before

#### Scenario: Local time zone is used

- **WHEN** the device is set to a time zone 5 hours 30 minutes ahead of UTC and `expires_at` is 2026-10-23T10:00:00Z
- **THEN** the note shows 23 October at 3:30 PM in the device's format
