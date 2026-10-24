import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'app_harness.dart';
import 'fake_api_client.dart';
import 'fake_provider_sign_in.dart';
import 'fake_session_storage.dart';

/// Pumps the whole app signed in and opens the profile screen.
Future<void> openProfile(
  WidgetTester tester, {
  required FakeApiClient client,
  FakeProviderSignIn? google,
  FakeProviderSignIn? apple,
  bool? appleAvailable,
  TargetPlatform platform = TargetPlatform.android,
}) async {
  await pumpApp(
    tester,
    client: client,
    storage: FakeSessionStorage(savedSession),
    google: google,
    apple: apple,
    appleAvailable: appleAvailable,
    platform: platform,
  );
  await tester.tap(find.byTooltip('Profile'));
  await tester.pumpAndSettle();
}

/// Scrolls the profile list to the tile titled [label] and taps it.
Future<void> tapTile(WidgetTester tester, String label) async {
  final tile = find.widgetWithText(ListTile, label);
  await tester.scrollUntilVisible(tile, 200, scrollable: find.byType(Scrollable).first);
  await tester.tap(tile);
  await tester.pumpAndSettle();
}

/// Scrolls to the tile titled [row] and taps its [action] button.
Future<void> tapRowAction(WidgetTester tester, String row, String action) async {
  final tile = find.widgetWithText(ListTile, row);
  await tester.scrollUntilVisible(tile, 200, scrollable: find.byType(Scrollable).first);
  await tester.tap(find.descendant(of: tile, matching: find.text(action)));
  await tester.pumpAndSettle();
}

Future<void> enterPassword(WidgetTester tester, String label, String value) async {
  await tester.enterText(find.widgetWithText(TextField, label), value);
  await tester.pump();
}

Finder fieldText(String label) => find.widgetWithText(TextField, label);
