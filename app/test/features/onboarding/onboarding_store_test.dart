import 'dart:async';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/onboarding/onboarding_store.dart';
import 'package:logging/logging.dart';

class _GatedStore implements OnboardingStore {
  final gate = Completer<void>();
  bool saved = false;

  @override
  Future<Directory> Function() get resolveRoot => throw UnimplementedError();

  @override
  Future<bool> hasSeen() async => false;

  @override
  Future<void> markSeen() async {
    await gate.future;
    saved = true;
  }
}

void main() {
  late Directory root;

  setUp(() => root = Directory.systemTemp.createTempSync('onboarding_store'));
  tearDown(() => root.deleteSync(recursive: true));

  OnboardingStore storeAt(Directory dir) =>
      OnboardingStore(resolveRoot: () async => dir);

  test('is not seen by default', () async {
    expect(await storeAt(root).hasSeen(), isFalse);
  });

  test('is seen after markSeen, and by a new store on the same folder', () async {
    await storeAt(root).markSeen();

    expect(await storeAt(root).hasSeen(), isTrue);
  });

  test('a read failure reads as not seen', () async {
    final store = OnboardingStore(resolveRoot: () async => throw const FileSystemException('nope'));

    expect(await store.hasSeen(), isFalse);
  });

  test('a write failure does not throw and is logged', () async {
    final records = <LogRecord>[];
    final sub = Logger.root.onRecord.listen(records.add);
    addTearDown(sub.cancel);
    final store = OnboardingStore(resolveRoot: () async => throw const FileSystemException('nope'));

    await store.markSeen();

    expect(records.map((r) => r.message), contains(contains('onboarding_save_failed')));
  });

  test('the provider updates its state before the write completes', () async {
    final store = _GatedStore();
    final container = ProviderContainer(
      overrides: [onboardingStoreProvider.overrideWithValue(store)],
    );
    addTearDown(container.dispose);
    expect(await container.read(onboardingSeenProvider.future), isFalse);

    final pending = container.read(onboardingSeenProvider.notifier).markSeen();

    expect(container.read(onboardingSeenProvider).value, isTrue);
    expect(store.saved, isFalse);
    store.gate.complete();
    await pending;
    expect(store.saved, isTrue);
  });
}
