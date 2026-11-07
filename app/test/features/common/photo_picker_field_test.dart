import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/common/photo_picker_field.dart';
import 'package:image_edit/core/provider_sign_in.dart';
import 'package:image_edit/features/auth/session_notifier.dart';
import 'package:image_edit/features/common/clock.dart';
import 'package:image_edit/features/common/pending_pick_store.dart';
import 'package:image_edit/services/app_settings.dart';
import 'package:image_edit/services/generation_providers.dart';
import 'package:image_picker/image_picker.dart';

import '../../support/fake_api_client.dart';
import '../../support/fake_app_settings.dart';
import '../../support/fake_image_picker.dart';
import '../../support/fake_pending_pick_store.dart';
import '../../support/fake_session_storage.dart';

final _now = DateTime.utc(2026, 1, 1, 12);

Future<ProviderContainer> _pump(
  WidgetTester tester,
  FakeImagePicker picker, {
  FakeAppSettings? settings,
  PickOrigin origin = const PickOrigin.template('golden-hour-beach'),
  TargetPlatform platform = TargetPlatform.iOS,
  PendingPickStore? pendingPicks,
}) async {
  final container = ProviderContainer(
    overrides: [
      imagePickerProvider.overrideWithValue(picker),
      appSettingsProvider.overrideWithValue(settings ?? FakeAppSettings()),
      targetPlatformProvider.overrideWithValue(platform),
      clockProvider.overrideWithValue(() => _now),
      apiClientProvider.overrideWithValue(FakeApiClient()),
      sessionStorageProvider.overrideWithValue(FakeSessionStorage(savedSession)),
      if (pendingPicks != null)
        pendingPickStoreProvider.overrideWithValue(pendingPicks),
    ],
  );
  addTearDown(container.dispose);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        home: Scaffold(body: Center(child: PhotoPickerField(origin: origin))),
      ),
    ),
  );
  await container.read(sessionProvider.future);
  return container;
}

