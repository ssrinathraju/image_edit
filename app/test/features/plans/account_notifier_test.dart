import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/auth/session_notifier.dart';
import 'package:image_edit/features/plans/account_notifier.dart';
import 'package:image_edit/services/generation_providers.dart';

import '../../support/fake_api_client.dart';
import '../../support/fake_session_storage.dart';

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
  test('loads the account once signed in', () async {
    final client = FakeApiClient()
      ..onFetchMe = () async => fakeProfile(usedToday: 1);
    final container = _container(client, FakeSessionStorage(savedSession));
    await container.read(sessionProvider.future);

    final account = await container.read(accountProvider.future);

    expect(account!.usage!.usedToday, 1);
  });

  test('is null while signed out', () async {
    final container = _container(FakeApiClient(), FakeSessionStorage());
    await container.read(sessionProvider.future);

    expect(await container.read(accountProvider.future), isNull);
  });

  test('refresh picks up a usage change', () async {
    var used = 0;
    final client = FakeApiClient()
      ..onFetchMe = () async => fakeProfile(usedToday: used);
    final container = _container(client, FakeSessionStorage(savedSession));
    await container.read(sessionProvider.future);
    await container.read(accountProvider.future);

    used = 2;
    await container.read(accountProvider.notifier).refresh();

    expect(container.read(accountProvider).value!.usage!.usedToday, 2);
  });

  test('a failed refresh keeps what was already loaded', () async {
    var fail = false;
    final client = FakeApiClient()
      ..onFetchMe = () async {
        if (fail) throw StateError('offline');
        return fakeProfile(usedToday: 1);
      };
    final container = _container(client, FakeSessionStorage(savedSession));
    await container.read(sessionProvider.future);
    await container.read(accountProvider.future);

    fail = true;
    await container.read(accountProvider.notifier).refresh();

    expect(container.read(accountProvider).value!.usage!.usedToday, 1);
  });

  test('resets when the session ends', () async {
    final client = FakeApiClient()..onFetchMe = () async => fakeProfile();
    final container = _container(client, FakeSessionStorage(savedSession));
    container.listen(accountProvider, (_, _) {});
    await container.read(sessionProvider.future);
    expect(await container.read(accountProvider.future), isNotNull);

    await container.read(sessionProvider.notifier).signOut();

    expect(await container.read(accountProvider.future), isNull);
  });
}
