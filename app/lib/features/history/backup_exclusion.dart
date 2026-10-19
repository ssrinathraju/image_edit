import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Marks a folder as not to be copied into device or cloud backups.
abstract class BackupExclusion {
  Future<void> excludeFromBackup(String path);
}

const MethodChannel _backupChannel = MethodChannel('image_edit/backup');
const String _excludeMethod = 'excludeFromBackup';

/// iOS needs a per-folder flag set natively; Android excludes the folder
/// through its backup rules, so there is nothing to do at runtime.
class PlatformBackupExclusion implements BackupExclusion {
  const PlatformBackupExclusion();

  @override
  Future<void> excludeFromBackup(String path) async {
    if (defaultTargetPlatform != TargetPlatform.iOS) return;
    await _backupChannel.invokeMethod<void>(_excludeMethod, path);
  }
}

final backupExclusionProvider = Provider<BackupExclusion>(
  (_) => const PlatformBackupExclusion(),
);
