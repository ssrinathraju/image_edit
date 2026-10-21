## ADDED Requirements

### Requirement: Report a creation

The creation detail screen SHALL offer Report, with the same sheet, categories, note limit, confirmation and refusal messages as reporting from the status screen. It SHALL send the creation's job id and its stored image, so it works at any age of the creation, and it SHALL need network access only for sending.

#### Scenario: Report an old creation

- **WHEN** the user opens a creation made three days ago, taps Report, chooses Other, and taps Send
- **THEN** the app sends the report with the job id and the stored image
- **AND** shows "Thanks, we'll review it."

#### Scenario: Report offline

- **WHEN** the device has no network access and the user taps Send on a report
- **THEN** the sheet stays open and says the report could not be sent, with the category and note kept
