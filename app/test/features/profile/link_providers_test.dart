import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_provider_sign_in.dart';
import '../../support/profile_harness.dart';

late FakeApiClient client;

Finder _row(String label) => find.widgetWithText(ListTile, label);

Finder _status(String label, String status) =>
    find.descendant(of: _row(label), matching: find.text(status));

Future<void> _unlinkGoogle(WidgetTester tester) async {
  await tapRowAction(tester, 'Google', 'Unlink');
  await tester.tap(find.widgetWithText(FilledButton, 'Unlink'));
  await tester.pumpAndSettle();
}

Future<void> _confirmPassword(WidgetTester tester, String password) async {
  await tester.enterText(fieldText('Current password'), password);
  await tester.pump();
  await tester.tap(find.widgetWithText(FilledButton, 'Confirm'));
  await tester.pumpAndSettle();
}

void main() {
  setUp(() => client = FakeApiClient());

  group('linking', () {
    testWidgets(
      'Link asks for the password first, then runs the Google sheet and shows Linked',
      (tester) async {
        final google = FakeProviderSignIn.google('google-token');
        client.onLinkGoogle = (_) async {
          client.onFetchMe = () async => fakeProfile(providers: ['google']);
        };
        await openProfile(tester, client: client, google: google);

        await tapRowAction(tester, 'Google', 'Link');
        expect(fieldText('Current password'), findsOneWidget);
        expect(google.calls, 0);
        await _confirmPassword(tester, 'old password');

        expect(google.calls, 1);
        expect(client.linkedGoogleTokens, ['google-token']);
        expect(client.linkReauths.single.password, 'old password');
        expect(_status('Google', 'Linked'), findsOneWidget);
        expect(find.widgetWithText(TextButton, 'Unlink'), findsOneWidget);
      },
    );

    testWidgets(
      'a cancelled password dialog shows no sheet and links nothing',
      (tester) async {
        final google = FakeProviderSignIn.google('google-token');
        await openProfile(tester, client: client, google: google);

        await tapRowAction(tester, 'Google', 'Link');
        await tester.tap(find.widgetWithText(TextButton, 'Cancel'));
        await tester.pumpAndSettle();

        expect(google.calls, 0);
        expect(client.linkedGoogleTokens, isEmpty);
        expect(find.byType(SnackBar), findsNothing);
      },
    );

    testWidgets('a wrong password says so and links nothing', (tester) async {
      client.onLinkGoogle = (_) async =>
          throw apiError(403, 'reauth_failed', 'wrong password');
      await openProfile(
        tester,
        client: client,
        google: FakeProviderSignIn.google(),
      );

      await tapRowAction(tester, 'Google', 'Link');
      await _confirmPassword(tester, 'nope');

      expect(find.text('Password is incorrect'), findsOneWidget);
      expect(_status('Google', 'Not linked'), findsOneWidget);
    });

    testWidgets(
      'a provider-only account links Apple after signing in with Google',
      (tester) async {
        client.onFetchMe = () async =>
            fakeProfile(hasPassword: false, providers: ['google']);
        final google = FakeProviderSignIn.google('fresh-google-token');
        final apple = FakeProviderSignIn.apple('apple-token');
        await openProfile(
          tester,
          client: client,
          google: google,
          apple: apple,
          platform: TargetPlatform.android,
        );

        await tapRowAction(tester, 'Apple', 'Link');

        expect(google.calls, 1);
        expect(
          client.linkReauths.single.credential!.token,
          'fresh-google-token',
        );
        expect(client.linkedApple.single.first, 'apple-token');
      },
    );

    testWidgets('linking Apple on iOS sends the token, raw nonce and code', (
      tester,
    ) async {
      final apple = FakeProviderSignIn.apple('apple-token');
      await openProfile(
        tester,
        client: client,
        apple: apple,
        platform: TargetPlatform.iOS,
      );

      await tapRowAction(tester, 'Apple', 'Link');
      await _confirmPassword(tester, 'old password');

      expect(client.linkedApple, [
        ['apple-token', 'raw-nonce', 'apple-code'],
      ]);
    });

    testWidgets(
      'an identity linked elsewhere says it belongs to a different user',
      (tester) async {
        client.onLinkGoogle = (_) async =>
            throw apiError(409, 'provider_in_use', 'linked elsewhere');
        await openProfile(
          tester,
          client: client,
          google: FakeProviderSignIn.google(),
        );

        await tapRowAction(tester, 'Google', 'Link');
        await _confirmPassword(tester, 'old password');

        expect(
          find.text(
            'That Google account is already linked to a different user.',
          ),
          findsOneWidget,
        );
        expect(_status('Google', 'Not linked'), findsOneWidget);
      },
    );

    testWidgets('a cancelled sheet changes nothing and shows no error', (
      tester,
    ) async {
      final google = FakeProviderSignIn(null);
      await openProfile(tester, client: client, google: google);

      await tapRowAction(tester, 'Google', 'Link');
      await _confirmPassword(tester, 'old password');

      expect(google.calls, 1);
      expect(client.linkedGoogleTokens, isEmpty);
      expect(find.byType(SnackBar), findsNothing);
      expect(_status('Google', 'Not linked'), findsOneWidget);
    });

    testWidgets('a rejected token does not sign the user out', (tester) async {
      client.onLinkGoogle = (_) async =>
          throw apiError(401, 'invalid_provider_token', 'rejected');
      await openProfile(
        tester,
        client: client,
        google: FakeProviderSignIn.google(),
      );

      await tapRowAction(tester, 'Google', 'Link');
      await _confirmPassword(tester, 'old password');

      expect(find.text("Couldn't confirm with Google"), findsOneWidget);
      expect(find.text('Profile'), findsOneWidget);
    });
  });

  group('unlinking', () {
    setUp(() {
      client.onFetchMe = () async => fakeProfile(providers: ['google']);
    });

    testWidgets(
      'confirms, re-authenticates with the password, then shows Not linked',
      (tester) async {
        client.onUnlinkProvider = (_, _) async {
          client.onFetchMe = () async => fakeProfile();
        };
        await openProfile(
          tester,
          client: client,
          google: FakeProviderSignIn.google(),
        );

        await _unlinkGoogle(tester);
        expect(client.unlinked, isEmpty);
        await _confirmPassword(tester, 'old password');

        expect(client.unlinked.single.provider, 'google');
        expect(client.unlinked.single.reauth.password, 'old password');
        expect(_status('Google', 'Not linked'), findsOneWidget);
      },
    );

    testWidgets('cancelling the confirmation changes nothing', (tester) async {
      await openProfile(
        tester,
        client: client,
        google: FakeProviderSignIn.google(),
      );

      await tapRowAction(tester, 'Google', 'Unlink');
      await tester.tap(find.widgetWithText(TextButton, 'Cancel'));
      await tester.pumpAndSettle();

      expect(client.unlinked, isEmpty);
      expect(_status('Google', 'Linked'), findsOneWidget);
    });

    testWidgets(
      'cancelling the password dialog changes nothing and shows no error',
      (tester) async {
        await openProfile(
          tester,
          client: client,
          google: FakeProviderSignIn.google(),
        );

        await _unlinkGoogle(tester);
        await tester.tap(find.widgetWithText(TextButton, 'Cancel'));
        await tester.pumpAndSettle();

        expect(client.unlinked, isEmpty);
        expect(find.byType(SnackBar), findsNothing);
        expect(_status('Google', 'Linked'), findsOneWidget);
      },
    );

    testWidgets('a wrong password says so and keeps the row Linked', (
      tester,
    ) async {
      client.onUnlinkProvider = (_, _) async =>
          throw apiError(403, 'reauth_failed', 'password is incorrect');
      await openProfile(
        tester,
        client: client,
        google: FakeProviderSignIn.google(),
      );

      await _unlinkGoogle(tester);
      await _confirmPassword(tester, 'wrong');

      expect(find.text('Password is incorrect'), findsOneWidget);
      expect(_status('Google', 'Linked'), findsOneWidget);
    });

    testWidgets(
      'the last sign-in method is kept and the user is told what to do',
      (tester) async {
        client.onFetchMe = () async =>
            fakeProfile(providers: ['google'], hasPassword: false);
        client.onUnlinkProvider = (_, _) async =>
            throw apiError(409, 'last_sign_in_method', 'only method');
        final google = FakeProviderSignIn.google('fresh-google-token');
        await openProfile(tester, client: client, google: google);

        await _unlinkGoogle(tester);

        expect(google.calls, 1);
        expect(
          client.unlinked.single.reauth.credential!.token,
          'fresh-google-token',
        );
        expect(
          find.text('Set a password or link another provider first.'),
          findsOneWidget,
        );
        expect(_status('Google', 'Linked'), findsOneWidget);
      },
    );

    testWidgets(
      'a cancelled provider sheet changes nothing and shows no error',
      (tester) async {
        client.onFetchMe = () async =>
            fakeProfile(providers: ['google'], hasPassword: false);
        await openProfile(
          tester,
          client: client,
          google: FakeProviderSignIn(null),
        );

        await _unlinkGoogle(tester);

        expect(client.unlinked, isEmpty);
        expect(find.byType(SnackBar), findsNothing);
      },
    );
  });
}
