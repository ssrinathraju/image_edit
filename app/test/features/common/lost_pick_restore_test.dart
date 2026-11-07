import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:image_edit/core/provider_sign_in.dart';
import 'package:image_edit/features/auth/session_notifier.dart';
import 'package:image_edit/features/common/clock.dart';
import 'package:image_edit/features/common/pending_pick_store.dart';
import 'package:image_edit/features/common/photo_picker_field.dart';
import 'package:image_edit/features/custom_generation/custom_generation_screen.dart';
import 'package:image_edit/features/home/home_screen.dart';
import 'package:image_edit/features/template_detail/template_screen.dart';
import 'package:image_edit/services/generation_providers.dart';
import 'package:image_picker/image_picker.dart';

import '../../support/fake_api_client.dart';
import '../../support/fake_image_picker.dart';
import '../../support/fake_pending_pick_store.dart';
import '../../support/fake_session_storage.dart';

const _keptMessage = 'We kept the photo you picked.';
final _started = DateTime.utc(2026, 1, 1, 12);

PendingPick _templateNote() => PendingPick(
  userId: 'user-1',
  kind: PendingPickKind.template,
  templateId: 'golden-hour-beach',
  startedAt: _started,
);

PendingPick _customNote({String userId = 'user-1'}) => PendingPick(
  userId: userId,
  kind: PendingPickKind.custom,
  prompt: 'astronaut on a beach',
  startedAt: _started,
);

class _Harness {
  _Harness({required this.picker, required this.store, required this.client});

  final FakeImagePicker picker;
  final FakePendingPickStore store;
  final FakeApiClient client;
}

Future<_Harness> _pumpHome(
  WidgetTester tester, {
  required FakeImagePicker picker,
  PendingPick? note,
  Duration sinceStart = const Duration(minutes: 5),
  TargetPlatform platform = TargetPlatform.android,
}) async {
  tester.view.physicalSize = const Size(430, 932);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final store = FakePendingPickStore(note: note);
  final client = FakeApiClient()
    ..onListTemplates = (_) async => [
      fakeTemplate('golden-hour-beach', title: 'Golden Hour Beach'),
    ];
  final router = GoRouter(
    routes: [
      GoRoute(path: '/', builder: (_, _) => const HomeScreen()),
      GoRoute(
        path: '/template/:id',
        builder: (_, state) => TemplateScreen(
          templateId: state.pathParameters['id']!,
          initialPhoto: state.extra is XFile ? state.extra! as XFile : null,
        ),
      ),
      GoRoute(
        path: '/create',
        builder: (_, state) => CustomGenerationScreen(
          initialPrompt: state.uri.queryParameters['prompt'] ?? '',
          initialPhoto: state.extra is XFile ? state.extra! as XFile : null,
        ),
      ),
    ],
  );
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(client),
        sessionStorageProvider.overrideWithValue(
          FakeSessionStorage(savedSession),
        ),
        imagePickerProvider.overrideWithValue(picker),
        pendingPickStoreProvider.overrideWithValue(store),
        targetPlatformProvider.overrideWithValue(platform),
        clockProvider.overrideWithValue(() => _started.add(sinceStart)),
      ],
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  await tester.pumpAndSettle();
  return _Harness(picker: picker, store: store, client: client);
}

FakeImagePicker _pickerWithLostPhoto() => FakeImagePicker(
  lost: LostDataResponse(
    file: XFile.fromData(tinyPng, name: 'lost.png'),
    type: RetrieveType.image,
  ),
);

void _expectOnHomeWithNothingKept(_Harness h) {
  expect(find.byType(HomeScreen), findsOneWidget);
  expect(find.text(_keptMessage), findsNothing);
  expect(h.store.note, isNull);
  expect(h.client.submitted, isEmpty);
}

bool _isGenerateEnabled(WidgetTester tester) =>
    tester
        .widget<FilledButton>(find.widgetWithText(FilledButton, 'Generate'))
        .onPressed !=
    null;

