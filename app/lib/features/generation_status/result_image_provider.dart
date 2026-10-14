import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../services/generation_providers.dart';

/// Fetches the generated image once; the screen and its actions share the bytes.
final resultImageBytesProvider =
    FutureProvider.autoDispose.family<Uint8List, String>((ref, url) {
  return ref.read(generationServiceProvider).fetchImageBytes(url);
});
