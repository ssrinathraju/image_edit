# Design

## Context

See `proposal.md — Why`. The backend exposes three endpoints the app needs: `POST /generations` (multipart), `GET /generations/{job_id}` (poll), and `GET /images/{job_id}.png` (result image). No auth. Backend URL is configurable.

## Goals / Non-Goals

**Goals:**
- Working two-screen Flutter app: New Generation → Generation Status
- API client layer isolated behind an interface (swappable for tests)
- Local validation mirroring backend rules (1–4 faces, prompt length)
- Polling loop that stops cleanly on terminal state or screen disposal

**Non-Goals:**
- Generation history / persistence
- Authentication UI (deferred)
- Face conditioning preview or editing
- Offline mode or local caching of results
- Tablet or web layout optimization

## Decisions

### 1. State management: Riverpod

Riverpod handles async state (submission, polling) cleanly with `AsyncNotifier` and auto-cancels when the provider is disposed — which stops the polling loop for free when the user navigates away. BLoC would work too but adds more boilerplate for a two-screen app.

### 2. HTTP client: `dio`

`dio` handles multipart file uploads (`FormData`) and image downloads with less ceremony than the base `http` package. One `Dio` instance is injected via Riverpod provider.

### 3. Routing: `go_router`

Declarative, URL-based routing that works well with deep links and future additions. Route `/` → New Generation screen; route `/status/:jobId` → Generation Status screen.

### 4. Image picker: `image_picker`

Standard Flutter plugin for accessing the device gallery on iOS and Android. Returns `XFile` objects that are passed directly to `dio`'s `MultipartFile`.

### 5. Backend URL config: `flutter_dotenv`

Reads a `.env` file at app startup. `.env` is gitignored; `.env.example` is checked in. Default: `API_BASE_URL=http://localhost:8000`. On a real device, set to the LAN IP of the dev box.

### 6. Folder structure (`app/lib/`)

```
lib/
  configs/          # AppConfig, env loading
  core/
    api_client.dart # GenerationApiClient interface + DioApiClient impl
  schemas/          # Dart models: GenerationJob, JobStatus
  services/
    generation_service.dart  # submit(), getStatus(), getResultUrl()
  features/
    new_generation/
      new_generation_screen.dart
      new_generation_notifier.dart
    generation_status/
      generation_status_screen.dart
      generation_status_notifier.dart
  main.dart
  router.dart
```

Mirrors the server's layered layout (configs → core → schemas → services → features).

### 7. Polling implementation

`GenerationStatusNotifier` (an `AsyncNotifier`) starts a `Timer.periodic(2s)` on build and cancels it in `dispose`. On each tick it calls `GenerationService.getStatus()` and updates state. When status is terminal it cancels the timer.

### 8. iOS / Android permissions

`image_picker` requires `NSPhotoLibraryUsageDescription` in `ios/Runner/Info.plist` and `READ_MEDIA_IMAGES` in `android/app/src/main/AndroidManifest.xml`. Added during scaffold tasks.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| `localhost:8000` unreachable from a physical device | Document: set `API_BASE_URL` to the dev box LAN IP in `.env` |
| iOS simulator can reach localhost; Android emulator needs `10.0.2.2` | Document both in README; make URL fully configurable |
| Polling 2s intervals on a slow network can stack up | Use a flag to skip the tick if previous request is still in flight |

## Open Questions

_(none — all design decisions are resolved)_
