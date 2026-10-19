import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/auth/session_notifier.dart';
import 'package:image_edit/features/consent/consent_text.dart';
import 'package:image_edit/features/custom_generation/custom_generation_screen.dart';
import 'package:image_edit/features/plans/account_notifier.dart';
import 'package:image_edit/features/profile/profile_providers.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_session_storage.dart';
import '../../support/screen_harness.dart';

late FakeApiClient client;
late String acceptedVersion;
late String currentVersion;

Future<void> _pumpCreate(
  WidgetTester tester, {
  List<Override> overrides = const [],
}) async {
  await pumpScreen(
    tester,
    client: client,
    screen: const CustomGenerationScreen(),
    overrides: [
      sessionStorageProvider.overrideWithValue(FakeSessionStorage(savedSession)),
      ...overrides,
    ],
  );
  final container = ProviderScope.containerOf(tester.element(find.byType(MaterialApp)));
  container.read(accountProvider);
  for (var i = 0; i < 50 && container.read(accountProvider).valueOrNull == null; i++) {
    await tester.pump(const Duration(milliseconds: 10));
  }
}

Future<void> _fillAndGenerate(WidgetTester tester) async {
  await tester.enterText(find.byType(TextField), 'a cat in space');
  await tester.pump();
  await pickPhoto(tester);
  await tester.tap(find.text('Generate'));
  await tester.pumpAndSettle();
}

