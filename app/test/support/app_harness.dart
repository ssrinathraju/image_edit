import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/auth/session_notifier.dart';
import 'package:image_edit/features/profile/profile_providers.dart';
import 'package:image_edit/router.dart';
import 'package:image_edit/services/generation_providers.dart';

import 'fake_api_client.dart';
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
