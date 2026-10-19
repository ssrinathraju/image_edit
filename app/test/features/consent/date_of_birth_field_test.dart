import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/common/clock.dart';
import 'package:image_edit/features/consent/date_of_birth_field.dart';

void main() {
  testWidgets('the real picker opens 18 years back and returns the chosen date', (tester) async {
    DateTime? chosen;
    await tester.pumpWidget(
      ProviderScope(
        overrides: [clockProvider.overrideWithValue(() => DateTime(2026, 10, 20))],
        child: MaterialApp(
          home: Scaffold(
            body: DateOfBirthField(value: null, onChanged: (date) => chosen = date),
          ),
        ),
      ),
    );
    expect(find.text('Choose a date'), findsOneWidget);

    await tester.tap(find.byType(DateOfBirthField));
    await tester.pumpAndSettle();
    await tester.tap(find.text('OK'));
    await tester.pumpAndSettle();

    expect(chosen, DateTime(2008, 10, 20));
  });

  testWidgets('a chosen date is shown as YYYY-MM-DD and a disabled field does not open', (tester) async {
    var changed = 0;
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          home: Scaffold(
            body: DateOfBirthField(
              value: DateTime(1990, 1, 31),
              enabled: false,
              onChanged: (_) => changed++,
            ),
          ),
        ),
      ),
    );

    expect(find.text('1990-01-31'), findsOneWidget);
    await tester.tap(find.byType(DateOfBirthField));
    await tester.pumpAndSettle();

    expect(find.text('OK'), findsNothing);
    expect(changed, 0);
  });
}
