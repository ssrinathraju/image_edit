import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:logging/logging.dart';

import '../../router.dart';
import '../../schemas/result_ready.dart';
import '../auth/session_notifier.dart';
import '../history/history_sync.dart';

final _log = Logger('ResultReadyPresenter');

const String _bannerText = 'Your image is ready';
const String _viewLabel = 'View';
const Duration _bannerDuration = Duration(seconds: 4);

/// The key set on the app's root `ScaffoldMessenger`.
final scaffoldMessengerKeyProvider =
    Provider<GlobalKey<ScaffoldMessengerState>>((_) => GlobalKey());

/// Shows a bottom banner for each saved creation of the signed-in account.
class ResultReadyPresenter {
  ResultReadyPresenter({
    required Stream<ResultReady> events,
    required this.messengerKey,
    required this.router,
    required this.signedInUserId,
  }) {
    _subscription = events.listen(_present);
  }

  final GlobalKey<ScaffoldMessengerState> messengerKey;
  final GoRouter router;
  final String? Function() signedInUserId;

  late final StreamSubscription<ResultReady> _subscription;

  void dispose() => unawaited(_subscription.cancel());

  void _present(ResultReady event) {
    try {
      if (event.userId != signedInUserId()) return;
      // `.uri` ignores pushed pages; the last match is the page in front.
      final location =
          router.routerDelegate.currentConfiguration.lastOrNull?.matchedLocation;
      if (location == '/status/${event.jobId}') return;
      messengerKey.currentState!.showSnackBar(_banner(event.jobId, _screenReaderInUse()));
    } on Object catch (error) {
      _log.warning('banner_failed job=${event.jobId} ${error.runtimeType}');
    }
  }

  bool _screenReaderInUse() =>
      MediaQuery.accessibleNavigationOf(messengerKey.currentContext!);

  SnackBar _banner(String jobId, bool persist) => SnackBar(
        content: const Text(_bannerText),
        duration: _bannerDuration,
        // An action makes a SnackBar stay until dismissed; only a screen
        // reader user needs that.
        persist: persist,
        behavior: SnackBarBehavior.floating,
        action: SnackBarAction(
          label: _viewLabel,
          onPressed: () => unawaited(router.push('/creations/$jobId')),
        ),
      );
}

final resultReadyPresenterProvider = Provider<ResultReadyPresenter>((ref) {
  final presenter = ResultReadyPresenter(
    events: ref.watch(historySyncProvider).results,
    messengerKey: ref.watch(scaffoldMessengerKeyProvider),
    router: ref.watch(routerProvider),
    signedInUserId: () => ref.read(sessionProvider).valueOrNull?.userId,
  );
  ref.onDispose(presenter.dispose);
  return presenter;
});
