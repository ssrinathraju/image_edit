import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/core/provider_sign_in.dart';
import 'package:image_edit/features/auth/registration_draft.dart';
import 'package:image_edit/features/auth/session_notifier.dart';
import 'package:image_edit/features/common/generation_request.dart';
import 'package:image_edit/features/common/submit_controller.dart';
import 'package:image_edit/features/history/creation_store.dart';
import 'package:image_edit/schemas/session.dart';
import 'package:image_edit/services/generation_providers.dart';
import 'package:image_picker/image_picker.dart';

import '../../support/fake_api_client.dart';
import '../../support/fake_image_picker.dart';
import '../../support/fake_session_storage.dart';
import '../../support/in_memory_creation_store.dart';

DioException _status(int code) => DioException(
      requestOptions: RequestOptions(path: '/me'),
      response: Response(
        requestOptions: RequestOptions(path: '/me'),
        statusCode: code,
      ),
    );

ProviderContainer _container(
  FakeApiClient client,
  FakeSessionStorage storage, {
  InMemoryCreationStore? store,
}) {
  final container = ProviderContainer(
    overrides: [
      apiClientProvider.overrideWithValue(client),
      sessionStorageProvider.overrideWithValue(storage),
      creationStoreProvider.overrideWithValue(store ?? InMemoryCreationStore()),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

final _dob = DateTime(1990, 1, 31);

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

  test('startRegistration keeps a draft and creates no session', () async {
    final container = _container(client, storage);
    await container.read(sessionProvider.future);

    await container.read(sessionProvider.notifier).startRegistration(
          email: 'new@example.com',
          password: 'password-1',
          dateOfBirth: _dob,
          referralCode: 'K7M2QX9P',
        );

    final draft = container.read(registrationDraftProvider)!;
    expect((draft.email, draft.password, draft.referralCode),
        ('new@example.com', 'password-1', 'K7M2QX9P'));
    expect(container.read(sessionProvider).value, isNull);
    expect(storage.saved, isNull);
  });

  test('the draft keeps the date so Resend sends the registration again with it', () async {
    final container = _container(client, storage);
    await container.read(sessionProvider.future);
    final notifier = container.read(sessionProvider.notifier);
    await notifier.startRegistration(
      email: 'new@example.com',
      password: 'password-1',
      dateOfBirth: _dob,
    );

    await notifier.resendRegistrationCode();

    expect(client.registeredDates, [_dob, _dob]);
  });

  test('a provider sign-in passes the date of birth through', () async {
    final container = _container(client, storage);
    await container.read(sessionProvider.future);
    const credential = ProviderCredential(
      provider: SignInProvider.google,
      token: 'g-tok',
    );

    await container
        .read(sessionProvider.notifier)
        .signInWithProvider(credential, dateOfBirth: _dob);

    expect(client.googleDates, [_dob]);
  });

  test('a refused startRegistration leaves no draft', () async {
    client.onRegister = (_, _) async => throw _status(409);
    final container = _container(client, storage);
    await container.read(sessionProvider.future);

    await expectLater(
      container
          .read(sessionProvider.notifier)
          .startRegistration(
            email: 'a@b.co',
            password: 'password-1',
            dateOfBirth: _dob,
          ),
      throwsA(isA<DioException>()),
    );
    expect(container.read(registrationDraftProvider), isNull);
  });

  test('confirmRegistration signs in and clears the draft', () async {
    final container = _container(client, storage);
    await container.read(sessionProvider.future);
    final notifier = container.read(sessionProvider.notifier);
    await notifier.startRegistration(
      email: 'new@example.com',
      password: 'password-1',
      dateOfBirth: _dob,
    );

    await notifier.confirmRegistration(code: '123456');

    expect(client.confirmedRegistrations, [
      ['new@example.com', '123456', 'password-1'],
    ]);
    expect(container.read(sessionProvider).value!.email, 'new@example.com');
    expect(storage.saved?.email, 'new@example.com');
    expect(container.read(registrationDraftProvider), isNull);
  });

  test('signing in clears a registration draft', () async {
    final container = _container(client, storage);
    await container.read(sessionProvider.future);
    final notifier = container.read(sessionProvider.notifier);
    await notifier.startRegistration(
      email: 'new@example.com',
      password: 'password-1',
      dateOfBirth: _dob,
    );

    await notifier.signIn(email: 'a@b.co', password: 'password-1');

    expect(container.read(registrationDraftProvider), isNull);
  });

  test('a rejected confirmation keeps the draft and the user signed out', () async {
    client.onConfirmRegistration = (_, _) async => throw _status(400);
    final container = _container(client, storage);
    await container.read(sessionProvider.future);
    final notifier = container.read(sessionProvider.notifier);
    await notifier.startRegistration(
      email: 'new@example.com',
      password: 'password-1',
      dateOfBirth: _dob,
    );

    await expectLater(
      notifier.confirmRegistration(code: '000000'),
      throwsA(isA<DioException>()),
    );

    expect(container.read(registrationDraftProvider)!.email, 'new@example.com');
    expect(container.read(sessionProvider).value, isNull);
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

  Future<InMemoryCreationStore> storeWithCreations() async {
    final store = InMemoryCreationStore();
    for (final userId in ['user-1', 'user-2']) {
      await store.save(
        userId: userId,
        jobId: 'job-$userId',
        label: 'a label',
        bytes: tinyPng,
        finishedAt: DateTime.utc(2026, 10, 19),
      );
      await store.remember(
        userId: userId,
        jobId: 'pending-$userId',
        label: '',
        submittedAt: DateTime.utc(2026, 10, 19),
      );
    }
    return store;
  }

  test('deleteAccount removes the account creations and pending jobs', () async {
    storage.saved = savedSession;
    final store = await storeWithCreations();
    final container = _container(client, storage, store: store);
    await container.read(sessionProvider.future);

    await container
        .read(sessionProvider.notifier)
        .deleteAccount(password: 'password-1');

    expect(store.deletedAccounts, ['user-1']);
    expect(await store.list('user-1'), isEmpty);
    expect(await store.pending('user-1'), isEmpty);
    expect(await store.list('user-2'), hasLength(1));
  });

  test('deleteAccountWithProvider removes the account creations too', () async {
    storage.saved = savedSession;
    final store = await storeWithCreations();
    final container = _container(client, storage, store: store);
    await container.read(sessionProvider.future);

    await container.read(sessionProvider.notifier).deleteAccountWithProvider(
          const ProviderCredential(provider: SignInProvider.google, token: 'g-token'),
        );

    expect(store.deletedAccounts, ['user-1']);
    expect(await store.list('user-1'), isEmpty);
    expect(await store.pending('user-1'), isEmpty);
    expect(container.read(sessionProvider).value, isNull);
  });

  test('a server failure deletes nothing locally', () async {
    storage.saved = savedSession;
    client.onDeleteAccount = (_) async => throw _status(403);
    final store = await storeWithCreations();
    final container = _container(client, storage, store: store);
    await container.read(sessionProvider.future);

    await expectLater(
      container.read(sessionProvider.notifier).deleteAccount(password: 'nope'),
      throwsA(isA<DioException>()),
    );

    expect(store.deletedAccounts, isEmpty);
    expect(await store.list('user-1'), hasLength(1));
    expect(await store.pending('user-1'), hasLength(1));
  });

  test('a local delete that throws still signs out', () async {
    storage.saved = savedSession;
    final store = await storeWithCreations();
    store.deleteAccountError = StateError('disk gone');
    final container = _container(client, storage, store: store);
    await container.read(sessionProvider.future);

    await container
        .read(sessionProvider.notifier)
        .deleteAccount(password: 'password-1');

    expect(container.read(sessionProvider).value, isNull);
    expect(storage.saved, isNull);
  });

  test('signOut keeps the creations', () async {
    storage.saved = savedSession;
    final store = await storeWithCreations();
    final container = _container(client, storage, store: store);
    await container.read(sessionProvider.future);

    await container.read(sessionProvider.notifier).signOut();

    expect(store.deletedAccounts, isEmpty);
    expect(await store.list('user-1'), hasLength(1));
    expect(await store.pending('user-1'), hasLength(1));
    expect(container.read(sessionProvider).value, isNull);
  });
}
