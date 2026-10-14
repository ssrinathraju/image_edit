import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/custom_generation/custom_generation_screen.dart';

import '../../support/fake_api_client.dart';
import '../../support/screen_harness.dart';

void main() {
  testWidgets('pre-fills the prompt and shows a multi-line field', (tester) async {
    await pumpScreen(
      tester,
      client: FakeApiClient(),
      screen: const CustomGenerationScreen(initialPrompt: 'astronaut on mars'),
    );

    final field = tester.widget<TextField>(find.byType(TextField));
    expect(field.controller!.text, 'astronaut on mars');
    expect(field.minLines, greaterThanOrEqualTo(4));
  });

  testWidgets('blank prompt keeps Generate disabled even with a photo', (tester) async {
    await pumpScreen(
      tester,
      client: FakeApiClient(),
      screen: const CustomGenerationScreen(),
    );

    await pickPhoto(tester);
    expect(isGenerateEnabled(tester), isFalse);

    await tester.enterText(find.byType(TextField), '   ');
    await tester.pump();
    expect(isGenerateEnabled(tester), isFalse);
  });

  testWidgets('an overlong prompt shows a validation message', (tester) async {
    await pumpScreen(
      tester,
      client: FakeApiClient(),
      screen: const CustomGenerationScreen(),
    );

    await pickPhoto(tester);
    await tester.enterText(find.byType(TextField), 'x' * 501);
    await tester.pump();

    expect(find.textContaining('500 characters or fewer'), findsOneWidget);
    expect(isGenerateEnabled(tester), isFalse);
  });

  testWidgets('submits the trimmed prompt and opens the status screen', (tester) async {
    final client = FakeApiClient();
    await pumpScreen(
      tester,
      client: client,
      screen: const CustomGenerationScreen(),
    );

    await tester.enterText(find.byType(TextField), '  a cat in space  ');
    await tester.pump();
    expect(isGenerateEnabled(tester), isFalse);
    await pickPhoto(tester);
    expect(isGenerateEnabled(tester), isTrue);
    await tester.tap(find.text('Generate'));
    await tester.pumpAndSettle();

    expect(client.submitted.single.prompt, 'a cat in space');
    expect(client.submitted.single.templateId, isNull);
    expect(find.text('status:job-1'), findsOneWidget);
  });
}
