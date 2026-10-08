# Tasks

## 1. Project Scaffold

- [x] 1.1 Run `flutter create . --org com.imageedit --project-name image_edit` in `app/`; verify `app/lib/main.dart` exists and `flutter run` compiles
- [x] 1.2 Replace generated `app/lib/main.dart` boilerplate with a minimal app shell (no counter demo); verify `flutter analyze` passes with no errors
- [x] 1.3 Add iOS photo library permission to `app/ios/Runner/Info.plist` (`NSPhotoLibraryUsageDescription`); add `READ_MEDIA_IMAGES` permission to `app/android/app/src/main/AndroidManifest.xml`; verify `flutter build apk --debug` completes without permission warnings

## 2. Dependencies

- [x] 2.1 Add to `app/pubspec.yaml`: `flutter_riverpod`, `go_router`, `dio`, `image_picker`, `flutter_dotenv`; run `flutter pub get`; verify no version conflicts
- [x] 2.2 Create `app/.env.example` with `API_BASE_URL=http://localhost:8000`; create `app/.env` with the same default; add `app/.env` to `app/.gitignore`; add `app/.env` as a Flutter asset in `pubspec.yaml`; verify `flutter pub get` still passes

## 3. Config and Core

- [x] 3.1 Create `app/lib/configs/app_config.dart` that loads `API_BASE_URL` from `.env` via `flutter_dotenv`; verify it reads the value at app startup without throwing
- [x] 3.2 Create `app/lib/schemas/job.dart` with `JobStatus` enum (`queued`, `running`, `succeeded`, `failed`) and `GenerationJob` model (`jobId`, `status`, `resultUrl`, `error`); verify `dart analyze` passes
- [x] 3.3 Create `app/lib/core/api_client.dart` with `GenerationApiClient` abstract class (methods: `submitGeneration`, `getJobStatus`, `getResultImageUrl`) and `DioApiClient` implementation using `dio`; verify `dart analyze` passes

## 4. Generation Service

- [x] 4.1 Create `app/lib/services/generation_service.dart` that wraps `GenerationApiClient`: `submit(List<XFile> faces, String prompt) -> String jobId`; `getStatus(String jobId) -> GenerationJob`; verify the service can be instantiated in a unit test with a mock client

## 5. New Generation Screen

- [x] 5.1 Create `app/lib/features/new_generation/new_generation_notifier.dart` (`AsyncNotifier`) managing: selected face list, prompt text, submit disabled state; verify `dart analyze` passes
- [x] 5.2 Create `app/lib/features/new_generation/new_generation_screen.dart` with: face photo grid (tappable to add via `image_picker`), prompt `TextField`, character counter, Submit button (disabled when invalid); verify screen renders in `flutter run` without errors
- [x] 5.3 Wire submit: on tap, call `GenerationService.submit`, navigate to `/status/:jobId` via `go_router`, show error snackbar on failure; verify end-to-end by submitting to a running backend and confirming navigation

## 6. Generation Status Screen

- [x] 6.1 Create `app/lib/features/generation_status/generation_status_notifier.dart` that polls `GenerationService.getStatus` every 2 seconds, cancels on dispose or terminal state; verify polling stops when notifier is disposed
- [x] 6.2 Create `app/lib/features/generation_status/generation_status_screen.dart` showing: progress indicator for `queued`/`running`, full-width image for `succeeded`, error message + "New Generation" button for `failed`; verify screen renders for each state
- [x] 6.3 Wire `go_router` routes: `/` → `NewGenerationScreen`, `/status/:jobId` → `GenerationStatusScreen`; verify back navigation clears the new generation form

## 7. Integration Smoke Test

- [x] 7.1 Run `flutter analyze` on the whole `app/` project; verify zero errors and zero warnings
- [x] 7.2 With the backend running (`MODEL_BACKEND=sana` or `stub`), launch the app in the iOS simulator or Android emulator, select a photo, enter a prompt, submit, and verify the status screen polls and displays the final image (or solid color for stub)

## 8. Documentation

- [x] 8.1 Create `app/README.md` with: prerequisites (Flutter SDK, Xcode/Android Studio), setup steps (`flutter pub get`, copy `.env.example` to `.env`, set `API_BASE_URL`), and run commands for iOS simulator and Android emulator
