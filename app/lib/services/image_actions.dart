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
    final format = detectImageFormat(bytes);
    await SharePlus.instance.share(
      ShareParams(
        files: [XFile.fromData(bytes, mimeType: format.mimeType)],
        fileNameOverrides: ['$name.${format.extension}'],
        sharePositionOrigin: origin,
      ),
    );
  }
}

typedef ImageFormat = ({String extension, String mimeType});

const ImageFormat _png = (extension: 'png', mimeType: 'image/png');
const ImageFormat _jpeg = (extension: 'jpg', mimeType: 'image/jpeg');
const ImageFormat _webp = (extension: 'webp', mimeType: 'image/webp');

const List<int> _jpegMagic = [0xFF, 0xD8, 0xFF];
const List<int> _riffMagic = [0x52, 0x49, 0x46, 0x46];
const List<int> _webpMagic = [0x57, 0x45, 0x42, 0x50];
const int _webpMagicOffset = 8;

/// Sniffs the container from magic bytes; the server's output format is not
/// part of the job payload. Falls back to PNG, which the pipeline produces.
@visibleForTesting
ImageFormat detectImageFormat(Uint8List bytes) {
  if (_hasBytesAt(bytes, _jpegMagic, 0)) return _jpeg;
  if (_hasBytesAt(bytes, _riffMagic, 0) &&
      _hasBytesAt(bytes, _webpMagic, _webpMagicOffset)) {
    return _webp;
  }
  return _png;
}

bool _hasBytesAt(Uint8List bytes, List<int> expected, int offset) {
  if (bytes.length < offset + expected.length) return false;
  for (var i = 0; i < expected.length; i++) {
    if (bytes[offset + i] != expected[i]) return false;
  }
  return true;
}

final imageActionsProvider =
    Provider<ImageActions>((_) => const PlatformImageActions());

/// Download and Share are only offered on mobile builds.
final showImageActionsProvider = Provider<bool>((_) => !kIsWeb);
