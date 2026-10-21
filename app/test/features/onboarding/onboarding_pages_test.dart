import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/onboarding/onboarding_pages.dart';

Future<void> _pump(WidgetTester tester, VoidCallback onDone) => tester.pumpWidget(
      MaterialApp(home: Scaffold(body: OnboardingPages(onDone: onDone))),
    );

void main() {
  testWidgets('each page says its message', (tester) async {
    await _pump(tester, () {});
    expect(find.textContaining('trending template'), findsOneWidget);
    expect(find.textContaining('describe your own scene'), findsOneWidget);
    expect(find.textContaining('photo of yourself'), findsOneWidget);

    await tester.tap(find.text('Next'));
    await tester.pumpAndSettle();
    expect(find.textContaining('then deleted'), findsOneWidget);
    expect(find.textContaining('saved on this device'), findsOneWidget);
    expect(find.textContaining('after 24 hours'), findsOneWidget);

    await tester.tap(find.text('Next'));
    await tester.pumpAndSettle();
    expect(find.textContaining('18 or older'), findsOneWidget);
    expect(find.textContaining('people who agreed'), findsOneWidget);
    expect(find.textContaining('Unsafe content is blocked'), findsOneWidget);
  });

  testWidgets('Next and swiping back move between pages, the indicator following',
      (tester) async {
    await _pump(tester, () {});
    expect(find.bySemanticsLabel('Page 1 of 3'), findsOneWidget);

    await tester.tap(find.text('Next'));
    await tester.pumpAndSettle();
    expect(find.text('Your privacy'), findsOneWidget);
    expect(find.bySemanticsLabel('Page 2 of 3'), findsOneWidget);

    await tester.fling(find.byType(PageView), const Offset(400, 0), 1000);
    await tester.pumpAndSettle();
    expect(find.text('How it works'), findsOneWidget);
    expect(find.bySemanticsLabel('Page 1 of 3'), findsOneWidget);
  });

  testWidgets('Skip on every page calls onDone', (tester) async {
    var done = 0;
    await _pump(tester, () => done++);

    for (var page = 0; page < 3; page++) {
      await tester.tap(find.text('Skip'));
      expect(done, page + 1);
      if (page < 2) {
        await tester.tap(find.text('Next'));
        await tester.pumpAndSettle();
      }
    }
  });

  testWidgets('Get started replaces Next on the last page and calls onDone',
      (tester) async {
    var done = 0;
    await _pump(tester, () => done++);
    expect(find.text('Get started'), findsNothing);

    await tester.tap(find.text('Next'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Next'));
    await tester.pumpAndSettle();

    expect(find.text('Next'), findsNothing);
    await tester.tap(find.text('Get started'));
    expect(done, 1);
  });
}
