import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:image_edit/features/common/photo_picker_field.dart';
import 'package:image_edit/services/generation_providers.dart';
import 'package:image_picker/image_picker.dart';

import 'fake_api_client.dart';
import 'fake_image_picker.dart';

Future<void> pumpScreen(
  WidgetTester tester, {
  required Widget screen,
  required FakeApiClient client,
  FakeImagePicker? picker,
  List<Override> overrides = const [],
}) async {
  tester.view.physicalSize = const Size(430, 932);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);

  final router = GoRouter(
    routes: [
      GoRoute(path: '/', builder: (_, _) => screen),
      GoRoute(path: '/upgrade', builder: (_, _) => const Text('upgrade-screen')),
      GoRoute(path: '/invite', builder: (_, _) => const Text('invite-screen')),
      GoRoute(
        path: '/status/:jobId',
        builder: (_, state) => Text('status:${state.pathParameters['jobId']}'),
      ),
    ],
  );
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(client),
        imagePickerProvider.overrideWithValue(
          picker ?? FakeImagePicker(result: XFile.fromData(tinyPng, name: 'me.png')),
        ),
        ...overrides,
      ],
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> pickPhoto(WidgetTester tester) async {
  await tester.tap(find.byType(PhotoPickerField));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Choose from library'));
  await tester.pumpAndSettle();
}

bool isGenerateEnabled(WidgetTester tester) {
  final button = tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Generate'));
  return button.onPressed != null;
}
