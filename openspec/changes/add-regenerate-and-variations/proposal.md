# Proposal

## Why

Image generation is hit and miss: users often want another take on a result they like, or a small change to the wording. Today the status screen has a single Retry. It looks the same after a success and a failure. Custom prompts can't be tweaked without retyping and picking the photo again. A saved creation in My creations offers no way back to its template or prompt.

## What Changes

- **More like this / Try again:** the status screen's Retry reads "More like this" after a success and "Try again" after a failure. It works as before: same photo, same template or prompt, a new job, one generation counted. The pipeline already samples a fresh random seed each run, so each variation differs.
- **Edit prompt:** for custom-prompt generations, the status screen also offers "Edit prompt". It opens the custom form with the same photo and prompt filled in, on top of the result.
- **Make another:** the creation detail screen offers "Make another". It opens the template screen or the custom form, prefilled with the template or prompt. The user picks the photo again, because the app never keeps face photos.
- **Creations record their source:** each creation and pending entry now records whether it came from a custom prompt (and which) or a template (and its id). Older entries have no source and no Make another.

Out of scope:
- several images per job, and choosing among them;
- a user-visible or reproducible seed;
- keeping input photos on the device;
- any server change, and any change to quota, consent or safety rules (each new job is a normal submission).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `generation-flow-ui`: Retry gets outcome-specific labels and stated availability, and a new "Edit prompt" requirement is added.
- `creation-history`: saved creations record their source, and a new "Make another" requirement is added.

## Impact

- **App only:**
  - `schemas/creation.dart` (an optional source on `Creation` and `PendingGeneration`);
  - `features/history/` (the store, catch-up and detail screen);
  - `features/generation_status/generation_status_screen.dart`;
  - `features/custom_generation/custom_generation_screen.dart` and `router.dart` (a prefilled photo);
  - `features/common/submit_flow.dart` (remember the source).
- **Existing on-device data:** old `index.json` and pending entries still read, with no source.
- **Server:** unchanged. No new dependencies.
