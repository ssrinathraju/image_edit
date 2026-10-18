import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_session_storage.dart';

late FakeApiClient client;
late FakeSessionStorage storage;

Future<void> _openConfirmScreen(WidgetTester tester) async {
  await pumpApp(tester, client: client, storage: storage);
  await tester.tap(find.text('Create an account'));
  await tester.pumpAndSettle();
  await tester.enterText(find.widgetWithText(TextField, 'Email'), 'new@example.com');
  await tester.enterText(find.widgetWithText(TextField, 'Password'), 'password-1');
  await tester.enterText(
    find.widgetWithText(TextField, 'Referral code (optional)'),
    'K7M2QX9P',
  );
  await tester.pump();
  await tester.tap(find.widgetWithText(FilledButton, 'Create account'));
  await tester.pumpAndSettle();
}

Future<void> _enterCode(WidgetTester tester, String code) async {
  await tester.enterText(find.widgetWithText(TextField, 'Code'), code);
  await tester.pump();
}

// The screen's only FilledButton; its label is replaced by a spinner while in flight.
final _confirmButton = find.byType(FilledButton);

bool _confirmEnabled(WidgetTester tester) =>
    tester.widget<FilledButton>(_confirmButton).onPressed != null;

OutlinedButton _resendButton(WidgetTester tester) =>
    tester.widget<OutlinedButton>(find.byType(OutlinedButton));

DioException _tooManyRequests(int retryAfter) => DioException(
      requestOptions: RequestOptions(path: '/auth/register'),
      response: Response(
        requestOptions: RequestOptions(path: '/auth/register'),
        statusCode: 429,
        headers: Headers.fromMap({
          'retry-after': ['$retryAfter'],
        }),
        data: {
          'detail': {'error': 'too_many_requests', 'detail': 'slow down'},
        },
      ),
    );

void main() {
  setUp(() {
    client = FakeApiClient();
    storage = FakeSessionStorage();
  });

  testWidgets('names the email and keeps Confirm disabled until 6 digits are entered', (
    tester,
  ) async {
    await _openConfirmScreen(tester);

    expect(find.textContaining('new@example.com'), findsOneWidget);
    expect(_confirmEnabled(tester), isFalse);

    await _enterCode(tester, '12345');
    expect(_confirmEnabled(tester), isFalse);

    await _enterCode(tester, '123456');
    expect(_confirmEnabled(tester), isTrue);
  });

  testWidgets('the correct code stores the session and opens home', (tester) async {
    await _openConfirmScreen(tester);

    await _enterCode(tester, '123456');
    await tester.tap(_confirmButton);
    await tester.pumpAndSettle();

    expect(client.confirmedRegistrations, [
      ['new@example.com', '123456'],
    ]);
    expect(storage.saved?.email, 'new@example.com');
    expect(find.text('Trending'), findsOneWidget);
    expect(find.text('Confirm registration'), findsNothing);
  });

  testWidgets('Confirm shows a spinner and is disabled while the request is in flight', (
    tester,
  ) async {
    final gate = Completer<void>();
    client.onConfirmRegistration = (email, _) async {
      await gate.future;
      return throw apiError(400, 'invalid_code', 'x');
    };
    await _openConfirmScreen(tester);

    await _enterCode(tester, '123456');
    await tester.tap(_confirmButton);
    await tester.pump();

    expect(_confirmEnabled(tester), isFalse);
    expect(
      find.descendant(of: _confirmButton, matching: find.byType(CircularProgressIndicator)),
      findsOneWidget,
    );

    gate.complete();
    await tester.pumpAndSettle();
    expect(_confirmEnabled(tester), isTrue);
  });

  testWidgets('a wrong code is reported as incorrect and the screen stays', (tester) async {
    client.onConfirmRegistration = (_, _) async =>
        throw apiError(400, 'invalid_code', 'the code is incorrect');
    await _openConfirmScreen(tester);

    await _enterCode(tester, '000000');
    await tester.tap(_confirmButton);
    await tester.pumpAndSettle();

    expect(find.text('Code is incorrect'), findsOneWidget);
    expect(find.text('Confirm registration'), findsOneWidget);
    expect(storage.saved, isNull);
  });

  testWidgets('an expired code points the user to Resend', (tester) async {
    client.onConfirmRegistration = (_, _) async =>
        throw apiError(400, 'code_expired', 'the code has expired');
    await _openConfirmScreen(tester);

    await _enterCode(tester, '123456');
    await tester.tap(_confirmButton);
    await tester.pumpAndSettle();

    expect(find.text('Code has expired, tap Resend'), findsOneWidget);
  });

  testWidgets('Resend counts down for 60 seconds, then sends the registration again', (
    tester,
  ) async {
    await _openConfirmScreen(tester);

    expect(find.text('Resend code in 60s'), findsOneWidget);
    expect(_resendButton(tester).onPressed, isNull);

    await tester.pump(const Duration(seconds: 60));
    expect(find.text('Resend code'), findsOneWidget);
    expect(_resendButton(tester).onPressed, isNotNull);
    expect(client.registered, ['new@example.com']);

    await tester.tap(find.text('Resend code'));
    await tester.pump();
    await tester.pump();

    expect(client.registered, ['new@example.com', 'new@example.com']);
    expect(client.registrationPasswords, ['password-1', 'password-1']);
    expect(client.referralCodes, ['K7M2QX9P', 'K7M2QX9P']);
    expect(find.text('Resend code in 60s'), findsOneWidget);
    expect(_resendButton(tester).onPressed, isNull);
  });

  testWidgets('a refused resend shows the message and the retry countdown', (tester) async {
    await _openConfirmScreen(tester);
    await tester.pump(const Duration(seconds: 60));
    client.onRegister = (_, _) async => throw _tooManyRequests(30);

    await tester.tap(find.text('Resend code'));
    await tester.pump();
    await tester.pump();

    expect(find.text('Too many codes requested, try again in 30s'), findsOneWidget);
    expect(find.text('Resend code in 30s'), findsOneWidget);
  });

  testWidgets('an email taken in the meantime offers to go to sign-in', (tester) async {
    client.onConfirmRegistration = (_, _) async =>
        throw apiError(409, 'email_taken', 'this email is already registered');
    await _openConfirmScreen(tester);

    await _enterCode(tester, '123456');
    await tester.tap(_confirmButton);
    await tester.pumpAndSettle();

    expect(find.text('Email already registered'), findsOneWidget);

    await tester.tap(find.text('Go to sign-in'));
    await tester.pumpAndSettle();

    expect(find.widgetWithText(FilledButton, 'Sign in'), findsOneWidget);
    expect(find.text('Confirm registration'), findsNothing);
  });

  testWidgets('Back returns to the registration screen with every value kept', (tester) async {
    await _openConfirmScreen(tester);

    await tester.tap(find.byType(BackButton));
    await tester.pumpAndSettle();

    String textOf(String label) =>
        tester.widget<TextField>(find.widgetWithText(TextField, label)).controller!.text;
    expect(find.widgetWithText(FilledButton, 'Create account'), findsOneWidget);
    expect(textOf('Email'), 'new@example.com');
    expect(textOf('Password'), 'password-1');
    expect(textOf('Referral code (optional)'), 'K7M2QX9P');
    expect(storage.saved, isNull);
  });
}
