import 'package:fake_async/fake_async.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/result_ready/result_watcher.dart';

const _five = Duration(seconds: 5);

class _Runs {
  final calls = <String>[];
  Duration duration = Duration.zero;
  Object? error;
  int running = 0;
  int maxRunning = 0;

  Future<void> run(String userId) async {
    calls.add(userId);
    running++;
    if (running > maxRunning) maxRunning = running;
    try {
      await Future<void>.delayed(duration);
      if (error != null) throw error!;
    } finally {
      running--;
    }
  }
}

void main() {
  late _Runs runs;
  late ResultWatcher watcher;

  setUp(() {
    runs = _Runs();
  });

  void inFakeTime(void Function(FakeAsync async) body) {
    fakeAsync((async) {
      watcher = ResultWatcher(run: runs.run);
      body(async);
      watcher.dispose();
      async.flushMicrotasks();
    });
  }

  test('runs at once and then every 5 seconds while resumed and signed in', () {
    inFakeTime((async) {
      watcher.updateUser('user-1');
      async.flushMicrotasks();
      expect(runs.calls, ['user-1']);

      async.elapse(_five);
      expect(runs.calls, hasLength(2));
      async.elapse(_five);
      expect(runs.calls, hasLength(3));
    });
  });

  test('a run that takes longer than 5 seconds never overlaps another', () {
    runs.duration = const Duration(seconds: 12);
    inFakeTime((async) {
      watcher.updateUser('user-1');
      async.elapse(const Duration(seconds: 40));

      expect(runs.maxRunning, 1);
      expect(runs.calls, hasLength(3));
    });
  });

  test('nothing runs while paused, and resuming runs at once', () {
    inFakeTime((async) {
      watcher.updateUser('user-1');
      async.flushMicrotasks();
      watcher.updateLifecycle(AppLifecycleState.paused);
      runs.calls.clear();

      async.elapse(const Duration(seconds: 30));
      expect(runs.calls, isEmpty);

      watcher.updateLifecycle(AppLifecycleState.resumed);
      async.flushMicrotasks();
      expect(runs.calls, ['user-1']);
    });
  });

  test('inactive also stops it', () {
    inFakeTime((async) {
      watcher.updateUser('user-1');
      async.flushMicrotasks();
      watcher.updateLifecycle(AppLifecycleState.inactive);
      runs.calls.clear();

      async.elapse(const Duration(seconds: 30));

      expect(runs.calls, isEmpty);
    });
  });

  test('a run that ends after a pause does not re-arm', () {
    runs.duration = const Duration(seconds: 3);
    inFakeTime((async) {
      watcher.updateUser('user-1');
      async.elapse(const Duration(seconds: 1));
      watcher.updateLifecycle(AppLifecycleState.paused);
      async.elapse(const Duration(seconds: 60));

      expect(runs.calls, hasLength(1));
    });
  });

  test('nothing runs before sign-in or after sign-out', () {
    inFakeTime((async) {
      async.elapse(const Duration(seconds: 30));
      expect(runs.calls, isEmpty);

      watcher.updateUser('user-1');
      async.flushMicrotasks();
      watcher.updateUser(null);
      runs.calls.clear();

      async.elapse(const Duration(seconds: 30));
      expect(runs.calls, isEmpty);
    });
  });

  test('switching accounts runs for the new account', () {
    inFakeTime((async) {
      watcher.updateUser('user-1');
      async.flushMicrotasks();
      watcher.updateUser('user-2');
      async.flushMicrotasks();
      runs.calls.clear();

      async.elapse(_five);

      expect(runs.calls, ['user-2']);
    });
  });

  test('a throwing run still re-arms', () {
    runs.error = StateError('boom');
    inFakeTime((async) {
      watcher.updateUser('user-1');
      async.elapse(const Duration(seconds: 12));

      expect(runs.calls, hasLength(3));
    });
  });
}
