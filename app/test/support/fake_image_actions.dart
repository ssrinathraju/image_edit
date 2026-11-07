import 'dart:async';
import 'dart:typed_data';
import 'dart:ui' show Rect;

import 'package:image_edit/services/image_actions.dart';

class FakeImageActions implements ImageActions {
  SaveResult saveResult = SaveResult.saved;
  Object? saveError;

  /// When set, a save waits for it before answering.
  Completer<void>? saveGate;
  final saved = <({Uint8List bytes, String name})>[];
  final shared = <({Uint8List bytes, String name})>[];

  @override
  Future<SaveResult> saveToLibrary(Uint8List bytes, {required String name}) async {
    saved.add((bytes: bytes, name: name));
    await saveGate?.future;
    if (saveError != null) throw saveError!;
    return saveResult;
  }

  @override
  Future<void> share(Uint8List bytes, {required String name, Rect? origin}) async {
    shared.add((bytes: bytes, name: name));
  }
}
