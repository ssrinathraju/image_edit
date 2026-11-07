import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:logging/logging.dart';

final _log = Logger('AppSettings');

const MethodChannel _settingsChannel = MethodChannel('image_edit/settings');
const String _openMethod = 'open';

/// Opens this app's page in the device settings.
abstract class AppSettings {
  /// Returns false when the settings could not be opened; never throws.
  Future<bool> open();
}

class PlatformAppSettings implements AppSettings {
  const PlatformAppSettings();

  @override
  Future<bool> open() async {
    try {
      await _settingsChannel.invokeMethod<void>(_openMethod);
      return true;
    } on Object catch (error) {
      _log.warning('open_failed ${error.runtimeType}');
      return false;
    }
  }
}

final appSettingsProvider = Provider<AppSettings>(
  (_) => const PlatformAppSettings(),
);