void main() {
  testWidgets('a template pick is restored with the photo and the message', (
    tester,
  ) async {
    final h = await _pumpHome(
      tester,
      picker: _pickerWithLostPhoto(),
      note: _templateNote(),
    );

    expect(find.byType(TemplateScreen), findsOneWidget);
    expect(find.text('Golden Hour Beach'), findsOneWidget);
    expect(find.text('Change photo'), findsOneWidget);
    expect(_isGenerateEnabled(tester), isTrue);
    expect(find.text(_keptMessage), findsOneWidget);
    expect(h.client.submitted, isEmpty);
    expect(h.store.note, isNull);
  });

  testWidgets('a custom pick is restored with its prompt and photo', (
    tester,
  ) async {
    final h = await _pumpHome(
      tester,
      picker: _pickerWithLostPhoto(),
      note: _customNote(),
    );

    expect(find.byType(CustomGenerationScreen), findsOneWidget);
    expect(find.text('astronaut on a beach'), findsOneWidget);
    expect(find.text('Change photo'), findsOneWidget);
    expect(_isGenerateEnabled(tester), isTrue);
    expect(find.text(_keptMessage), findsOneWidget);
    expect(h.client.submitted, isEmpty);
    expect(h.store.note, isNull);
  });

  testWidgets('back from a restored form returns to home', (tester) async {
    await _pumpHome(
      tester,
      picker: _pickerWithLostPhoto(),
      note: _customNote(),
    );

    await tester.pageBack();
    await tester.pumpAndSettle();

    expect(find.byType(HomeScreen), findsOneWidget);
  });

  testWidgets('another account: nothing opens and the note is dropped', (
    tester,
  ) async {
    final h = await _pumpHome(
      tester,
      picker: _pickerWithLostPhoto(),
      note: _customNote(userId: 'someone-else'),
    );

    expect(h.picker.retrieveCalls, 1);
    _expectOnHomeWithNothingKept(h);
  });

  testWidgets('more than an hour later: nothing opens, the note is dropped', (
    tester,
  ) async {
    final h = await _pumpHome(
      tester,
      picker: _pickerWithLostPhoto(),
      note: _templateNote(),
      sinceStart: const Duration(minutes: 61),
    );

    _expectOnHomeWithNothingKept(h);
  });

  testWidgets('just under an hour still restores', (tester) async {
    await _pumpHome(
      tester,
      picker: _pickerWithLostPhoto(),
      note: _templateNote(),
      sinceStart: const Duration(minutes: 59),
    );

    expect(find.byType(TemplateScreen), findsOneWidget);
  });

  testWidgets('cancelled picker: home opens normally, the note is dropped', (
    tester,
  ) async {
    final h = await _pumpHome(
      tester,
      picker: FakeImagePicker(),
      note: _templateNote(),
    );

    expect(h.picker.retrieveCalls, 1);
    _expectOnHomeWithNothingKept(h);
  });

  testWidgets('a lost error with no file counts as no file', (tester) async {
    final h = await _pumpHome(
      tester,
      picker: FakeImagePicker(
        lost: LostDataResponse(
          exception: PlatformException(code: 'camera_access_denied'),
        ),
      ),
      note: _templateNote(),
    );

    _expectOnHomeWithNothingKept(h);
  });

  testWidgets('a photo with no note is discarded', (tester) async {
    final h = await _pumpHome(tester, picker: _pickerWithLostPhoto());

    _expectOnHomeWithNothingKept(h);
  });

  testWidgets('retrieveLostData throwing is swallowed, the note dropped', (
    tester,
  ) async {
    final h = await _pumpHome(
      tester,
      picker: FakeImagePicker(lostError: StateError('plugin gone')),
      note: _templateNote(),
    );

    _expectOnHomeWithNothingKept(h);
  });

  testWidgets('iOS never asks for lost data and leaves home alone', (
    tester,
  ) async {
    final h = await _pumpHome(
      tester,
      picker: _pickerWithLostPhoto(),
      note: _templateNote(),
      platform: TargetPlatform.iOS,
    );

    expect(h.picker.retrieveCalls, 0);
    expect(find.byType(HomeScreen), findsOneWidget);
    expect(find.text(_keptMessage), findsNothing);
  });

  testWidgets('home shown a second time does not restore again', (
    tester,
  ) async {
    final h = await _pumpHome(
      tester,
      picker: FakeImagePicker(),
      note: _templateNote(),
    );

    final router = GoRouter.of(tester.element(find.byType(HomeScreen)));
    router.go('/create');
    await tester.pumpAndSettle();
    router.go('/');
    await tester.pumpAndSettle();

    expect(h.picker.retrieveCalls, 1);
  });
}
