import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/template_detail/template_screen.dart';

import '../../support/fake_api_client.dart';
import '../../support/screen_harness.dart';

void main() {
  final template = fakeTemplate('beach', title: 'Golden Beach');

  testWidgets('has no prompt field and blocks Generate without a photo', (tester) async {
    await pumpScreen(
      tester,
      client: FakeApiClient(),
      screen: TemplateScreen(templateId: 'beach', template: template),
    );

    expect(find.text('Golden Beach'), findsOneWidget);
    expect(find.byType(TextField), findsNothing);
    expect(isGenerateEnabled(tester), isFalse);
  });

  testWidgets('submits the template id and opens the status screen', (tester) async {
    final client = FakeApiClient();
    await pumpScreen(
      tester,
      client: client,
      screen: TemplateScreen(templateId: 'beach', template: template),
    );

    await pickPhoto(tester);
    expect(isGenerateEnabled(tester), isTrue);
    await tester.tap(find.text('Generate'));
    await tester.pumpAndSettle();

    expect(client.submitted.single.templateId, 'beach');
    expect(client.submitted.single.prompt, isNull);
    expect(find.text('status:job-1'), findsOneWidget);
  });

  testWidgets('shows an error and stays put when submission fails', (tester) async {
    final client = FakeApiClient()
      ..onSubmit = (_) async => throw DioException(
            requestOptions: RequestOptions(path: '/generations'),
          );
    await pumpScreen(
      tester,
      client: client,
      screen: TemplateScreen(templateId: 'beach', template: template),
    );

    await pickPhoto(tester);
    await tester.tap(find.text('Generate'));
    await tester.pumpAndSettle();

    expect(find.textContaining('Could not reach the server'), findsOneWidget);
    expect(find.text('Golden Beach'), findsOneWidget);
    expect(isGenerateEnabled(tester), isTrue);
  });

  testWidgets('looks the template up when it was not passed in', (tester) async {
    final client = FakeApiClient()
      ..onListTemplates = (_) async => [fakeTemplate('beach', title: 'Looked Up')];
    await pumpScreen(
      tester,
      client: client,
      screen: const TemplateScreen(templateId: 'beach'),
    );

    expect(find.text('Looked Up'), findsOneWidget);
  });

  testWidgets('reports an unknown template', (tester) async {
    await pumpScreen(
      tester,
      client: FakeApiClient(),
      screen: const TemplateScreen(templateId: 'gone'),
    );

    expect(find.text('This template is no longer available.'), findsOneWidget);
  });
}