void main() {
  setUp(() {
    dotenv.testLoad(fileInput: '');
    client = FakeApiClient();
    acceptedVersion = '';
    currentVersion = '1';
    client.onFetchMe = () async => fakeProfile(
          consentGiven: acceptedVersion.isNotEmpty,
          acceptedConsentVersion: acceptedVersion,
          currentConsentVersion: currentVersion,
        );
    client.onAcceptConsent = (version) async => acceptedVersion = version;
  });

  testWidgets('the first submission asks for consent before anything is uploaded', (tester) async {
    await _pumpCreate(tester);

    await _fillAndGenerate(tester);

    expect(find.text('Face photo consent'), findsOneWidget);
    expect(find.text(consentTextFor('1')!.points.first), findsOneWidget);
    expect(find.text(consentTextFor('1')!.points[1]), findsOneWidget);
    expect(find.text(consentTextFor('1')!.points[2]), findsOneWidget);
    expect(find.text(consentTextFor('1')!.points[3]), findsOneWidget);
    expect(client.submitted, isEmpty);
  });

  testWidgets('accepting records the version and submits the same request', (tester) async {
    await _pumpCreate(tester);
    await _fillAndGenerate(tester);

    await tester.tap(find.widgetWithText(FilledButton, 'Accept'));
    await tester.pumpAndSettle();

    expect(client.acceptedConsents, ['1']);
    expect(client.submitted, hasLength(1));
    expect(client.submitted.single.prompt, 'a cat in space');
    expect(find.text('status:job-1'), findsOneWidget);
  });

  testWidgets('declining returns to the form with the photo and prompt kept', (tester) async {
    await _pumpCreate(tester);
    await _fillAndGenerate(tester);

    await tester.tap(find.widgetWithText(TextButton, 'Decline'));
    await tester.pumpAndSettle();

    expect(client.submitted, isEmpty);
    expect(client.acceptedConsents, isEmpty);
    expect(tester.widget<TextField>(find.byType(TextField)).controller!.text, 'a cat in space');
    expect(isGenerateEnabled(tester), isTrue);
    expect(find.text('Face photo consent'), findsNothing);
  });

  testWidgets('a consenting account submits without the consent screen', (tester) async {
    acceptedVersion = '1';
    await _pumpCreate(tester);

    await _fillAndGenerate(tester);

    expect(find.text('Face photo consent'), findsNothing);
    expect(client.submitted, hasLength(1));
    expect(find.text('status:job-1'), findsOneWidget);
  });

  testWidgets('a consent version the app has no text for cannot be accepted', (tester) async {
    acceptedVersion = '1';
    currentVersion = '2';
    await _pumpCreate(tester);

    await _fillAndGenerate(tester);

    expect(find.text('Face photo consent'), findsOneWidget);
    expect(find.text('Update the app to continue'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Accept'), findsNothing);
    expect(client.acceptedConsents, isEmpty);
    expect(client.submitted, isEmpty);
  });

  testWidgets('a server consent_required opens the screen and retries once after Accept', (tester) async {
    acceptedVersion = '1';
    var refused = true;
    client.onSubmit = (_) async {
      if (refused) {
        refused = false;
        acceptedVersion = '';
        throw apiError(403, 'consent_required', 'accept consent first');
      }
      return 'job-9';
    };
    await _pumpCreate(tester);

    await _fillAndGenerate(tester);
    expect(find.text('Face photo consent'), findsOneWidget);
    expect(client.submitted, hasLength(1));

    await tester.tap(find.widgetWithText(FilledButton, 'Accept'));
    await tester.pumpAndSettle();

    expect(client.submitted, hasLength(2));
    expect(find.text('status:job-9'), findsOneWidget);
  });

  testWidgets('declining after a server consent_required submits nothing more', (tester) async {
    acceptedVersion = '1';
    client.onSubmit = (_) async {
      acceptedVersion = '';
      throw apiError(403, 'consent_required', 'accept consent first');
    };
    await _pumpCreate(tester);

    await _fillAndGenerate(tester);
    await tester.tap(find.widgetWithText(TextButton, 'Decline'));
    await tester.pumpAndSettle();

    expect(client.submitted, hasLength(1));
    expect(isGenerateEnabled(tester), isTrue);
  });

  testWidgets('a server age_not_confirmed sends the user to Confirm your age', (tester) async {
    acceptedVersion = '1';
    client.onSubmit = (_) async =>
        throw apiError(403, 'age_not_confirmed', 'confirm your age first');
    await _pumpCreate(tester);

    await _fillAndGenerate(tester);

    expect(find.text('confirm-age-screen'), findsOneWidget);
  });

  testWidgets('a version change while the screen is open stops at an unknown version', (tester) async {
    await _pumpCreate(tester);
    await _fillAndGenerate(tester);
    client.onAcceptConsent = (_) async {
      currentVersion = '2';
      throw apiError(400, 'consent_version_mismatch', 'current version is 2');
    };

    await tester.tap(find.widgetWithText(FilledButton, 'Accept'));
    await tester.pumpAndSettle();

    expect(find.text('Update the app to continue'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Accept'), findsNothing);
    expect(client.acceptedConsents, ['1']);
    expect(client.submitted, isEmpty);
  });

  testWidgets('a failed Accept keeps the screen and submits nothing', (tester) async {
    client.onAcceptConsent = (_) async => throw StateError('offline');
    await _pumpCreate(tester);
    await _fillAndGenerate(tester);

    await tester.tap(find.widgetWithText(FilledButton, 'Accept'));
    await tester.pumpAndSettle();

    expect(find.text("Couldn't save your choice, try again"), findsOneWidget);
    expect(client.submitted, isEmpty);
  });

  testWidgets('the privacy policy link opens when configured', (tester) async {
    final launcher = FakeLinkLauncher();
    await _pumpCreate(
      tester,
      overrides: [
        profileLinksProvider.overrideWithValue(
          const ProfileLinks(privacyUrl: 'https://example.com/privacy'),
        ),
        linkLauncherProvider.overrideWithValue(launcher),
      ],
    );
    await _fillAndGenerate(tester);

    await tester.tap(find.text('Privacy policy'));
    await tester.pumpAndSettle();

    expect(launcher.opened, [Uri.parse('https://example.com/privacy')]);
  });

  testWidgets('without a configured privacy URL there is no link', (tester) async {
    await _pumpCreate(tester);

    await _fillAndGenerate(tester);

    expect(find.text('Privacy policy'), findsNothing);
  });

  test('a version the app has no text for has no text', () {
    expect(consentTextFor('99'), isNull);
  });
}
