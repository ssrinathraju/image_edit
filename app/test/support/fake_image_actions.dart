import 'dart:typed_data';
import 'dart:ui' show Rect;

import 'package:image_edit/services/image_actions.dart';

class FakeImageActions implements ImageActions {
  SaveResult saveResult = SaveResult.saved;
  Object? saveError;
  final saved = <({Uint8List bytes, String name})>[];
  final shared = <({Uint8List bytes, String name})>[];

  @override
  Future<SaveResult> saveToLibrary(Uint8List bytes, {required String name}) async {
    saved.add((bytes: bytes, name: name));
    if (saveError != null) throw saveError!;
    return saveResult;
  }

  @override
  Future<void> share(Uint8List bytes, {required String name, Rect? origin}) async {
    shared.add((bytes: bytes, name: name));
  }
}
