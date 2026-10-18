import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/auth/session_notifier.dart';
import 'package:image_edit/features/custom_generation/custom_generation_screen.dart';
import 'package:image_edit/features/plans/account_notifier.dart';
import 'package:image_edit/schemas/session.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_session_storage.dart';
import '../../support/screen_harness.dart';

late FakeApiClient client;

Future<void> _pumpCustom(WidgetTester tester) => pumpScreen(
      tester,
      client: client,
      screen: const CustomGenerationScreen(),
      overrides: [
        sessionStorageProvider.overrideWithValue(FakeSessionStorage(savedSession)),
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
}
