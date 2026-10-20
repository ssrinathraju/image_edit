import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/auth/session_notifier.dart';
import 'package:image_edit/features/custom_generation/custom_generation_screen.dart';
import 'package:image_edit/features/common/clock.dart';
import 'package:image_edit/features/template_detail/template_screen.dart';
import 'package:image_edit/features/plans/account_notifier.dart';
import 'package:image_edit/schemas/session.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_session_storage.dart';
import '../../support/in_memory_creation_store.dart';
import '../../support/screen_harness.dart';

late FakeApiClient client;

final _now = DateTime.utc(2026, 10, 19, 8);

Future<void> _pumpCustom(WidgetTester tester, {InMemoryCreationStore? store}) =>
    pumpScreen(
      tester,
      client: client,
      store: store,
      screen: const CustomGenerationScreen(),
      overrides: [
        sessionStorageProvider.overrideWithValue(FakeSessionStorage(savedSession)),
        clockProvider.overrideWithValue(() => _now),
      ],
    );

Future<void> _pumpTemplate(WidgetTester tester, InMemoryCreationStore store) =>
    pumpScreen(
      tester,
      client: client,
      store: store,
      screen: TemplateScreen(
        templateId: 'golden-hour',
        template: fakeTemplate('golden-hour', title: 'Golden Hour Beach'),
      ),
      overrides: [
        sessionStorageProvider.overrideWithValue(FakeSessionStorage(savedSession)),
        clockProvider.overrideWithValue(() => _now),
      ],
    );

/// Loads the session and account up front, as the running app has by the time
/// anyone taps Generate.
Future<void> _primeAccount(WidgetTester tester) async {
  final container = ProviderScope.containerOf(tester.element(find.byType(MaterialApp)));
  container.read(accountProvider);
  // Futures only advance when the fake-async test zone is pumped.
  for (var i = 0; i < 50 && container.read(accountProvider).valueOrNull == null; i++) {
    await tester.pump(const Duration(milliseconds: 10));
  }
  expect(container.read(accountProvider).valueOrNull, isNotNull);
}

Future<void> _generate(WidgetTester tester) async {
  await tester.enterText(find.byType(TextField), 'a cat in space');
  await tester.pump();
  await pickPhoto(tester);
  await tester.tap(find.text('Generate'));
  await tester.pumpAndSettle();
}

