import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

const double _maxPhotoWidth = 2048;
const int _photoQuality = 90;
const double _tileHeight = 220;

final imagePickerProvider = Provider<ImagePicker>((_) => ImagePicker());

final selectedPhotoProvider = StateProvider.autoDispose<XFile?>((_) => null);

class PhotoPickerField extends ConsumerWidget {
  const PhotoPickerField({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final photo = ref.watch(selectedPhotoProvider);
    return InkWell(
      onTap: () => _chooseSource(context, ref),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        height: _tileHeight,
        width: double.infinity,
        decoration: BoxDecoration(
          border: Border.all(color: Theme.of(context).colorScheme.outline),
          borderRadius: BorderRadius.circular(12),
        ),
        clipBehavior: Clip.antiAlias,
        child: photo == null ? const _EmptyTile() : _PhotoPreview(photo: photo),
      ),
    );
  }

  Future<void> _chooseSource(BuildContext context, WidgetRef ref) async {
    final source = await showModalBottomSheet<ImageSource>(
      context: context,
      builder: (sheetContext) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.photo_camera_outlined),
              title: const Text('Take photo'),
              onTap: () => Navigator.pop(sheetContext, ImageSource.camera),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library_outlined),
              title: const Text('Choose from library'),
              onTap: () => Navigator.pop(sheetContext, ImageSource.gallery),
            ),
          ],
        ),
      ),
    );
    if (source == null || !context.mounted) return;
    await _pick(context, ref, source);
  }

  Future<void> _pick(
    BuildContext context,
    WidgetRef ref,
    ImageSource source,
  ) async {
    try {
      final file = await ref.read(imagePickerProvider).pickImage(
            source: source,
            maxWidth: _maxPhotoWidth,
            imageQuality: _photoQuality,
          );
      if (file != null) ref.read(selectedPhotoProvider.notifier).state = file;
    } catch (_) {
      if (!context.mounted) return;
      final message = source == ImageSource.camera
          ? 'The camera is not available. Choose a photo from the library instead.'
          : 'Could not open the photo library.';
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
    }
  }
}

class _EmptyTile extends StatelessWidget {
  const _EmptyTile();

  @override
  Widget build(BuildContext context) {
    return const Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(Icons.add_a_photo_outlined, size: 40),
        SizedBox(height: 8),
        Text('Add your photo'),
      ],
    );
  }
}

class _PhotoPreview extends StatefulWidget {
  const _PhotoPreview({required this.photo});

  final XFile photo;

  @override
  State<_PhotoPreview> createState() => _PhotoPreviewState();
}

class _PhotoPreviewState extends State<_PhotoPreview> {
  late Future<Uint8List> _bytes = widget.photo.readAsBytes();

  @override
  void didUpdateWidget(_PhotoPreview oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.photo != widget.photo) _bytes = widget.photo.readAsBytes();
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.expand,
      children: [
        FutureBuilder<Uint8List>(
          future: _bytes,
          builder: (_, snapshot) {
            final data = snapshot.data;
            if (data == null) {
              return const Center(child: CircularProgressIndicator());
            }
            return Image.memory(data, fit: BoxFit.cover);
          },
        ),
        const Positioned(
          right: 8,
          bottom: 8,
          child: Chip(label: Text('Change photo')),
        ),
      ],
    );
  }
}
