import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/auth/verify_email_screen.dart';
import 'package:image_edit/router.dart';
import 'package:dio/dio.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_session_storage.dart';

late FakeApiClient client;

/// Opens the Verify screen as a signed-in user, from home (so Later can pop).
Future<void> _openFromHome(WidgetTester tester) async {
  final container = await pumpApp(
    tester,
    client: client,
    storage: FakeSessionStorage(savedSession),
  );
  unawaited(container.read(routerProvider).push('/verify-email'));
  await tester.pumpAndSettle();
}

Future<void> _enterCode(WidgetTester tester, String code) async {
  await tester.enterText(find.widgetWithText(TextField, 'Code'), code);
  await tester.pump();
}

bool _enabled(WidgetTester tester, Finder finder) =>
    tester.widget<ButtonStyleButton>(finder).onPressed != null;

Finder get _verify => find.widgetWithText(FilledButton, 'Verify');

DioException _tooMany({String? retryAfter}) => DioException(
      requestOptions: RequestOptions(path: '/x'),
      response: Response(
        requestOptions: RequestOptions(path: '/x'),
        statusCode: 429,
        headers: Headers.fromMap({
          if (retryAfter != null) 'retry-after': [retryAfter],
        }),
        data: {
          'detail': {'error': 'too_many_requests', 'detail': 'slow down'},
        },
      ),
    );

void main() {
  setUp(() => client = FakeApiClient());

  testWidgets('submit is disabled until 6 digits are entered', (tester) async {
    await _openFromHome(tester);

    expect(find.byType(VerifyEmailScreen), findsOneWidget);
    expect(_enabled(tester, _verify), isFalse);
    await _enterCode(tester, '12345');
    expect(_enabled(tester, _verify), isFalse);
    await _enterCode(tester, '123456');
    expect(_enabled(tester, _verify), isTrue);
  });

  testWidgets('only digits are accepted', (tester) async {
    await _openFromHome(tester);

    await _enterCode(tester, '12ab34');

    expect(tester.widget<TextField>(find.widgetWithText(TextField, 'Code')).controller!.text, '1234');
  });

  testWidgets('success refreshes the account and goes back to home', (tester) async {
    var verified = false;
    client.onFetchMe = () async => fakeProfile(emailVerified: verified);
    client.onVerifyEmail = (_) async => verified = true;
    await _openFromHome(tester);
    expect(find.text('Verify your email', skipOffstage: false), findsOneWidget);

    await _enterCode(tester, '123456');
    await tester.tap(_verify);
    await tester.pumpAndSettle();

    expect(client.verifiedWith, ['123456']);
    expect(find.text('Trending'), findsOneWidget);
    expect(find.text('Verify your email'), findsNothing);
  });

  testWidgets('a wrong code is reported and the screen stays', (tester) async {
    client.onVerifyEmail = (_) async =>
        throw apiError(400, 'invalid_code', 'the code is incorrect');
    await _openFromHome(tester);

    await _enterCode(tester, '000000');
    await tester.tap(_verify);
    await tester.pumpAndSettle();

    expect(find.text('Code is incorrect'), findsOneWidget);
    expect(find.byType(VerifyEmailScreen), findsOneWidget);
  });

  testWidgets('an expired code points to Resend', (tester) async {
    client.onVerifyEmail = (_) async =>
        throw apiError(400, 'code_expired', 'the code has expired');
    await _openFromHome(tester);

    await _enterCode(tester, '123456');
    await tester.tap(_verify);
    await tester.pumpAndSettle();

    expect(find.text('Code has expired, tap Resend'), findsOneWidget);
  });

  testWidgets('an already verified account refreshes and leaves', (tester) async {
    client.onVerifyEmail = (_) async =>
        throw apiError(409, 'already_verified', 'this email is already verified');
    await _openFromHome(tester);

    await _enterCode(tester, '123456');
    await tester.tap(_verify);
    await tester.pumpAndSettle();

    expect(find.text('Trending'), findsOneWidget);
  });

  testWidgets('submit shows a spinner and is disabled while in flight', (tester) async {
    final pending = Completer<void>();
    client.onVerifyEmail = (_) => pending.future;
    await _openFromHome(tester);

    await _enterCode(tester, '123456');
    await tester.tap(_verify);
    await tester.pump();

    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(_enabled(tester, find.byType(FilledButton)), isFalse);

    pending.complete();
    await tester.pumpAndSettle();
  });

  testWidgets('Resend is enabled when the screen is opened from home', (tester) async {
    await _openFromHome(tester);

    final resend = find.widgetWithText(OutlinedButton, 'Resend code');
    expect(_enabled(tester, resend), isTrue);

    await tester.tap(resend);
    await tester.pump();

    expect(client.resendCalls, 1);
    expect(find.text('Resend code in 60s'), findsOneWidget);
  });

  testWidgets('after registration Resend counts down 60 seconds, then enables', (tester) async {
    await pumpApp(tester, client: client, storage: FakeSessionStorage(), settle: true);
    await tester.tap(find.text('Create an account'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'Email'), 'new@example.com');
    await tester.enterText(find.widgetWithText(TextField, 'Password'), 'password-1');
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, 'Create account'));
    await tester.pump();
    await tester.pump();
    await tester.pump();

    expect(find.text('Resend code in 60s'), findsOneWidget);
    expect(_enabled(tester, find.widgetWithText(OutlinedButton, 'Resend code in 60s')), isFalse);

    await tester.pump(const Duration(seconds: 30));
    expect(find.text('Resend code in 30s'), findsOneWidget);

    await tester.pump(const Duration(seconds: 30));
    final resend = find.widgetWithText(OutlinedButton, 'Resend code');
    expect(_enabled(tester, resend), isTrue);
  });

  testWidgets('a 429 on Resend says so and restarts the countdown from Retry-After', (tester) async {
    client.onResendVerification = () async => throw _tooMany(retryAfter: '40');
    await _openFromHome(tester);

    await tester.tap(find.widgetWithText(OutlinedButton, 'Resend code'));
    await tester.pump();
    await tester.pump();

    expect(find.text('Too many codes requested, try later'), findsOneWidget);
    expect(find.text('Resend code in 40s'), findsOneWidget);
  });

  testWidgets('Later goes home without verifying and the banner stays', (tester) async {
    client.onFetchMe = () async => fakeProfile(emailVerified: false);
    await _openFromHome(tester);

    await tester.tap(find.text('Later'));
    await tester.pumpAndSettle();

    expect(find.text('Trending'), findsOneWidget);
    expect(find.text('Verify your email'), findsOneWidget);
    expect(client.verifiedWith, isEmpty);
  });

  testWidgets('Later right after registration goes home', (tester) async {
    client.onFetchMe = () async => fakeProfile(emailVerified: false);
    await pumpApp(tester, client: client, storage: FakeSessionStorage());
    await tester.tap(find.text('Create an account'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'Email'), 'new@example.com');
    await tester.enterText(find.widgetWithText(TextField, 'Password'), 'password-1');
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, 'Create account'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Later'));
    await tester.pumpAndSettle();

    expect(find.text('Trending'), findsOneWidget);
    expect(find.text('Verify your email'), findsOneWidget);
  });
}