void main() {
  _safetyTests();

  setUp(() {
    client = FakeApiClient();
    client.onFetchMe = () async => fakeProfile(
          usedToday: 3,
          resetsAt: DateTime.utc(2026, 10, 17, 9, 30),
        );
    client.onSubmit = (_) async => throw apiError(
          429,
          'quota_exceeded',
          'the daily generation limit has been reached',
        );
  });

  testWidgets('a refused generation explains the limit and the reset time', (tester) async {
    await _pumpCustom(tester);

    await _generate(tester);

    expect(find.text('Daily limit reached'), findsOneWidget);
    expect(find.textContaining('reset'), findsOneWidget);
    expect(find.text('Upgrade'), findsOneWidget);
    expect(find.text('Invite friends'), findsOneWidget);
  });

  testWidgets('the photo and prompt are kept after the dialog closes', (tester) async {
    await _pumpCustom(tester);
    await _generate(tester);

    await tester.tap(find.text('Close'));
    await tester.pumpAndSettle();

    final field = tester.widget<TextField>(find.byType(TextField));
    expect(field.controller!.text, 'a cat in space');
    expect(isGenerateEnabled(tester), isTrue);
    expect(find.text('status:job-1'), findsNothing);
  });

  testWidgets('Upgrade opens the upgrade screen', (tester) async {
    await _pumpCustom(tester);
    await _generate(tester);

    await tester.tap(find.widgetWithText(FilledButton, 'Upgrade'));
    await tester.pumpAndSettle();

    expect(find.text('upgrade-screen'), findsOneWidget);
  });

  testWidgets('Invite friends opens the invite screen', (tester) async {
    await _pumpCustom(tester);
    await _generate(tester);

    await tester.tap(find.widgetWithText(TextButton, 'Invite friends'));
    await tester.pumpAndSettle();

    expect(find.text('invite-screen'), findsOneWidget);
  });

  testWidgets('other failures still show a snackbar, not the dialog', (tester) async {
    client.onSubmit = (_) async =>
        throw apiError(400, 'invalid_prompt', 'prompt must not be empty');
    await _pumpCustom(tester);

    await _generate(tester);

    expect(find.text('Daily limit reached'), findsNothing);
    expect(find.text('prompt must not be empty'), findsOneWidget);
  });

  testWidgets('navigates before the account reload finishes', (tester) async {
    var calls = 0;
    final stall = Completer<UserProfile>();
    client.onFetchMe = () {
      calls++;
      // Calls 1 and 2 are the session restore and the account load; later
      // reloads hang.
      return calls <= 2 ? Future.value(fakeProfile()) : stall.future;
    };
    client.onSubmit = (_) async => 'job-1';
    await _pumpCustom(tester);
    await _primeAccount(tester);
    expect(calls, 2);

    await _generate(tester);

    expect(find.text('status:job-1'), findsOneWidget);
    expect(calls, 3, reason: 'the reload was started, and is still stalled');
  });

  testWidgets('shows the limit dialog without waiting for the reload', (tester) async {
    var calls = 0;
    final stall = Completer<UserProfile>();
    client.onFetchMe = () {
      calls++;
      return calls <= 2 ? Future.value(fakeProfile(usedToday: 3)) : stall.future;
    };
    await _pumpCustom(tester);
    await _primeAccount(tester);

    await _generate(tester);

    expect(find.text('Daily limit reached'), findsOneWidget);
    expect(calls, 3);
  });

  testWidgets('a refused submit with an unknown error shows the server message', (tester) async {
    client.onSubmit = (_) async => throw apiError(
          400,
          'invalid_prompt',
          'the prompt is not allowed',
        );
    await _pumpCustom(tester);

    await _generate(tester);

    expect(find.text('the prompt is not allowed'), findsOneWidget);
    final field = tester.widget<TextField>(find.byType(TextField));
    expect(field.controller!.text, 'a cat in space');
    expect(isGenerateEnabled(tester), isTrue);
  });

  testWidgets('a custom prompt is remembered with its text', (tester) async {
    client.onSubmit = (_) async => 'job-9';
    final store = InMemoryCreationStore();
    await _pumpCustom(tester, store: store);
    await _primeAccount(tester);

    await _generate(tester);

    final pending = await store.pending('user-1');
    expect(pending.single.jobId, 'job-9');
    expect(pending.single.label, 'a cat in space');
    expect(pending.single.submittedAt, _now);
    expect(find.text('status:job-9'), findsOneWidget);
  });

  testWidgets('a template is remembered with its title', (tester) async {
    client.onSubmit = (_) async => 'job-8';
    final store = InMemoryCreationStore();
    await _pumpTemplate(tester, store);
    await _primeAccount(tester);

    await pickPhoto(tester);
    await tester.tap(find.text('Generate'));
    await tester.pumpAndSettle();

    final pending = await store.pending('user-1');
    expect(pending.single.label, 'Golden Hour Beach');
  });

  testWidgets('a failed submit remembers nothing', (tester) async {
    final store = InMemoryCreationStore();
    await _pumpCustom(tester, store: store);
    await _primeAccount(tester);

    await _generate(tester);

    expect(await store.pending('user-1'), isEmpty);
  });

  testWidgets('a store that cannot remember still opens the status screen', (tester) async {
    client.onSubmit = (_) async => 'job-7';
    final store = InMemoryCreationStore()..rememberError = StateError('disk full');
    await _pumpCustom(tester, store: store);
    await _primeAccount(tester);

    await _generate(tester);

    expect(find.text('status:job-7'), findsOneWidget);
  });
}

