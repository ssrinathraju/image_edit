import 'dart:io';

import 'package:image_edit/features/common/pending_pick_store.dart';

/// Holds the note in memory, so widget tests need no real file I/O.
class FakePendingPickStore extends PendingPickStore {
  FakePendingPickStore({this.note})
    : super(resolveRoot: () async => Directory.systemTemp);

  PendingPick? note;
  int deleteCalls = 0;

  @override
  Future<void> write(PendingPick pick) async => note = pick;

  @override
  Future<PendingPick?> read() async => note;

  @override
  Future<void> delete() async {
    deleteCalls++;
    note = null;
  }
}
