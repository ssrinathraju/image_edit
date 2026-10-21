import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:logging/logging.dart';
import 'package:path_provider/path_provider.dart';

final _log = Logger('OnboardingStore');

const String _markerFile = 'onboarding_seen';

/// The on-device record that onboarding was seen: an empty marker file in the
/// app support folder, so it disappears when the app is uninstalled.
class OnboardingStore {
  OnboardingStore({required this.resolveRoot});

  final Future<Directory> Function() resolveRoot;

  /// Whether the marker exists; any failure to find out reads as not seen.
  Future<bool> hasSeen() async {
    try {
      final root = await resolveRoot();
      return await File('${root.path}/$_markerFile').exists();
    } catch (error) {
      _log.warning('onboarding_read_failed ${error.runtimeType}');
      return false;
    }
  }

  /// Creates the marker; never throws, so a failure cannot block the app.
  Future<void> markSeen() async {
    try {
      final root = await resolveRoot();
      await File('${root.path}/$_markerFile').create(recursive: true);
    } catch (error) {
      _log.warning('onboarding_save_failed ${error.runtimeType}');
    }
  }
}

final onboardingStoreProvider = Provider<OnboardingStore>(
  (_) => OnboardingStore(resolveRoot: getApplicationSupportDirectory),
);

/// Whether onboarding was seen on this device, loaded once at startup.
class OnboardingSeenNotifier extends AsyncNotifier<bool> {
  @override
  Future<bool> build() => ref.read(onboardingStoreProvider).hasSeen();

  /// Updates the state first so the router moves on at once, then saves.
  Future<void> markSeen() async {
    state = const AsyncData(true);
    await ref.read(onboardingStoreProvider).markSeen();
  }
}

final onboardingSeenProvider =
    AsyncNotifierProvider<OnboardingSeenNotifier, bool>(
  OnboardingSeenNotifier.new,
);
