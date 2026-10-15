import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/router.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';
import '../../support/fake_session_storage.dart';

Future<void> _openInvite(
  WidgetTester tester,
  FakeApiClient client, {
  required FakeShare share,
  String? inviteUrl,
}) async {
  final container = await pumpApp(
    tester,
    client: client,
    storage: FakeSessionStorage(savedSession),
    share: share,
    inviteUrl: inviteUrl,
  );
  container.read(routerProvider).go('/invite');
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('shows the code and how many friends were rewarded', (tester) async {
    final client = FakeApiClient()
      ..onFetchMe = () async => fakeProfile(rewards: 3, code: 'K7M2QX9P');

    await _openInvite(tester, client, share: FakeShare());

    expect(find.text('K7M2QX9P'), findsOneWidget);
    expect(find.text('3 of 10 friends rewarded'), findsOneWidget);
  });

  testWidgets('Share sends a message containing the code', (tester) async {
    final share = FakeShare();
    final client = FakeApiClient()..onFetchMe = () async => fakeProfile(code: 'K7M2QX9P');
    await _openInvite(tester, client, share: share);

    await tester.tap(find.text('Share'));
    await tester.pumpAndSettle();

    expect(share.texts.single, contains('K7M2QX9P'));
    expect(share.texts.single, isNot(contains('http')));
  });

  testWidgets('the invite link is appended when configured', (tester) async {
    final share = FakeShare();
    final client = FakeApiClient()..onFetchMe = () async => fakeProfile(code: 'K7M2QX9P');
    await _openInvite(
      tester,
      client,
      share: share,
      inviteUrl: 'https://example.com/get',
    );

    await tester.tap(find.text('Share'));
    await tester.pumpAndSettle();

    expect(share.texts.single, contains('K7M2QX9P'));
    expect(share.texts.single, endsWith('https://example.com/get'));
  });

  testWidgets('without referral data the screen explains and offers no Share', (tester) async {
    await _openInvite(tester, FakeApiClient(), share: FakeShare());

    expect(find.text('Share'), findsNothing);
    expect(find.textContaining('not available'), findsOneWidget);
  });
}
