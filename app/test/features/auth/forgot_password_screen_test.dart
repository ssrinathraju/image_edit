import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_session_storage.dart';

late FakeApiClient client;

Future<void> _openForgot(WidgetTester tester, {String typedEmail = ''}) async {
  await pumpApp(tester, client: client, storage: FakeSessionStorage());
  if (typedEmail.isNotEmpty) {
    await tester.enterText(find.widgetWithText(TextField, 'Email'), typedEmail);
    await tester.pump();
  }
  await tester.tap(find.text('Forgot password?'));
  await tester.pumpAndSettle();
}

String _emailText(WidgetTester tester) =>
    tester.widget<TextField>(find.widgetWithText(TextField, 'Email')).controller!.text;

void main() {
  setUp(() => client = FakeApiClient());

  testWidgets('the email typed on the sign-in screen is prefilled', (tester) async {
    await _openForgot(tester, typedEmail: 'ana@example.com');

    expect(find.widgetWithText(FilledButton, 'Send code'), findsOneWidget);
    expect(_emailText(tester), 'ana@example.com');
  });

  testWidgets('submit is disabled while the email is empty', (tester) async {
    await _openForgot(tester);

    final button = tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Send code'));
    expect(button.onPressed, isNull);
  });

  testWidgets('submitting asks for a code and opens the reset screen', (tester) async {
    await _openForgot(tester, typedEmail: 'ana@example.com');

    await tester.tap(find.widgetWithText(FilledButton, 'Send code'));
    await tester.pumpAndSettle();

    expect(client.resetRequestedFor, ['ana@example.com']);
    expect(find.widgetWithText(FilledButton, 'Reset password'), findsOneWidget);
    expect(
      find.text('If an account exists for ana@example.com, we sent it a 6-digit code.'),
      findsOneWidget,
    );
  });

  testWidgets('a malformed email is reported and the screen stays', (tester) async {
    client.onRequestPasswordReset = (_) async => throw apiError(
          400,
          'invalid_credentials_format',
          'email address is not valid',
        );
    await _openForgot(tester, typedEmail: 'nonsense');

    await tester.tap(find.widgetWithText(FilledButton, 'Send code'));
    await tester.pumpAndSettle();

    expect(find.text('Email address is not valid'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Send code'), findsOneWidget);
    expect(_emailText(tester), 'nonsense');
  });
}
