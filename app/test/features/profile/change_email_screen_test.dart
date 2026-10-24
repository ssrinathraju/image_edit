import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_provider_sign_in.dart';
import '../../support/profile_harness.dart';

late FakeApiClient client;

const _newEmail = 'new@example.com';

Finder get _sendCode => find.widgetWithText(FilledButton, 'Send code');
Finder get _confirm => find.widgetWithText(FilledButton, 'Confirm');

Future<void> _openChangeEmail(
  WidgetTester tester, {
  FakeProviderSignIn? google,
}) async {
  await openProfile(tester, client: client, google: google);
  await tapTile(tester, 'Change email');
}

Future<void> _requestCode(WidgetTester tester, {String password = 'old password'}) async {
  await tester.enterText(fieldText('New email'), _newEmail);
  await tester.pump();
  await tester.tap(_sendCode);
  await tester.pumpAndSettle();
  if (find.byType(AlertDialog).evaluate().isEmpty) return;
  await tester.enterText(fieldText('Current password'), password);
  await tester.pump();
  await tester.tap(_confirm);
  await tester.pumpAndSettle();
}

Future<void> _enterCode(WidgetTester tester, String code) async {
  await tester.enterText(fieldText('Code'), code);
  await tester.pump();
  await tester.tap(_confirm);
  await tester.pumpAndSettle();
}

