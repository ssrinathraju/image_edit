# onboarding Specification

## Purpose
Introduces the app to people on their first launch: what it does, how their photos and results are handled, and the rules for using it. They can see it again later from the profile.

## Requirements

### Requirement: Show onboarding on the first launch

On the first launch on a device, before the sign-in screen, the app SHALL show the onboarding pages. Once the user finishes or skips them, the app SHALL remember that on the device and SHALL NOT show them automatically again. A launch with a saved session SHALL NOT show onboarding, even if it was never seen.

#### Scenario: First launch

- **WHEN** the app is opened for the first time after installing
- **THEN** the first onboarding page is shown before the sign-in screen

#### Scenario: Later launches skip it

- **WHEN** the user has finished or skipped onboarding and opens the app again, signed out
- **THEN** the sign-in screen is shown directly

#### Scenario: Reinstalling shows it again

- **WHEN** the app is deleted and installed again
- **THEN** the next launch shows onboarding

#### Scenario: Signed-in launch is not interrupted

- **WHEN** the app launches with a saved session that the server accepts
- **THEN** the home screen is shown without onboarding

### Requirement: Explain the app in three pages

The onboarding SHALL have three pages that the user can move between by swiping or with Next, with an indicator showing which page is current:
1. **How it works:** pick a trending template or describe a scene, add a photo of yourself, and get a new image.
2. **Your privacy:** your photo is used for that one image and then deleted, results are saved on this device, and our copy is deleted after 24 hours.
3. **The rules:** you must be 18 or older, only upload photos of yourself or of people who agreed, and unsafe content is blocked.

#### Scenario: Paging forward and back

- **WHEN** the user taps Next on the first page and swipes back
- **THEN** the second page is shown, then the first again, with the indicator following

#### Scenario: Each page says its message

- **WHEN** the user views each page
- **THEN** the first mentions templates, describing a scene, and adding a photo; the second mentions that the photo is deleted, that results stay on the device, and that the server copy is deleted after 24 hours; the third mentions 18+, uploading only yourself or people who agreed, and that unsafe content is blocked

### Requirement: Skip or finish onboarding

Every page SHALL offer Skip. The last page SHALL offer Get started in place of Next. Skip and Get started SHALL both end onboarding and show the sign-in screen when it was shown at launch.

#### Scenario: Skip from the first page

- **WHEN** the user taps Skip on the first page
- **THEN** the sign-in screen is shown and onboarding is remembered as seen

#### Scenario: Get started on the last page

- **WHEN** the user reaches the third page and taps Get started
- **THEN** the sign-in screen is shown and onboarding is remembered as seen

### Requirement: Reopen onboarding from the profile

The profile screen SHALL offer a "How it works" row that opens the same onboarding pages. Skip, Get started, or going back SHALL return to the profile.

#### Scenario: Revisit from the profile

- **WHEN** a signed-in user taps "How it works" on the profile and then taps Get started on the last page
- **THEN** the profile screen is shown again and the user is still signed in

### Requirement: Never block the app on the onboarding record

If the app cannot read whether onboarding was seen, it SHALL show onboarding. If it cannot save that onboarding was seen, it SHALL continue to the sign-in screen anyway, and it MAY show onboarding again on the next launch.

#### Scenario: Unreadable record

- **WHEN** reading the onboarding record fails at launch
- **THEN** onboarding is shown

#### Scenario: Unsavable record

- **WHEN** saving the onboarding record fails after Get started
- **THEN** the sign-in screen is shown
