import 'package:image_edit/features/history/backup_exclusion.dart';

class FakeBackupExclusion implements BackupExclusion {
  final excluded = <String>[];
  Object? error;

  @override
  Future<void> excludeFromBackup(String path) async {
    excluded.add(path);
    if (error != null) throw error!;
  }
}
