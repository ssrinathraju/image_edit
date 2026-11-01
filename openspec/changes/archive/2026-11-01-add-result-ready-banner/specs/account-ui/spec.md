## ADDED Requirements

### Requirement: Ask for an app update when the consent version is unknown

When the server's current consent version has no consent text in the app, the consent screen SHALL show "Update the app to continue" instead of the consent text, with no Accept action. Leaving the screen SHALL count as declining: nothing is submitted. This SHALL also apply when the server's current version changes to an unknown one while the consent screen is open.

#### Scenario: Unknown version on opening

- **WHEN** the consent screen opens and the server's current consent version has no text in the app
- **THEN** the screen shows "Update the app to continue" and no Accept action

#### Scenario: Version changes to an unknown one while open

- **WHEN** the consent screen is showing the consent text and the account is reloaded with a current version that has no text in the app
- **THEN** the screen shows "Update the app to continue" and no Accept action

#### Scenario: Leaving submits nothing

- **WHEN** the user goes back from the "Update the app to continue" screen
- **THEN** the form shows the same photo and prompt and no generation was submitted
