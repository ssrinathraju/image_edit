import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/auth/session_notifier.dart';
import 'package:image_edit/features/plans/account_notifier.dart';
import 'package:image_edit/services/generation_providers.dart';

import '../../support/app_harness.dart';
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

  group('age and consent', () {
    late FakeApiClient client;
    late ProviderContainer container;

    Future<void> open() async {
      container = _container(client, FakeSessionStorage(savedSession));
      await container.read(sessionProvider.future);
      await container.read(accountProvider.future);
    }

    setUp(() => client = FakeApiClient());

    test('confirmAge posts the date and reloads the account as confirmed', () async {
      var confirmed = false;
      client.onFetchMe = () async => fakeProfile(ageConfirmed: confirmed);
      client.onConfirmAge = (_) async => confirmed = true;
      await open();
      expect(container.read(accountProvider).value!.ageConfirmed, isFalse);

      await container.read(accountProvider.notifier).confirmAge(DateTime(1990, 1, 31));

      expect(client.confirmedAges, [DateTime(1990, 1, 31)]);
      expect(container.read(accountProvider).value!.ageConfirmed, isTrue);
    });

    test('confirmAge lets under_age through and leaves the account unconfirmed', () async {
      client.onFetchMe = () async => fakeProfile(ageConfirmed: false);
      client.onConfirmAge = (_) async => throw apiError(403, 'under_age', 'x');
      await open();

      await expectLater(
        container.read(accountProvider.notifier).confirmAge(DateTime(2015, 1, 1)),
        throwsA(isA<DioException>()),
      );

      expect(container.read(accountProvider).value!.ageConfirmed, isFalse);
    });

    test('acceptConsent records the current version and reloads', () async {
      var accepted = '';
      client.onFetchMe = () async => fakeProfile(
            consentGiven: accepted.isNotEmpty,
            acceptedConsentVersion: accepted,
            currentConsentVersion: '2',
          );
      client.onAcceptConsent = (version) async => accepted = version;
      await open();

      await container.read(accountProvider.notifier).acceptConsent();

      expect(client.acceptedConsents, ['2']);
      expect(container.read(accountProvider).value!.consent!.isCurrentVersionAccepted, isTrue);
    });

    test('withdrawConsent calls the server and reloads', () async {
      var given = true;
      client.onFetchMe = () async => fakeProfile(consentGiven: given);
      client.onWithdrawConsent = () async => given = false;
      await open();

      await container.read(accountProvider.notifier).withdrawConsent();

      expect(client.withdrawnConsents, 1);
      expect(container.read(accountProvider).value!.consent!.isCurrentVersionAccepted, isFalse);
    });

    test('a failed withdrawal throws and keeps the loaded consent', () async {
      client.onFetchMe = () async => fakeProfile();
      client.onWithdrawConsent = () async => throw StateError('offline');
      await open();

      await expectLater(
        container.read(accountProvider.notifier).withdrawConsent(),
        throwsStateError,
      );

      expect(container.read(accountProvider).value!.consent!.isCurrentVersionAccepted, isTrue);
    });
  });
}
