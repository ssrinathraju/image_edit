# image_edit — Flutter App

## Prerequisites

- Flutter SDK ≥ 3.13 (`flutter --version`)
- For iOS: Xcode 15+ with an iOS simulator
- For Android: Android Studio with an Android emulator (API 33+)
- For web: Chrome (already installed on most machines)
- A running instance of the image_edit backend (see `server/README.md`)

## Setup

```bash
flutter pub get
cp .env.example .env
```

Edit `.env` and set `API_BASE_URL` to point at your backend:

```
API_BASE_URL=http://localhost:8000
```

## Run

**Chrome (no simulator required):**

```bash
flutter run -d chrome
```

**iOS simulator:**

```bash
flutter run -d <simulator-device-id>
# List available simulators:
flutter devices
```

**Android emulator:**

```bash
flutter run -d <emulator-device-id>
# List available emulators:
flutter devices
```

## Test

```bash
flutter test
```

## Analyze

```bash
flutter analyze
```