void main() {
  setUp(() => client = FakeApiClient());

  group('Change email screen', () {
    testWidgets('Submit stays disabled until the email looks valid', (tester) async {
      await _openChangeEmail(tester);
      expect(tester.widget<FilledButton>(_sendCode).onPressed, isNull);

      await tester.enterText(fieldText('New email'), 'not-an-email');
      await tester.pump();
      expect(tester.widget<FilledButton>(_sendCode).onPressed, isNull);

      await tester.enterText(fieldText('New email'), _newEmail);
      await tester.pump();
      expect(tester.widget<FilledButton>(_sendCode).onPressed, isNotNull);
    });

    testWidgets('asks for the password, requests the code and shows the code screen', (
      tester,
    ) async {
      await _openChangeEmail(tester);

      await _requestCode(tester);

      final request = client.emailChangeRequests.single;
      expect(request.newEmail, _newEmail);
      expect(request.reauth.password, 'old password');
      expect(find.textContaining('We sent a 6-digit code to $_newEmail'), findsOneWidget);
    });

    testWidgets('a provider-only account re-authenticates with its provider', (tester) async {
      client.onFetchMe = () async => fakeProfile(providers: ['google'], hasPassword: false);
      final google = FakeProviderSignIn.google('fresh-google-token');
      await _openChangeEmail(tester, google: google);

      await _requestCode(tester);

      expect(google.calls, 1);
      expect(client.emailChangeRequests.single.reauth.credential!.token, 'fresh-google-token');
      expect(find.textContaining('We sent a 6-digit code'), findsOneWidget);
    });

    testWidgets('a cancelled password dialog changes nothing and shows no error', (tester) async {
      await _openChangeEmail(tester);
      await tester.enterText(fieldText('New email'), _newEmail);
      await tester.pump();

      await tester.tap(_sendCode);
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(TextButton, 'Cancel'));
      await tester.pumpAndSettle();

      expect(client.emailChangeRequests, isEmpty);
      expect(find.text('Password is incorrect'), findsNothing);
    });

    testWidgets('a wrong current password says so and keeps the new email entered', (
      tester,
    ) async {
      client.onRequestEmailChange =
          (_, _) async => throw apiError(403, 'reauth_failed', 'password is incorrect');
      await _openChangeEmail(tester);

      await _requestCode(tester, password: 'wrong');

      expect(find.text('Password is incorrect'), findsOneWidget);
      expect(tester.widget<TextField>(fieldText('New email')).controller!.text, _newEmail);
    });

    testWidgets('an email already in use says so and keeps the value', (tester) async {
      client.onRequestEmailChange =
          (_, _) async => throw apiError(409, 'email_taken', 'taken');
      await _openChangeEmail(tester);

      await _requestCode(tester);

      expect(
        find.text('That email is already used by another account'),
        findsOneWidget,
      );
      expect(tester.widget<TextField>(fieldText('New email')).controller!.text, _newEmail);
    });

    testWidgets('a rate limit shows how long to wait', (tester) async {
      client.onRequestEmailChange = (_, _) async => throw DioException(
            requestOptions: RequestOptions(path: '/me/email'),
            response: Response(
              requestOptions: RequestOptions(path: '/me/email'),
              statusCode: 429,
              headers: Headers.fromMap({
                'retry-after': ['40'],
              }),
              data: {
                'detail': {'error': 'too_many_requests', 'detail': 'slow down'},
              },
            ),
          );
      await _openChangeEmail(tester);

      await _requestCode(tester);

      expect(find.text('Too many codes requested, try again in 40s'), findsOneWidget);
    });
  });

  group('code step', () {
    Future<void> toCodeScreen(WidgetTester tester) async {
      await _openChangeEmail(tester);
      await _requestCode(tester);
    }

    testWidgets('a correct code shows the new email on the profile with the message', (
      tester,
    ) async {
      client.onConfirmEmailChange = (_) async {
        client.onFetchMe = () async => fakeProfile(email: _newEmail);
        return _newEmail;
      };
      await toCodeScreen(tester);

      await _enterCode(tester, '123456');

      expect(client.confirmedEmailCodes, ['123456']);
      expect(find.text('Profile'), findsOneWidget);
      expect(find.text(_newEmail), findsOneWidget);
      expect(find.text('ana@example.com'), findsNothing);
      expect(
        find.text('Email changed. Other devices were signed out.'),
        findsOneWidget,
      );
    });

    testWidgets('a wrong code is explained and can be retried', (tester) async {
      client.onConfirmEmailChange =
          (_) async => throw apiError(400, 'invalid_code', 'wrong');
      await toCodeScreen(tester);

      await _enterCode(tester, '000000');

      expect(find.text('Code is incorrect'), findsOneWidget);
      expect(find.textContaining('We sent a 6-digit code'), findsOneWidget);
    });

    testWidgets('an expired code points to Resend', (tester) async {
      client.onConfirmEmailChange =
          (_) async => throw apiError(400, 'code_expired', 'expired');
      await toCodeScreen(tester);

      await _enterCode(tester, '123456');

      expect(find.text('Code has expired, tap Resend'), findsOneWidget);
    });

    testWidgets('Resend counts down for 60 seconds, then asks for a code again', (
      tester,
    ) async {
      await toCodeScreen(tester);
      expect(find.text('Resend code in 60s'), findsOneWidget);

      await tester.pump(const Duration(seconds: 60));
      expect(find.text('Resend code'), findsOneWidget);
      await tester.tap(find.text('Resend code'));
      await tester.pump();
      await tester.pump();

      expect(client.emailChangeRequests, hasLength(2));
      expect(client.emailChangeRequests.last.newEmail, _newEmail);
      expect(client.emailChangeRequests.last.reauth.password, 'old password');
      expect(find.text('Resend code in 60s'), findsOneWidget);
      await tester.pump(const Duration(seconds: 60));
    });

    testWidgets('an email taken meanwhile goes back to Change email with the value kept', (
      tester,
    ) async {
      client.onConfirmEmailChange =
          (_) async => throw apiError(409, 'email_taken', 'taken');
      await toCodeScreen(tester);

      await _enterCode(tester, '123456');

      expect(find.widgetWithText(AppBar, 'Change email'), findsOneWidget);
      expect(tester.widget<TextField>(fieldText('New email')).controller!.text, _newEmail);
      expect(find.textContaining('already used by another account'), findsOneWidget);
    });

    testWidgets('Back returns to Change email with the value kept', (tester) async {
      await toCodeScreen(tester);

      await tester.tap(find.byType(BackButton));
      await tester.pumpAndSettle();

      expect(tester.widget<TextField>(fieldText('New email')).controller!.text, _newEmail);
      expect(client.confirmedEmailCodes, isEmpty);
    });
  });
}
