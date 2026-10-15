import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/auth/session_notifier.dart';
import 'package:image_edit/features/common/generation_request.dart';
import 'package:image_edit/features/common/submit_controller.dart';
import 'package:image_edit/schemas/session.dart';
import 'package:image_edit/services/generation_providers.dart';
import 'package:image_picker/image_picker.dart';

import '../../support/fake_api_client.dart';
import '../../support/fake_image_picker.dart';
import '../../support/fake_session_storage.dart';

DioException _status(int code) => DioException(
      requestOptions: RequestOptions(path: '/me'),
      response: Response(
        requestOptions: RequestOptions(path: '/me'),
        statusCode: code,
      ),
    );

ProviderContainer _container(FakeApiClient client, FakeSessionStorage storage) {
  final container = ProviderContainer(
    overrides: [
      apiClientProvider.overrideWithValue(client),
      sessionStorageProvider.overrideWithValue(storage),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  late FakeApiClient client;
  late FakeSessionStorage storage;

  setUp(() {
    client = FakeApiClient();
    storage = FakeSessionStorage();
  });

  test('restore: a saved session the server accepts is kept', () async {
    storage.saved = savedSession;
    final container = _container(client, storage);

    final session = await container.read(sessionProvider.future);

    expect(session, savedSession);
    expect(container.read(sessionTokenHolderProvider).token, 'saved-token');
  });

  test('restore: nothing saved means signed out', () async {
    final container = _container(client, storage);

    expect(await container.read(sessionProvider.future), isNull);
  });

  test('restore: a 401 clears storage and signs out', () async {
    storage.saved = savedSession;
    client.onFetchMe = () async => throw _status(401);
    final container = _container(client, storage);

    expect(await container.read(sessionProvider.future), isNull);
    expect(storage.saved, isNull);
    expect(container.read(sessionTokenHolderProvider).token, isNull);
  });

  test('restore: offline keeps the token and reports an error', () async {
    storage.saved = savedSession;
    client.onFetchMe = () async => throw DioException(
          requestOptions: RequestOptions(path: '/me'),
          type: DioExceptionType.connectionError,
        );
    final container = _container(client, storage);
    container.listen(sessionProvider, (_, _) {});

    await expectLater(
      container.read(sessionProvider.future),
      throwsA(isA<DioException>()),
    );
    expect(container.read(sessionProvider).hasError, isTrue);
    expect(storage.saved, savedSession);

    client.onFetchMe =
        () async => const UserProfile(id: 'user-1', email: 'ana@example.com');
    container.read(sessionProvider.notifier).retryRestore();
    expect(await container.read(sessionProvider.future), savedSession);
  });

  test('signIn stores the session and exposes its token', () async {
    final container = _container(client, storage);
    await container.read(sessionProvider.future);

    await container
        .read(sessionProvider.notifier)
        .signIn(email: 'ana@example.com', password: 'password-1');

    final session = container.read(sessionProvider).value!;
    expect(session.email, 'ana@example.com');
    expect(storage.saved, session);
    expect(container.read(sessionTokenHolderProvider).token, session.token);
  });

  test('signIn failure leaves the user signed out and rethrows', () async {
    client.onLogin = (_, _) async => throw _status(401);
    final container = _container(client, storage);
    await container.read(sessionProvider.future);

    await expectLater(
      container
          .read(sessionProvider.notifier)
          .signIn(email: 'ana@example.com', password: 'wrong'),
      throwsA(isA<DioException>()),
    );
    expect(container.read(sessionProvider).value, isNull);
    expect(storage.saved, isNull);
  });

  test('signOut works offline and still clears the local session', () async {
    storage.saved = savedSession;
    client.onLogout = () async => throw DioException(
          requestOptions: RequestOptions(path: '/auth/logout'),
          type: DioExceptionType.connectionError,
        );
    final container = _container(client, storage);
    await container.read(sessionProvider.future);

    await container.read(sessionProvider.notifier).signOut();

    expect(container.read(sessionProvider).value, isNull);
    expect(storage.saved, isNull);
    expect(client.logoutCalls, 1);
  });

  test('expire clears the session and the remembered request', () async {
    storage.saved = savedSession;
    final container = _container(client, storage);
    await container.read(sessionProvider.future);
    container.read(lastRequestProvider.notifier).state = (
      jobId: 'job-1',
      request: GenerationRequest(
        photo: XFile.fromData(tinyPng, name: 'me.png'),
        prompt: 'hello',
      ),
    );

    await container.read(sessionProvider.notifier).expire();

    expect(container.read(sessionProvider).value, isNull);
    expect(storage.saved, isNull);
    expect(container.read(lastRequestProvider), isNull);
  });

  test('deleteAccount with a wrong password keeps the session', () async {
    storage.saved = savedSession;
    client.onDeleteAccount = (_) async => throw _status(403);
    final container = _container(client, storage);
    await container.read(sessionProvider.future);

    await expectLater(
      container.read(sessionProvider.notifier).deleteAccount(password: 'nope'),
      throwsA(isA<DioException>()),
    );
    expect(container.read(sessionProvider).value, savedSession);
    expect(storage.saved, savedSession);
  });

  test('deleteAccount success signs out locally', () async {
    storage.saved = savedSession;
    final container = _container(client, storage);
    await container.read(sessionProvider.future);

    await container
        .read(sessionProvider.notifier)
        .deleteAccount(password: 'password-1');

    expect(client.deletedWith, ['password-1']);
    expect(container.read(sessionProvider).value, isNull);
    expect(storage.saved, isNull);
  });
}