DioException _refused(int status, String code, {String? suspendedUntil}) => DioException(
      requestOptions: RequestOptions(path: '/generations'),
      response: Response(
        requestOptions: RequestOptions(path: '/generations'),
        statusCode: status,
        data: {
          'detail': {
            'error': code,
            'detail': 'server wording that must not be shown',
            'suspended_until': ?suspendedUntil,
          },
        },
      ),
    );

void _safetyTests() {
  group('safety refusals', () {
    setUp(() {
      client = FakeApiClient();
      client.onFetchMe = () async => fakeProfile();
    });

    testWidgets('a blocked prompt keeps the form and says so in the app\'s words', (tester) async {
      client.onSubmit = (_) async => throw _refused(400, 'prompt_blocked');
      await _pumpCustom(tester);

      await _generate(tester);

      expect(find.text("Your prompt contains words we don't allow."), findsOneWidget);
      expect(find.textContaining('server wording'), findsNothing);
      final field = tester.widget<TextField>(find.byType(TextField));
      expect(field.controller!.text, 'a cat in space');
      expect(isGenerateEnabled(tester), isTrue);
      expect(find.text('status:job-1'), findsNothing);
    });

    testWidgets('a blocked photo keeps the form and asks for another', (tester) async {
      client.onSubmit = (_) async => throw _refused(400, 'photo_blocked');
      await _pumpCustom(tester);

      await _generate(tester);

      expect(find.text("This photo can't be used. Choose another."), findsOneWidget);
      final field = tester.widget<TextField>(find.byType(TextField));
      expect(field.controller!.text, 'a cat in space');
      expect(isGenerateEnabled(tester), isTrue);
    });

    testWidgets('unavailable checks say to try again', (tester) async {
      client.onSubmit = (_) async => throw _refused(503, 'safety_unavailable');
      await _pumpCustom(tester);

      await _generate(tester);

      expect(find.text('Checks are unavailable right now, try again.'), findsOneWidget);
    });

    testWidgets('a paused account sees when the pause ends in local time', (tester) async {
      final until = DateTime.utc(2026, 10, 21, 15, 5);
      client.onSubmit = (_) async =>
          throw _refused(403, 'generation_suspended', suspendedUntil: until.toIso8601String());
      await _pumpCustom(tester);

      await _generate(tester);

      final local = until.toLocal();
      final context = tester.element(find.byType(AlertDialog));
      final localizations = MaterialLocalizations.of(context);
      final expectedEnd = '${localizations.formatMediumDate(local)}, '
          '${localizations.formatTimeOfDay(TimeOfDay.fromDateTime(local))}';
      expect(find.text('Generating is paused'), findsOneWidget);
      expect(find.textContaining('until $expectedEnd'), findsOneWidget);
      expect(find.textContaining('recent results broke our content rules'), findsOneWidget);
    });

    testWidgets('closing the paused dialog returns to the form with the values kept', (tester) async {
      client.onSubmit = (_) async => throw _refused(
            403,
            'generation_suspended',
            suspendedUntil: DateTime.utc(2026, 10, 21, 15, 5).toIso8601String(),
          );
      await _pumpCustom(tester);
      await _generate(tester);

      await tester.tap(find.text('OK'));
      await tester.pumpAndSettle();

      expect(find.byType(AlertDialog), findsNothing);
      final field = tester.widget<TextField>(find.byType(TextField));
      expect(field.controller!.text, 'a cat in space');
      expect(isGenerateEnabled(tester), isTrue);
    });

    testWidgets('a pause without a readable end time still explains itself', (tester) async {
      client.onSubmit = (_) async => throw _refused(403, 'generation_suspended');
      await _pumpCustom(tester);

      await _generate(tester);

      expect(find.text('Generating is paused'), findsOneWidget);
      expect(find.textContaining('recent results broke our content rules'), findsOneWidget);
    });
  });
}