void main() {
  testWidgets('shows the empty state, then the preview after picking', (tester) async {
    final photo = XFile.fromData(tinyPng, name: 'me.png');
    final picker = FakeImagePicker(result: photo);
    final container = await _pump(tester, picker);
    expect(find.text('Add your photo'), findsOneWidget);

    await tester.tap(find.byType(PhotoPickerField));
    await tester.pumpAndSettle();
    expect(find.text('Take photo'), findsOneWidget);
    await tester.tap(find.text('Choose from library'));
    await tester.pumpAndSettle();

    expect(picker.sources, [ImageSource.gallery]);
    expect(container.read(selectedPhotoProvider), same(photo));
    expect(find.text('Change photo'), findsOneWidget);
    expect(find.text('Add your photo'), findsNothing);
  });

  testWidgets('camera failure shows a message and keeps the library option', (tester) async {
    final picker = FakeImagePicker(error: Exception('no camera'));
    final container = await _pump(tester, picker);

    await tester.tap(find.byType(PhotoPickerField));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Take photo'));
    await tester.pumpAndSettle();

    expect(find.textContaining('camera is not available'), findsOneWidget);
    expect(container.read(selectedPhotoProvider), isNull);

    await tester.tap(find.byType(PhotoPickerField));
    await tester.pumpAndSettle();
    expect(find.text('Choose from library'), findsOneWidget);
  });

  group('denied access', () {
    Future<void> choose(WidgetTester tester, String source) async {
      await tester.tap(find.byType(PhotoPickerField));
      await tester.pumpAndSettle();
      await tester.tap(find.text(source));
      await tester.pumpAndSettle();
    }

    testWidgets('camera denied shows the dialog with three actions', (
      tester,
    ) async {
      final picker = FakeImagePicker(
        error: PlatformException(code: 'camera_access_denied'),
      );
      final container = await _pump(tester, picker);

      await choose(tester, 'Take photo');

      expect(find.textContaining('Camera access is off'), findsOneWidget);
      expect(find.text('Open Settings'), findsOneWidget);
      expect(find.text('Choose from library'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);
      expect(find.byType(SnackBar), findsNothing);
      expect(container.read(selectedPhotoProvider), isNull);
    });

    testWidgets('Choose from library in the dialog runs the gallery pick', (
      tester,
    ) async {
      final picker = FakeImagePicker(
        error: PlatformException(code: 'camera_access_denied'),
        errorSource: ImageSource.camera,
        result: XFile.fromData(tinyPng, name: 'me.png'),
      );
      final container = await _pump(tester, picker);

      await choose(tester, 'Take photo');
      await tester.tap(find.text('Choose from library'));
      await tester.pumpAndSettle();

      expect(picker.sources, [ImageSource.camera, ImageSource.gallery]);
      expect(container.read(selectedPhotoProvider), isNotNull);
    });

    testWidgets(
      'Open Settings calls the settings channel and keeps the photo',
      (tester) async {
        final settings = FakeAppSettings();
        final existing = XFile.fromData(tinyPng, name: 'old.png');
        final picker = FakeImagePicker(
          error: PlatformException(code: 'camera_access_denied'),
        );
        final container = await _pump(tester, picker, settings: settings);
        container.read(selectedPhotoProvider.notifier).state = existing;
        await tester.pump();

        await choose(tester, 'Take photo');
        await tester.tap(find.text('Open Settings'));
        await tester.pumpAndSettle();

        expect(settings.openCount, 1);
        expect(container.read(selectedPhotoProvider), same(existing));
      },
    );

    testWidgets('Cancel closes the dialog and opens nothing', (tester) async {
      final settings = FakeAppSettings();
      final picker = FakeImagePicker(
        error: PlatformException(code: 'camera_access_denied'),
      );
      await _pump(tester, picker, settings: settings);

      await choose(tester, 'Take photo');
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Camera access is off'), findsNothing);
      expect(settings.openCount, 0);
      expect(picker.sources, [ImageSource.camera]);
    });

    testWidgets('library denied shows the photo dialog with two actions', (
      tester,
    ) async {
      final settings = FakeAppSettings();
      final picker = FakeImagePicker(
        error: PlatformException(code: 'photo_access_denied'),
      );
      await _pump(tester, picker, settings: settings);

      await choose(tester, 'Choose from library');

      expect(find.textContaining('Photo access is off'), findsOneWidget);
      expect(find.text('Open Settings'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);
      expect(find.text('Choose from library'), findsNothing);

      await tester.tap(find.text('Open Settings'));
      await tester.pumpAndSettle();
      expect(settings.openCount, 1);
    });

    testWidgets('Open Settings failing says so', (tester) async {
      final picker = FakeImagePicker(
        error: PlatformException(code: 'photo_access_denied'),
      );
      await _pump(tester, picker, settings: FakeAppSettings(opens: false));

      await choose(tester, 'Choose from library');
      await tester.tap(find.text('Open Settings'));
      await tester.pumpAndSettle();

      expect(find.text('Could not open Settings.'), findsOneWidget);
    });

    testWidgets('another platform error keeps the camera message', (
      tester,
    ) async {
      final picker = FakeImagePicker(
        error: PlatformException(code: 'no_available_camera'),
      );
      await _pump(tester, picker);

      await choose(tester, 'Take photo');

      expect(find.textContaining('camera is not available'), findsOneWidget);
      expect(find.text('Open Settings'), findsNothing);
    });

    testWidgets('a platform error on the library keeps the library message', (
      tester,
    ) async {
      final picker = FakeImagePicker(
        error: PlatformException(code: 'camera_access_denied'),
      );
      await _pump(tester, picker);

      await choose(tester, 'Choose from library');

      expect(find.text('Could not open the photo library.'), findsOneWidget);
      expect(find.text('Open Settings'), findsNothing);
    });
  });

  group('pending note', () {
    late FakePendingPickStore store;

    setUp(() => store = FakePendingPickStore());

    Future<void> chooseLibrary(WidgetTester tester) async {
      await tester.tap(find.byType(PhotoPickerField));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Choose from library'));
      await tester.pumpAndSettle();
    }

    testWidgets('Android writes the template note while the picker is open', (tester) async {
      PendingPick? during;
      final picker = FakeImagePicker(
        result: XFile.fromData(tinyPng, name: 'me.png'),
        duringPick: () async => during = store.note,
      );
      await _pump(
        tester,
        picker,
        platform: TargetPlatform.android,
        pendingPicks: store,
      );

      await chooseLibrary(tester);

      expect(during!.userId, 'user-1');
      expect(during!.kind, PendingPickKind.template);
      expect(during!.templateId, 'golden-hour-beach');
      expect(during!.startedAt, _now);
      expect(store.note, isNull);
    });

    testWidgets('Android writes the custom prompt as typed so far', (tester) async {
      PendingPick? during;
      final picker = FakeImagePicker(
        duringPick: () async => during = store.note,
      );
      await _pump(
        tester,
        picker,
        origin: PickOrigin.custom(() => 'astronaut on a beach'),
        platform: TargetPlatform.android,
        pendingPicks: store,
      );

      await chooseLibrary(tester);

      expect(during!.kind, PendingPickKind.custom);
      expect(during!.prompt, 'astronaut on a beach');
    });

    testWidgets('iOS never writes a note', (tester) async {
      var existedDuringPick = false;
      final picker = FakeImagePicker(
        duringPick: () async => existedDuringPick = store.note != null,
      );
      await _pump(tester, picker, pendingPicks: store);

      await chooseLibrary(tester);

      expect(existedDuringPick, isFalse);
      expect(store.note, isNull);
    });

    testWidgets('the note is gone after a pick', (tester) async {
      final picker = FakeImagePicker(
        result: XFile.fromData(tinyPng, name: 'me.png'),
      );
      await _pump(tester, picker, platform: TargetPlatform.android, pendingPicks: store);

      await chooseLibrary(tester);

      expect(store.note, isNull);
    });

    testWidgets('the note is gone after the user cancels', (tester) async {
      final picker = FakeImagePicker();
      await _pump(tester, picker, platform: TargetPlatform.android, pendingPicks: store);

      await chooseLibrary(tester);

      expect(picker.sources, [ImageSource.gallery]);
      expect(store.note, isNull);
    });

    testWidgets('the note is gone after a failure', (tester) async {
      final picker = FakeImagePicker(error: Exception('boom'));
      await _pump(tester, picker, platform: TargetPlatform.android, pendingPicks: store);

      await chooseLibrary(tester);

      expect(find.text('Could not open the photo library.'), findsOneWidget);
      expect(store.note, isNull);
    });

    testWidgets('the note is gone after a denial', (tester) async {
      final picker = FakeImagePicker(
        error: PlatformException(code: 'photo_access_denied'),
      );
      await _pump(tester, picker, platform: TargetPlatform.android, pendingPicks: store);

      await chooseLibrary(tester);

      expect(find.textContaining('Photo access is off'), findsOneWidget);
      expect(store.note, isNull);
    });

    testWidgets('a signed-out picker writes nothing and still picks', (tester) async {
      var existedDuringPick = false;
      final picker = FakeImagePicker(
        result: XFile.fromData(tinyPng, name: 'me.png'),
        duringPick: () async => existedDuringPick = store.note != null,
      );
      final container = await _pump(
        tester,
        picker,
        platform: TargetPlatform.android,
        pendingPicks: store,
      );
      await container.read(sessionProvider.notifier).signOut();

      await chooseLibrary(tester);

      expect(existedDuringPick, isFalse);
      expect(container.read(selectedPhotoProvider), isNotNull);
    });
  });
}
