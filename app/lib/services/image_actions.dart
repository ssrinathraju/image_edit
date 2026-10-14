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
      await Gal.putImageBytes(bytes, name: '$name.${_detectFormat(bytes).extension}');
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
    final format = _detectFormat(bytes);
    await SharePlus.instance.share(
      ShareParams(
        files: [XFile.fromData(bytes, mimeType: format.mimeType)],
        fileNameOverrides: ['$name.${format.extension}'],
        sharePositionOrigin: origin,
      ),
    );
  }
}

typedef _ImageFormat = ({String extension, String mimeType});

const _ImageFormat _png = (extension: 'png', mimeType: 'image/png');
const _ImageFormat _jpeg = (extension: 'jpg', mimeType: 'image/jpeg');
const _ImageFormat _webp = (extension: 'webp', mimeType: 'image/webp');

/// Sniffs the container from magic bytes; the server's output format is not
/// part of the job payload. Falls back to PNG, which the pipeline produces.
_ImageFormat _detectFormat(Uint8List bytes) {
  bool startsWith(List<int> prefix, {int offset = 0}) =>
      bytes.length >= offset + prefix.length &&
      [for (var i = 0; i < prefix.length; i++) bytes[offset + i]]
          .asMap()
          .entries
          .every((e) => e.value == prefix[e.key]);

  if (startsWith([0xFF, 0xD8, 0xFF])) return _jpeg;
  if (startsWith([0x52, 0x49, 0x46, 0x46]) &&
      startsWith([0x57, 0x45, 0x42, 0x50], offset: 8)) {
    return _webp;
  }
  return _png;
}

final imageActionsProvider =
    Provider<ImageActions>((_) => const PlatformImageActions());

/// Download and Share are only offered on mobile builds.
final showImageActionsProvider = Provider<bool>((_) => !kIsWeb);
