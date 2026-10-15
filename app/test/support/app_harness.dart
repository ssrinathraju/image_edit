import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';
import 'package:image_edit/features/auth/session_notifier.dart';
import 'package:image_edit/features/common/photo_picker_field.dart';
import 'package:image_edit/features/plans/invite_screen.dart';
import 'package:image_edit/features/profile/profile_providers.dart';
import 'package:image_edit/router.dart';
import 'package:image_edit/services/generation_providers.dart';

import 'fake_api_client.dart';
import 'fake_image_picker.dart';
import 'fake_session_storage.dart';

class FakeLinkLauncher implements LinkLauncher {
  final opened = <Uri>[];
  bool result = true;

  @override
  Future<bool> open(Uri uri) async {
    opened.add(uri);
    return result;
  }
}

class FakeShare {
  final texts = <String>[];

  Future<void> call(String text, {Rect? origin}) async => texts.add(text);
}

DioException apiError(int status, String code, String detail) => DioException(
      requestOptions: RequestOptions(path: '/x'),
      response: Response(
        requestOptions: RequestOptions(path: '/x'),
        statusCode: status,
        data: {
          'detail': {'error': code, 'detail': detail},
        },
      ),
    );

/// Pumps the whole app (real router and screens) against fakes.
Future<ProviderContainer> pumpApp(
  WidgetTester tester, {
  required FakeApiClient client,
  required FakeSessionStorage storage,
  ProfileLinks links = const ProfileLinks(),
  FakeLinkLauncher? launcher,
  FakeShare? share,
  String? inviteUrl,
  FakeImagePicker? picker,
  bool settle = true,
}) async {
  tester.view.physicalSize = const Size(430, 932);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(client),
        sessionStorageProvider.overrideWithValue(storage),
        profileLinksProvider.overrideWithValue(links),
        linkLauncherProvider.overrideWithValue(launcher ?? FakeLinkLauncher()),
        appVersionProvider.overrideWith((_) async => '1.2.3 (45)'),
        imagePickerProvider.overrideWithValue(
          picker ?? FakeImagePicker(result: XFile.fromData(tinyPng, name: 'me.png')),
        ),
        shareTextProvider.overrideWithValue((share ?? FakeShare()).call),
        inviteUrlProvider.overrideWithValue(inviteUrl),
      ],
      child: Consumer(
        builder: (context, ref, _) =>
            MaterialApp.router(routerConfig: ref.watch(routerProvider)),
      ),
    ),
  );
  if (settle) await tester.pumpAndSettle();
  return ProviderScope.containerOf(tester.element(find.byType(MaterialApp)));
}
