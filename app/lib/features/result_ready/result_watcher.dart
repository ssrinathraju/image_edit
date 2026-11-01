import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:logging/logging.dart';

import '../auth/session_notifier.dart';
import '../history/history_sync.dart';

final _log = Logger('ResultWatcher');

/// How long after one catch-up finishes the next one starts.
const Duration catchUpInterval = Duration(seconds: 5);

/// Runs the catch-up repeatedly while the app is in the foreground and
/// someone is signed in. Runs never overlap and a failed run never stops it.
class ResultWatcher {
  ResultWatcher({
    required this.run,
    this.interval = catchUpInterval,
  });

  final Future<void> Function(String userId) run;
  final Duration interval;

  bool _isResumed = true;
  String? _userId;
  String? _activeUserId;
  Timer? _timer;
  // Bumped on every stop, so a run that ends after a stop cannot re-arm.
  int _generation = 0;

  void updateLifecycle(AppLifecycleState state) {
    _isResumed = state == AppLifecycleState.resumed;
    _apply();
  }

  void updateUser(String? userId) {
    if (userId == _userId) return;
    _userId = userId;
    _apply();
  }

  void dispose() {
    _isResumed = false;
    _apply();
  }

  void _apply() {
    final userId = _isResumed ? _userId : null;
    if (userId == _activeUserId) return;
    _stop();
    _activeUserId = userId;
    if (userId == null) return;
    _log.fine('started');
    unawaited(_tick(userId, _generation));
  }

  void _stop() {
    if (_activeUserId != null) _log.fine('stopped');
    _timer?.cancel();
    _timer = null;
    _generation++;
    _activeUserId = null;
  }

  Future<void> _tick(String userId, int generation) async {
    try {
      await run(userId);
    } on Object catch (error) {
      _log.warning('run_failed ${error.runtimeType}');
    } finally {
      if (generation == _generation) {
        _timer = Timer(interval, () => unawaited(_tick(userId, generation)));
      }
    }
  }
}

final resultWatcherProvider = Provider<ResultWatcher>((ref) {
  final sync = ref.watch(historySyncProvider);
  final watcher = ResultWatcher(run: sync.run);
  watcher.updateLifecycle(
    WidgetsBinding.instance.lifecycleState ?? AppLifecycleState.resumed,
  );
  ref.listen(
    sessionProvider,
    (_, next) => watcher.updateUser(next.valueOrNull?.userId),
    fireImmediately: true,
  );
  ref.onDispose(watcher.dispose);
  return watcher;
});
