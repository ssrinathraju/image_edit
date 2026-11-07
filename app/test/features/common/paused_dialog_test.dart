import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/common/paused_dialog.dart';

Future<void> _open(
  WidgetTester tester, {
  required DateTime until,
  required DateTime Function(DateTime) toLocal,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Builder(
        builder: (context) => TextButton(
          onPressed: () =>
              showPausedDialog(context, until: until, toLocal: toLocal),
          child: const Text('open'),
        ),
      ),
    ),
  );
  await tester.tap(find.text('open'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('the end time is shown after the local-time conversion', (
    tester,
  ) async {
    // 21:05 UTC in a +05:30 zone is already the next day, so a missing
    // conversion changes both the date and the time.
    final until = DateTime.utc(2026, 10, 21, 21, 5);

    await _open(
      tester,
      until: until,
      toLocal: (utc) => utc.add(const Duration(hours: 5, minutes: 30)),
    );

    expect(find.textContaining('until Thu, Oct 22, 2:35 AM'), findsOneWidget);
  });
}
