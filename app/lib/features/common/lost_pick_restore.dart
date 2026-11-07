import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:logging/logging.dart';

import '../../core/provider_sign_in.dart' show targetPlatformProvider;
import '../auth/session_notifier.dart';
import 'clock.dart';
import 'pending_pick_store.dart';
import 'photo_picker_field.dart';

final _log = Logger('LostPickRestore');

/// Tells the restore it already ran, so it is tried once per app start.
class LostPickRestoreGuard {
  bool hasStarted = false;
}

final lostPickRestoreGuardProvider = Provider<LostPickRestoreGuard>(
  (_) => LostPickRestoreGuard(),
);

enum _Outcome {
  restored('restored'),
  noNote('no_note'),
  expired('expired'),
  otherAccount('other_account'),
  noFile('no_file'),
  error('error');

  const _Outcome(this.logName);

  final String logName;
}

/// Gets back a photo picked while Android closed the app and reopens the form
/// it was picked for. Android only, once per start, and it never throws. The
/// prompt, ids and file paths are never logged, only the outcome.
Future<void> restoreLostPick(
  WidgetRef ref, {
  required bool Function() isMounted,
  required void Function(String location, XFile photo) open,
}) async {
  if (ref.read(targetPlatformProvider) != TargetPlatform.android) return;
  final guard = ref.read(lostPickRestoreGuardProvider);
  if (guard.hasStarted) return;
  guard.hasStarted = true;

  final store = ref.read(pendingPickStoreProvider);
  final picker = ref.read(imagePickerProvider);
  final now = ref.read(clockProvider);
  final sessionFuture = ref.read(sessionProvider.future);
  try {
    final note = await store.read();
    final lost = await picker.retrieveLostData();
    final session = await sessionFuture;
    final photo = lost.file ?? lost.files?.firstOrNull;
    final outcome = _decide(note, photo, session?.userId, now());
    await store.delete();
    _log.info('outcome ${outcome.logName}');
    if (outcome == _Outcome.restored && isMounted()) {
      open(_locationFor(note!), photo!);
    }
  } on Object catch (error) {
    _log.warning('outcome ${_Outcome.error.logName} ${error.runtimeType}');
    await store.delete();
  }
}

_Outcome _decide(
  PendingPick? note,
  XFile? photo,
  String? userId,
  DateTime now,
) {
  if (note == null) return _Outcome.noNote;
  if (note.isExpiredAt(now)) return _Outcome.expired;
  if (note.userId != userId) return _Outcome.otherAccount;
  if (photo == null) return _Outcome.noFile;
  return _Outcome.restored;
}

String _locationFor(PendingPick note) {
  if (note.kind == PendingPickKind.template) {
    return '/template/${Uri.encodeComponent(note.templateId!)}';
  }
  final prompt = note.prompt ?? '';
  return Uri(
    path: '/create',
    queryParameters: prompt.isEmpty ? null : {'prompt': prompt},
  ).toString();
}
