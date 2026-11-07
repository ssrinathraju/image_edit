import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/services/image_actions.dart';

Uint8List _webp() => Uint8List.fromList([
  0x52,
  0x49,
  0x46,
  0x46,
  0,
  0,
  0,
  0,
  0x57,
  0x45,
  0x42,
  0x50,
  0x56,
  0x50,
]);

void main() {
  group('detectImageFormat', () {
    test('recognises PNG', () {
      final png = Uint8List.fromList([
        0x89,
        0x50,
        0x4E,
        0x47,
        0x0D,
        0x0A,
        0x1A,
        0x0A,
      ]);
      expect(detectImageFormat(png), (extension: 'png', mimeType: 'image/png'));
    });

    test('recognises JPEG', () {
      final jpeg = Uint8List.fromList([0xFF, 0xD8, 0xFF, 0xE0, 0, 0x10]);
      expect(detectImageFormat(jpeg), (
        extension: 'jpg',
        mimeType: 'image/jpeg',
      ));
    });

    test('recognises WebP', () {
      expect(detectImageFormat(_webp()), (
        extension: 'webp',
        mimeType: 'image/webp',
      ));
    });

    test('RIFF without the WebP tag is not WebP', () {
      final wave = _webp()..[8] = 0x41;
      expect(detectImageFormat(wave).extension, 'png');
    });

    test('short or empty input falls back to PNG', () {
      expect(detectImageFormat(Uint8List(0)).extension, 'png');
      expect(
        detectImageFormat(Uint8List.fromList([0xFF, 0xD8])).extension,
        'png',
      );
      expect(
        detectImageFormat(Uint8List.fromList([0x52, 0x49, 0x46, 0x46]))
            .extension,
        'png',
      );
    });
  });
}
