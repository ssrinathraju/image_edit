import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fake_api_client.dart';
import '../../support/fake_provider_sign_in.dart';
import '../../support/profile_harness.dart';

late FakeApiClient client;

Finder _row(String label) => find.widgetWithText(ListTile, label);

Future<void> _scrollTo(WidgetTester tester, Finder finder) => tester.scrollUntilVisible(
      finder,
      200,
      scrollable: find.byType(Scrollable).first,
    );

void main() {
  setUp(() => client = FakeApiClient());

  testWidgets('a password account sees Change password, Change email and Google with Link', (
    tester,
  ) async {
    await openProfile(tester, client: client, google: FakeProviderSignIn.google());
    await _scrollTo(tester, _row('Change email'));

    expect(find.text('Sign-in & security'), findsOneWidget);
    expect(_row('Change password'), findsOneWidget);
    expect(_row('Set a password'), findsNothing);
    expect(_row('Change email'), findsOneWidget);
    expect(find.descendant(of: _row('Google'), matching: find.text('Not linked')), findsOneWidget);
  });

  testWidgets('a provider-only account sees Set a password and Google linked', (tester) async {
    client.onFetchMe = () async => fakeProfile(providers: ['google'], hasPassword: false);

    await openProfile(tester, client: client, google: FakeProviderSignIn.google());
    await _scrollTo(tester, _row('Change email'));

    expect(_row('Set a password'), findsOneWidget);
    expect(_row('Change password'), findsNothing);
    expect(find.descendant(of: _row('Google'), matching: find.text('Linked')), findsOneWidget);
  });

  testWidgets('a provider that is not configured in the app has no row', (tester) async {
    await openProfile(tester, client: client);
    await _scrollTo(tester, _row('Change email'));

    expect(_row('Google'), findsNothing);
    expect(_row('Apple'), findsNothing);
  });

  testWidgets('the Apple row shows on iOS when configured, and never on Android', (tester) async {
    final apple = FakeProviderSignIn.apple();
    await openProfile(
      tester,
      client: client,
      apple: apple,
      platform: TargetPlatform.iOS,
    );
    await _scrollTo(tester, _row('Change email'));
    expect(_row('Apple'), findsOneWidget);
  });

  testWidgets('the Apple row is hidden on Android', (tester) async {
    await openProfile(tester, client: client, google: FakeProviderSignIn.google());
    await _scrollTo(tester, _row('Change email'));

    expect(_row('Apple'), findsNothing);
  });
}
