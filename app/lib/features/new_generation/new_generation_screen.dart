import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';

import 'new_generation_notifier.dart';

class NewGenerationScreen extends ConsumerWidget {
  const NewGenerationScreen({super.key});

  static const int _maxPromptChars = 500;

  Future<void> _pickFace(WidgetRef ref) async {
    final picker = ImagePicker();
    final file = await picker.pickImage(source: ImageSource.gallery);
    if (file != null) {
      ref.read(newGenerationProvider.notifier).addFace(file);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncState = ref.watch(newGenerationProvider);
    final state = asyncState.valueOrNull ?? const NewGenerationState();

    return Scaffold(
      appBar: AppBar(title: const Text('New Generation')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _FaceGrid(
              faces: state.faces,
              onAdd: state.faces.length < 4
                  ? () => _pickFace(ref)
                  : null,
              onRemove: (i) =>
                  ref.read(newGenerationProvider.notifier).removeFace(i),
            ),
            const SizedBox(height: 16),
            _PromptField(
              onChanged: (v) =>
                  ref.read(newGenerationProvider.notifier).setPrompt(v),
            ),
            const SizedBox(height: 8),
            Text(
              '${state.prompt.length}/$_maxPromptChars',
              style: Theme.of(context).textTheme.bodySmall,
              textAlign: TextAlign.end,
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: state.canSubmit
                  ? () => _submit(context, ref)
                  : null,
              child: state.isSubmitting
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Generate'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _submit(BuildContext context, WidgetRef ref) async {
    try {
      final jobId =
          await ref.read(newGenerationProvider.notifier).submit();
      if (context.mounted) {
        context.go('/status/$jobId');
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed: $e')),
        );
      }
    }
  }
}

class _FaceGrid extends StatelessWidget {
  const _FaceGrid({
    required this.faces,
    required this.onAdd,
    required this.onRemove,
  });

  final List<XFile> faces;
  final VoidCallback? onAdd;
  final void Function(int index) onRemove;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Reference faces (${faces.length}/4)',
          style: Theme.of(context).textTheme.titleSmall,
        ),
        const SizedBox(height: 8),
        SizedBox(
          height: 100,
          child: ListView(
            scrollDirection: Axis.horizontal,
            children: [
              for (int i = 0; i < faces.length; i++)
                _FaceTile(
                  file: faces[i],
                  onRemove: () => onRemove(i),
                ),
              if (onAdd != null)
                _AddFaceTile(onTap: onAdd!),
            ],
          ),
        ),
      ],
    );
  }
}

class _FaceTile extends StatelessWidget {
  const _FaceTile({required this.file, required this.onRemove});

  final XFile file;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        Container(
          width: 90,
          height: 90,
          margin: const EdgeInsets.only(right: 8),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(8),
            image: DecorationImage(
              image: NetworkImage(file.path),
              fit: BoxFit.cover,
            ),
          ),
        ),
        Positioned(
          top: 2,
          right: 10,
          child: GestureDetector(
            onTap: onRemove,
            child: const CircleAvatar(
              radius: 10,
              backgroundColor: Colors.black54,
              child: Icon(Icons.close, size: 12, color: Colors.white),
            ),
          ),
        ),
      ],
    );
  }
}

class _AddFaceTile extends StatelessWidget {
  const _AddFaceTile({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 90,
        height: 90,
        decoration: BoxDecoration(
          border: Border.all(color: Theme.of(context).colorScheme.outline),
          borderRadius: BorderRadius.circular(8),
        ),
        child: const Icon(Icons.add_a_photo_outlined),
      ),
    );
  }
}

class _PromptField extends StatelessWidget {
  const _PromptField({required this.onChanged});

  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return TextField(
      maxLines: 4,
      maxLength: 500,
      buildCounter: (_, {required currentLength, required isFocused, maxLength}) =>
          null,
      decoration: const InputDecoration(
        labelText: 'Prompt',
        hintText: 'Describe the image you want to generate…',
        border: OutlineInputBorder(),
      ),
      onChanged: onChanged,
    );
  }
}
