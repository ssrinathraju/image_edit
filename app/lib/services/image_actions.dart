import 'dart:ui' show Rect;

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gal/gal.dart';
import 'package:share_plus/share_plus.dart';

enum SaveResult { saved, permissionDenied }

abstract class ImageActions {
  Future<SaveResult> saveToLibrary(Uint8List bytes, {required String name});
  Future<void> share(Uint8List bytes, {required String name, Rect? origin});
}

class PlatformImageActions implements ImageActions {
  const PlatformImageActions();

  @override
  Future<SaveResult> saveToLibrary(Uint8List bytes, {required String name}) async {
    try {
      final hasAccess = await Gal.hasAccess() || await Gal.requestAccess();
      if (!hasAccess) return SaveResult.permissionDenied;
      await Gal.putImageBytes(bytes, name: name);
      return SaveResult.saved;
    } on GalException catch (error) {
      if (error.type == GalExceptionType.accessDenied) {
        return SaveResult.permissionDenied;
      }
      rethrow;
    }
  }

  @override
  Future<void> share(Uint8List bytes, {required String name, Rect? origin}) async {
    await SharePlus.instance.share(
      ShareParams(
        files: [XFile.fromData(bytes, mimeType: 'image/png')],
        fileNameOverrides: ['$name.png'],
        sharePositionOrigin: origin,
      ),
    );
  }
}

final imageActionsProvider =
    Provider<ImageActions>((_) => const PlatformImageActions());

/// Download and Share are only offered on mobile builds.
final showImageActionsProvider = Provider<bool>((_) => !kIsWeb);
