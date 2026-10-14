import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/home/home_notifier.dart';
import 'package:image_edit/schemas/template.dart';
import 'package:image_edit/services/generation_providers.dart';

import '../../support/fake_api_client.dart';

const _debounce = Duration(milliseconds: 20);
const _settle = Duration(milliseconds: 80);

ProviderContainer _container(FakeApiClient client) {
  final container = ProviderContainer(
    overrides: [
      apiClientProvider.overrideWithValue(client),
      homeDebounceProvider.overrideWithValue(_debounce),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

Future<void> _wait([Duration d = _settle]) => Future<void>.delayed(d);

void main() {
  test('rapid typing results in a single request', () async {
    final client = FakeApiClient()
      ..onListTemplates = (q) async => [fakeTemplate(q ?? 'all')];
    final container = _container(client);
    final sub = container.listen(homeNotifierProvider, (_, _) {});
    addTearDown(sub.close);
    await container.read(homeNotifierProvider.future);

    final notifier = container.read(homeNotifierProvider.notifier);
    notifier
      ..setQuery('b')
      ..setQuery('be')
      ..setQuery('beach');
    await _wait();

    expect(client.queries, [null, 'beach']);
    expect(container.read(homeNotifierProvider).value!.single.id, 'beach');
  });

  test('a slow earlier response does not overwrite a newer one', () async {
    final pending = <String, Completer<List<TemplateSummary>>>{};
    final client = FakeApiClient()
      ..onListTemplates = (q) {
        if (q == null) return Future.value(const []);
        return (pending[q] = Completer<List<TemplateSummary>>()).future;
      };
    final container = _container(client);
    final sub = container.listen(homeNotifierProvider, (_, _) {});
    addTearDown(sub.close);
    await container.read(homeNotifierProvider.future);
    final notifier = container.read(homeNotifierProvider.notifier);

    notifier.setQuery('a');
    await _wait();
    notifier.setQuery('ab');
    await _wait();

    pending['ab']!.complete([fakeTemplate('newer')]);
    await _wait(const Duration(milliseconds: 10));
    pending['a']!.complete([fakeTemplate('stale')]);
    await _wait(const Duration(milliseconds: 10));

    expect(container.read(homeNotifierProvider).value!.single.id, 'newer');
  });

  test('a failed load can be retried', () async {
    var calls = 0;
    final client = FakeApiClient()
      ..onListTemplates = (_) async {
        calls++;
        if (calls == 1) throw StateError('offline');
        return [fakeTemplate('ok')];
      };
    final container = _container(client);
    final sub = container.listen(homeNotifierProvider, (_, _) {});
    addTearDown(sub.close);

    await expectLater(container.read(homeNotifierProvider.future), throwsStateError);
    expect(container.read(homeNotifierProvider).hasError, isTrue);

    await container.read(homeNotifierProvider.notifier).retry();

    expect(container.read(homeNotifierProvider).value!.single.id, 'ok');
  });
}
