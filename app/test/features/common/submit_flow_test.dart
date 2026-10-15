import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/auth/session_notifier.dart';
import 'package:image_edit/features/custom_generation/custom_generation_screen.dart';

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
}

