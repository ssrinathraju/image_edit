import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/router.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_session_storage.dart';

late FakeApiClient client;
late FakeSessionStorage storage;

Future<void> _openReset(WidgetTester tester) async {
  storage = FakeSessionStorage();
  final container = await pumpApp(tester, client: client, storage: storage);
  container.read(routerProvider).go('/reset-password?email=ana%40example.com');
  await tester.pumpAndSettle();
}

Future<void> _fill(WidgetTester tester, {String code = '123456', String password = 'new password 1'}) async {
  await tester.enterText(find.widgetWithText(TextField, 'Code'), code);
  await tester.enterText(find.widgetWithText(TextField, 'New password'), password);
  await tester.pump();
}

Finder get _submit => find.widgetWithText(FilledButton, 'Reset password');

bool _enabled(WidgetTester tester, Finder finder) =>
    tester.widget<ButtonStyleButton>(finder).onPressed != null;

String _textOf(WidgetTester tester, String label) =>
    tester.widget<TextField>(find.widgetWithText(TextField, label)).controller!.text;

void main() {
  setUp(() => client = FakeApiClient());

  testWidgets('success stores the returned session and lands on home', (tester) async {
    await _openReset(tester);

    await _fill(tester);
    await tester.tap(_submit);
    await tester.pumpAndSettle();

    expect(client.resetConfirmed, [
      ['ana@example.com', '123456', 'new password 1'],
    ]);
    expect(storage.saved?.token, 'token-reset');
    expect(find.text('Trending'), findsOneWidget);
  });

  testWidgets('a rejected code keeps the entered values', (tester) async {
    client.onConfirmPasswordReset = (_, _, _) async =>
        throw apiError(400, 'invalid_code', 'code is incorrect or has expired');
    await _openReset(tester);

    await _fill(tester);
    await tester.tap(_submit);
    await tester.pumpAndSettle();

    expect(find.text('Code is incorrect or has expired'), findsOneWidget);
    expect(_textOf(tester, 'Code'), '123456');
    expect(_textOf(tester, 'New password'), 'new password 1');
    expect(storage.saved, isNull);
  });

  testWidgets('a short password shows a message and disables submit', (tester) async {
    await _openReset(tester);

    await _fill(tester, password: 'short');

    expect(find.text('At least 8 characters'), findsOneWidget);
    expect(_enabled(tester, _submit), isFalse);
  });

  testWidgets('an incomplete code disables submit', (tester) async {
    await _openReset(tester);

    await _fill(tester, code: '123');

    expect(_enabled(tester, _submit), isFalse);
  });

  testWidgets('Resend calls the request endpoint after the countdown', (tester) async {
    await _openReset(tester);
    final countingDown = find.widgetWithText(OutlinedButton, 'Resend code in 60s');
    expect(_enabled(tester, countingDown), isFalse);

    await tester.pump(const Duration(seconds: 60));
    await tester.tap(find.widgetWithText(OutlinedButton, 'Resend code'));
    await tester.pump();

    expect(client.resetRequestedFor, ['ana@example.com']);
    expect(find.text('Resend code in 60s'), findsOneWidget);
  });
}
