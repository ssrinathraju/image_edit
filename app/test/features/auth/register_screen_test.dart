import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_session_storage.dart';

late FakeApiClient client;

Future<void> _openRegister(WidgetTester tester) async {
  await pumpApp(tester, client: client, storage: FakeSessionStorage());
  await tester.tap(find.text('Create an account'));
  await tester.pumpAndSettle();
}

Future<void> _fill(WidgetTester tester, {String code = ''}) async {
  await tester.enterText(find.widgetWithText(TextField, 'Email'), 'new@example.com');
  await tester.enterText(find.widgetWithText(TextField, 'Password'), 'password-1');
  if (code.isNotEmpty) {
    await tester.enterText(
      find.widgetWithText(TextField, 'Referral code (optional)'),
      code,
    );
  }
  await tester.pump();
}

void main() {
  setUp(() => client = FakeApiClient());

  testWidgets('the referral code is sent trimmed when entered', (tester) async {
    await _openRegister(tester);

    await _fill(tester, code: '  k7m2qx9p ');
    await tester.tap(find.widgetWithText(FilledButton, 'Create account'));
    await tester.pumpAndSettle();

    expect(client.referralCodes, ['k7m2qx9p']);
  });

  testWidgets('a blank referral code is omitted', (tester) async {
    await _openRegister(tester);

    await _fill(tester);
    await tester.tap(find.widgetWithText(FilledButton, 'Create account'));
    await tester.pumpAndSettle();

    expect(client.referralCodes, [null]);
  });

  testWidgets('an unknown code shows the message and keeps every entry', (tester) async {
    client.onRegister = (_, _) async => throw apiError(
          400,
          'invalid_referral_code',
          'this referral code was not recognised',
        );
    await _openRegister(tester);

    await _fill(tester, code: 'NOSUCH22');
    await tester.tap(find.widgetWithText(FilledButton, 'Create account'));
    await tester.pumpAndSettle();

    expect(find.text('this referral code was not recognised'), findsOneWidget);
    String textOf(String label) =>
        tester.widget<TextField>(find.widgetWithText(TextField, label)).controller!.text;
    expect(textOf('Email'), 'new@example.com');
    expect(textOf('Password'), 'password-1');
    expect(textOf('Referral code (optional)'), 'NOSUCH22');
  });

  testWidgets('a rewarded signup shows the bonus on the home screen after verifying', (tester) async {
    client.onFetchMe = () async => fakeProfile(bonusCredits: 5);
    await _openRegister(tester);

    await _fill(tester, code: 'K7M2QX9P');
    await tester.tap(find.widgetWithText(FilledButton, 'Create account'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'Code'), '123456');
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, 'Verify'));
    await tester.pumpAndSettle();

    expect(find.text('8 generations left today'), findsOneWidget);
  });
}
