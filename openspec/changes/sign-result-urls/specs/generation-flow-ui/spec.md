## ADDED Requirements

### Requirement: Reload a result image with a fresh link

When the status screen of a succeeded generation cannot load the image, its Reload action SHALL ask the server for the job's status again and load the image from the newly returned `result_url`, not from the link that failed. A link that has expired SHALL therefore be recoverable with Reload while the server still keeps the image.

#### Scenario: Reload after the link expired

- **WHEN** the status screen of a succeeded generation shows "Could not load the image." because its link expired, and the user taps Reload
- **THEN** the app requests the job's status again and shows the image from the new link

#### Scenario: Reload after the image was deleted

- **WHEN** the user taps Reload after the server's retention period has passed
- **THEN** the app shows an error with no image and still offers the way back home
