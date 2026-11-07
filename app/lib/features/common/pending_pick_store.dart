import 'dart:convert';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:logging/logging.dart';
import 'package:path_provider/path_provider.dart';

final _log = Logger('PendingPickStore');

/// A note older than this is dropped, and a photo recovered with it is discarded.
const Duration pendingPickLifetime = Duration(hours: 1);

const String _noteFile = 'pending_pick.json';
const String _tempExtension = '.tmp';

enum PendingPickKind { template, custom }

/// Where a photo pick was started from, and for whom, so a photo recovered
/// after Android closed the app can go back to the same form.
class PendingPick {
  const PendingPick({
    required this.userId,
    required this.kind,
    required this.startedAt,
    this.templateId,
    this.prompt,
  });

  factory PendingPick.fromJson(Map<String, dynamic> json) {
    final kind = PendingPickKind.values.byName(json['kind'] as String);
    final templateId = json['templateId'] as String?;
    if (kind == PendingPickKind.template && templateId == null) {
      throw const FormatException('template note without a template id');
    }
    return PendingPick(
      userId: json['userId'] as String,
      kind: kind,
      templateId: templateId,
      prompt: json['prompt'] as String?,
      startedAt: DateTime.parse(json['startedAt'] as String),
    );
  }

  final String userId;
  final PendingPickKind kind;
  final String? templateId;
  final String? prompt;
  final DateTime startedAt;

  bool isExpiredAt(DateTime now) =>
      now.difference(startedAt) > pendingPickLifetime;

  Map<String, dynamic> toJson() => {
    'userId': userId,
    'kind': kind.name,
    if (templateId != null) 'templateId': templateId,
    if (prompt != null) 'prompt': prompt,
    'startedAt': startedAt.toIso8601String(),
  };
}

/// The single note in the app's private support folder. It is excluded from
/// backups through the Android backup rules. No method throws: a problem here
/// must never get in the way of picking a photo.
class PendingPickStore {
  PendingPickStore({required this.resolveRoot});

  final Future<Directory> Function() resolveRoot;

  /// Writes the note through a temp file and a rename, so it is never half written.
  Future<void> write(PendingPick pick) async {
    try {
      final root = await resolveRoot();
      final temp = File('${root.path}/$_noteFile$_tempExtension');
      await temp.create(recursive: true);
      await temp.writeAsString(jsonEncode(pick.toJson()), flush: true);
      await temp.rename('${root.path}/$_noteFile');
    } on Object catch (error) {
      _log.warning('write_failed ${error.runtimeType}');
    }
  }

  /// The note, or null when there is none; a corrupt note is deleted.
  Future<PendingPick?> read() async {
    try {
      final file = File('${(await resolveRoot()).path}/$_noteFile');
      if (!await file.exists()) return null;
      return await _parse(file);
    } on Object catch (error) {
      _log.warning('read_failed ${error.runtimeType}');
      return null;
    }
  }

  Future<PendingPick?> _parse(File file) async {
    try {
      final json = jsonDecode(await file.readAsString());
      return PendingPick.fromJson(json as Map<String, dynamic>);
    } on Object catch (error) {
      _log.warning('note_corrupt ${error.runtimeType}');
      await delete();
      return null;
    }
  }

  Future<void> delete() async {
    try {
      final root = await resolveRoot();
      for (final name in [_noteFile, '$_noteFile$_tempExtension']) {
        final file = File('${root.path}/$name');
        if (await file.exists()) await file.delete();
      }
    } on Object catch (error) {
      _log.warning('delete_failed ${error.runtimeType}');
    }
  }
}

final pendingPickStoreProvider = Provider<PendingPickStore>(
  (_) => PendingPickStore(resolveRoot: getApplicationSupportDirectory),
);
