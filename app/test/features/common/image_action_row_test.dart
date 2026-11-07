import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/common/image_action_row.dart';
import 'package:image_edit/services/app_settings.dart';
import 'package:image_edit/services/image_actions.dart';

import '../../support/fake_app_settings.dart';
import '../../support/fake_image_actions.dart';
import '../../support/fake_image_picker.dart';

Future<FakeImageActions> _pump(
  WidgetTester tester,
  FakeAppSettings settings,
) async {
  final actions = FakeImageActions();
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        imageActionsProvider.overrideWithValue(actions),
        showImageActionsProvider.overrideWithValue(true),
        appSettingsProvider.overrideWithValue(settings),
      ],
      child: MaterialApp(
        home: Scaffold(
          body: ImageActionRow(bytes: tinyPng, name: 'job-1', jobId: 'job-1'),
        ),
      ),
    ),
  );
  return actions;
}

void main() {
  testWidgets('a denied download offers Settings, which opens the app page', (
    tester,
  ) async {
    final settings = FakeAppSettings();
    final actions = await _pump(tester, settings);
    actions.saveResult = SaveResult.permissionDenied;

    await tester.tap(find.text('Download'));
    await tester.pumpAndSettle();
    expect(
      find.textContaining('Photo library access is required'),
      findsOneWidget,
    );

    await tester.tap(find.text('Settings'));
    await tester.pumpAndSettle();

    expect(settings.openCount, 1);
    expect(find.text('Could not open Settings.'), findsNothing);
  });

  testWidgets('says so when Settings cannot be opened', (tester) async {
    final settings = FakeAppSettings(opens: false);
    final actions = await _pump(tester, settings);
    actions.saveResult = SaveResult.permissionDenied;

    await tester.tap(find.text('Download'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Settings'));
    await tester.pumpAndSettle();

    expect(settings.openCount, 1);
    expect(find.text('Could not open Settings.'), findsOneWidget);
  });

  testWidgets('a saved or failed download has no Settings action', (
    tester,
  ) async {
    final actions = await _pump(tester, FakeAppSettings());

    await tester.tap(find.text('Download'));
    await tester.pumpAndSettle();
    expect(find.text('Saved to your photo library.'), findsOneWidget);
    expect(find.text('Settings'), findsNothing);

    ScaffoldMessenger.of(tester.element(find.byType(ImageActionRow)))
        .clearSnackBars();
    actions.saveError = Exception('disk');
    await tester.tap(find.text('Download'));
    await tester.pumpAndSettle();
    expect(find.text('Could not save the image.'), findsOneWidget);
    expect(find.text('Settings'), findsNothing);
  });
}
