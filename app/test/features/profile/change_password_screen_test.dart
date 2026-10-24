import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/core/provider_sign_in.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_provider_sign_in.dart';
import '../../support/profile_harness.dart';

late FakeApiClient client;

const _newPassword = 'a brand new passphrase';

Finder get _submit => find.widgetWithText(FilledButton, 'Change password');

Future<void> _submitWithPassword(WidgetTester tester, {String current = 'old password'}) async {
  await enterPassword(tester, 'New password', _newPassword);
  await tester.tap(_submit);
  await tester.pumpAndSettle();
  await tester.enterText(fieldText('Current password'), current);
  await tester.pump();
  await tester.tap(find.widgetWithText(FilledButton, 'Confirm'));
  await tester.pumpAndSettle();
}

void main() {
  setUp(() => client = FakeApiClient());

  group('account with a password', () {
    setUp(() async {});

    testWidgets('a short password shows the inline message and keeps Submit disabled', (
      tester,
    ) async {
      await openProfile(tester, client: client);
      await tapTile(tester, 'Change password');

      await enterPassword(tester, 'New password', 'short');

      expect(find.text('At least 8 characters'), findsOneWidget);
      expect(tester.widget<FilledButton>(_submit).onPressed, isNull);
    });

    testWidgets('asks for the current password, then changes it and says so on the profile', (
      tester,
    ) async {
      await openProfile(tester, client: client);
      await tapTile(tester, 'Change password');

      await _submitWithPassword(tester);

      expect(client.changedPasswords, hasLength(1));
      expect(client.changedPasswords.single.newPassword, _newPassword);
      expect(client.changedPasswords.single.reauth.password, 'old password');
      expect(find.text('Profile'), findsOneWidget);
      expect(
        find.text('Password changed. Other devices were signed out.'),
        findsOneWidget,
      );
    });

    testWidgets('cancelling the password dialog changes nothing and shows no error', (
      tester,
    ) async {
      await openProfile(tester, client: client);
      await tapTile(tester, 'Change password');
      await enterPassword(tester, 'New password', _newPassword);

      await tester.tap(_submit);
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(TextButton, 'Cancel'));
      await tester.pumpAndSettle();

      expect(client.changedPasswords, isEmpty);
      expect(find.text('Password is incorrect'), findsNothing);
      expect(tester.widget<FilledButton>(_submit).onPressed, isNotNull);
    });

    testWidgets('a wrong current password says so and keeps the new password typed', (
      tester,
    ) async {
      client.onChangePassword =
          (_, _) async => throw apiError(403, 'reauth_failed', 'password is incorrect');
      await openProfile(tester, client: client);
      await tapTile(tester, 'Change password');

      await _submitWithPassword(tester, current: 'wrong');

      expect(find.text('Password is incorrect'), findsOneWidget);
      expect(tester.widget<TextField>(fieldText('New password')).controller!.text, _newPassword);
      expect(find.text('Profile'), findsNothing);
    });

    testWidgets('a lockout shows the server explanation', (tester) async {
      client.onChangePassword = (_, _) async => throw apiError(
            429,
            'too_many_attempts',
            'too many failed attempts; try again in 15 minutes',
          );
      await openProfile(tester, client: client);
      await tapTile(tester, 'Change password');

      await _submitWithPassword(tester);

      expect(find.textContaining('try again in 15 minutes'), findsOneWidget);
    });
  });

  group('account without a password', () {
    setUp(() {
      client.onFetchMe = () async => fakeProfile(providers: ['google'], hasPassword: false);
    });

    testWidgets('sets a password after signing in with the provider again', (tester) async {
      final google = FakeProviderSignIn.google('fresh-google-token');
      await openProfile(tester, client: client, google: google);
      await tapTile(tester, 'Set a password');
      await enterPassword(tester, 'New password', _newPassword);

      await tester.tap(find.widgetWithText(FilledButton, 'Set a password'));
      await tester.pumpAndSettle();

      expect(google.calls, 1);
      expect(find.byType(AlertDialog), findsNothing);
      final reauth = client.changedPasswords.single.reauth;
      expect(reauth.provider, SignInProvider.google);
      expect(reauth.credential!.token, 'fresh-google-token');
      expect(
        find.text('Password changed. Other devices were signed out.'),
        findsOneWidget,
      );
    });

    testWidgets('a cancelled provider sheet changes nothing and shows no error', (tester) async {
      final google = FakeProviderSignIn(null);
      await openProfile(tester, client: client, google: google);
      await tapTile(tester, 'Set a password');
      await enterPassword(tester, 'New password', _newPassword);

      await tester.tap(find.widgetWithText(FilledButton, 'Set a password'));
      await tester.pumpAndSettle();

      expect(google.calls, 1);
      expect(client.changedPasswords, isEmpty);
      expect(find.textContaining("Couldn't confirm"), findsNothing);
      expect(tester.widget<TextField>(fieldText('New password')).controller!.text, _newPassword);
    });

    testWidgets('a refused provider sign-in says it could not be confirmed', (tester) async {
      client.onChangePassword =
          (_, _) async => throw apiError(403, 'reauth_failed', 'sign in again');
      await openProfile(tester, client: client, google: FakeProviderSignIn.google());
      await tapTile(tester, 'Set a password');
      await enterPassword(tester, 'New password', _newPassword);

      await tester.tap(find.widgetWithText(FilledButton, 'Set a password'));
      await tester.pumpAndSettle();

      expect(find.text("Couldn't confirm with Google"), findsOneWidget);
      expect(tester.widget<TextField>(fieldText('New password')).controller!.text, _newPassword);
    });
  });
}
