import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/profile/profile_providers.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_provider_sign_in.dart';
import '../../support/fake_session_storage.dart';

late FakeApiClient client;
late FakeSessionStorage storage;

Future<FakeLinkLauncher> _openProfile(
  WidgetTester tester, {
  ProfileLinks links = const ProfileLinks(),
  FakeProviderSignIn? google,
  FakeProviderSignIn? apple,
  TargetPlatform platform = TargetPlatform.android,
}) async {
  final launcher = FakeLinkLauncher();
  await pumpApp(
    tester,
    client: client,
    storage: storage,
    links: links,
    launcher: launcher,
    google: google,
    apple: apple,
    platform: platform,
  );
  await tester.tap(find.byTooltip('Profile'));
  await tester.pumpAndSettle();
  return launcher;
}

void main() {
  setUp(() {
    client = FakeApiClient();
    storage = FakeSessionStorage(savedSession);
  });

  testWidgets('the home icon opens the profile and back returns home', (tester) async {
    await _openProfile(tester);

    expect(find.text('Profile'), findsOneWidget);

    await tester.tap(find.byType(BackButton));
    await tester.pumpAndSettle();
    expect(find.text('Trending'), findsOneWidget);
  });

  testWidgets('the header shows the email, its initial, and the version', (tester) async {
    await _openProfile(tester);

    expect(find.text('ana@example.com'), findsOneWidget);
    expect(find.text('A'), findsOneWidget);
    expect(find.text('Version 1.2.3 (45)'), findsOneWidget);
  });

  testWidgets('unconfigured links are hidden', (tester) async {
    await _openProfile(tester);

    expect(find.text('Help and feedback'), findsNothing);
    expect(find.text('Privacy policy'), findsNothing);
    expect(find.text('Terms'), findsNothing);
  });

  testWidgets('configured links are shown and open their address', (tester) async {
    final launcher = await _openProfile(
      tester,
      links: const ProfileLinks(
        privacyUrl: 'https://example.com/privacy',
        supportEmail: 'help@example.com',
      ),
    );

    expect(find.text('Privacy policy'), findsOneWidget);
    expect(find.text('Help and feedback'), findsOneWidget);
    expect(find.text('Terms'), findsNothing);

    await tester.tap(find.text('Privacy policy'));
    await tester.pumpAndSettle();
    expect(launcher.opened.single.toString(), 'https://example.com/privacy');

    await tester.tap(find.text('Help and feedback'));
    await tester.pumpAndSettle();
    expect(launcher.opened.last.toString(), 'mailto:help@example.com');
  });

  testWidgets('a link that cannot open shows a snackbar', (tester) async {
    final launcher = await _openProfile(
      tester,
      links: const ProfileLinks(termsUrl: 'https://example.com/terms'),
    );
    launcher.result = false;

    await tester.tap(find.text('Terms'));
    await tester.pumpAndSettle();

    expect(find.text('Could not open the link.'), findsOneWidget);
  });

  group('log out', () {
    testWidgets('confirming returns to sign-in and clears the session', (tester) async {
      await _openProfile(tester);

      await tester.tap(find.widgetWithText(ListTile, 'Log out'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Log out'));
      await tester.pumpAndSettle();

      expect(find.widgetWithText(FilledButton, 'Sign in'), findsOneWidget);
      expect(client.logoutCalls, 1);
      expect(storage.saved, isNull);
    });

    testWidgets('cancelling does nothing', (tester) async {
      await _openProfile(tester);

      await tester.tap(find.widgetWithText(ListTile, 'Log out'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(find.text('Profile'), findsOneWidget);
      expect(client.logoutCalls, 0);
      expect(storage.saved, savedSession);
    });
  });

  group('delete account', () {
    Future<void> openDialog(WidgetTester tester) async {
      await tester.tap(find.widgetWithText(ListTile, 'Delete account'));
      await tester.pumpAndSettle();
    }

    FilledButton deleteButton(WidgetTester tester) => tester.widget<FilledButton>(
          find.widgetWithText(FilledButton, 'Delete account'),
        );

    testWidgets('the destructive button is disabled until a password is typed', (tester) async {
      await _openProfile(tester);
      await openDialog(tester);

      expect(find.textContaining('permanent'), findsOneWidget);
      expect(deleteButton(tester).onPressed, isNull);

      await tester.enterText(find.byType(TextField), 'password-1');
      await tester.pump();
      expect(deleteButton(tester).onPressed, isNotNull);
    });

    testWidgets('success returns to sign-in', (tester) async {
      await _openProfile(tester);
      await openDialog(tester);

      await tester.enterText(find.byType(TextField), 'password-1');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Delete account'));
      await tester.pumpAndSettle();

      expect(client.deletedWith, ['password-1']);
      expect(find.widgetWithText(FilledButton, 'Sign in'), findsOneWidget);
      expect(storage.saved, isNull);
    });

    testWidgets('a wrong password keeps the user on the profile with a message', (tester) async {
      client.onDeleteAccount = (_) async =>
          throw apiError(403, 'invalid_password', 'password is incorrect');
      await _openProfile(tester);
      await openDialog(tester);

      await tester.enterText(find.byType(TextField), 'nope');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Delete account'));
      await tester.pumpAndSettle();

      expect(find.text('Profile'), findsOneWidget);
      expect(find.text('password is incorrect'), findsOneWidget);
      expect(storage.saved, savedSession);
    });

    testWidgets('cancelling does not call the server', (tester) async {
      await _openProfile(tester);
      await openDialog(tester);

      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(client.deletedWith, isEmpty);
    });
  });

  group('sign-in providers', () {
    testWidgets('a Google-linked account shows Signed in with Google', (tester) async {
      client.onFetchMe = () async => fakeProfile(providers: ['google']);
      await _openProfile(tester);

      expect(find.text('Signed in with Google'), findsOneWidget);
      expect(find.text('Signed in with Apple'), findsNothing);
    });

    testWidgets('both providers are shown when both are linked', (tester) async {
      client.onFetchMe = () async => fakeProfile(providers: ['apple', 'google']);
      await _openProfile(tester);

      expect(find.text('Signed in with Google'), findsOneWidget);
      expect(find.text('Signed in with Apple'), findsOneWidget);
    });

    testWidgets('a password-only account has no provider line', (tester) async {
      client.onFetchMe = () async => fakeProfile();
      await _openProfile(tester);

      expect(find.textContaining('Signed in with'), findsNothing);
    });

    testWidgets('no provider line is shown when the account failed to load', (tester) async {
      await _openProfile(tester);

      expect(find.textContaining('Signed in with'), findsNothing);
    });
  });

  group('delete account without a password', () {
    setUp(() {
      client.onFetchMe = () async =>
          fakeProfile(providers: ['google'], hasPassword: false);
    });

    Future<void> confirmDialog(WidgetTester tester) async {
      await tester.tap(find.widgetWithText(ListTile, 'Delete account'));
      await tester.pumpAndSettle();
      expect(find.byType(TextField), findsNothing);
      expect(find.textContaining('sign in with Google again'), findsOneWidget);
      await tester.tap(find.widgetWithText(FilledButton, 'Delete account'));
      await tester.pumpAndSettle();
    }

    testWidgets('signs in with Google, deletes with the token and returns to sign-in', (
      tester,
    ) async {
      final google = FakeProviderSignIn.google('fresh-google-token');
      await _openProfile(tester, google: google);

      await confirmDialog(tester);

      expect(google.calls, 1);
      expect(client.deletedViaProvider, [
        ['google', 'fresh-google-token', null],
      ]);
      expect(client.deletedWith, isEmpty);
      expect(find.widgetWithText(FilledButton, 'Sign in'), findsOneWidget);
      expect(storage.saved, isNull);
    });

    testWidgets('an Apple-linked account on iOS confirms with Apple and its nonce', (
      tester,
    ) async {
      client.onFetchMe = () async =>
          fakeProfile(providers: ['apple', 'google'], hasPassword: false);
      final apple = FakeProviderSignIn.apple('fresh-apple-token');
      final google = FakeProviderSignIn.google();
      await _openProfile(tester, google: google, apple: apple, platform: TargetPlatform.iOS);

      await tester.tap(find.widgetWithText(ListTile, 'Delete account'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Delete account'));
      await tester.pumpAndSettle();

      expect(apple.calls, 1);
      expect(google.calls, 0);
      expect(client.deletedViaProvider, [
        ['apple', 'fresh-apple-token', 'raw-nonce'],
      ]);
    });

    testWidgets('cancelling the provider sheet stays on the profile without an error', (
      tester,
    ) async {
      final google = FakeProviderSignIn(null);
      await _openProfile(tester, google: google);

      await confirmDialog(tester);

      expect(google.calls, 1);
      expect(client.deletedViaProvider, isEmpty);
      expect(find.text('Profile'), findsOneWidget);
      expect(find.byType(SnackBar), findsNothing);
      expect(storage.saved, savedSession);
    });

    testWidgets('a rejected provider token shows the message and keeps the account', (
      tester,
    ) async {
      client.onDeleteWithProvider = (_, _, _) async =>
          throw apiError(403, 'invalid_provider_token', 'server wording');
      await _openProfile(tester, google: FakeProviderSignIn.google());

      await confirmDialog(tester);

      expect(find.text("Couldn't confirm with Google"), findsOneWidget);
      expect(find.text('Profile'), findsOneWidget);
      expect(storage.saved, savedSession);
    });

    testWidgets('cancelling the dialog does not open the provider sheet', (tester) async {
      final google = FakeProviderSignIn.google();
      await _openProfile(tester, google: google);

      await tester.tap(find.widgetWithText(ListTile, 'Delete account'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(google.calls, 0);
      expect(client.deletedViaProvider, isEmpty);
    });
  });

  testWidgets('an account with a password still confirms with the password dialog', (
    tester,
  ) async {
    client.onFetchMe = () async => fakeProfile(providers: ['google']);
    final google = FakeProviderSignIn.google();
    await _openProfile(tester, google: google);

    await tester.tap(find.widgetWithText(ListTile, 'Delete account'));
    await tester.pumpAndSettle();
    expect(find.byType(TextField), findsOneWidget);
    await tester.enterText(find.byType(TextField), 'password-1');
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, 'Delete account'));
    await tester.pumpAndSettle();

    expect(client.deletedWith, ['password-1']);
    expect(google.calls, 0);
  });
}
