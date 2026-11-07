import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../configs/app_config.dart';
import '../common/generation_request.dart';
import '../common/photo_picker_field.dart';
import '../common/submit_controller.dart';
import '../common/submit_flow.dart';

const int _promptMinLines = 4;
const int _promptMaxLines = 8;

class CustomGenerationScreen extends StatelessWidget {
  const CustomGenerationScreen({
    this.initialPrompt = '',
    this.initialPhoto,
    super.key,
  });

  final String initialPrompt;

  /// Pre-selects the photo when the form is opened from a finished result.
  final XFile? initialPhoto;

  @override
  Widget build(BuildContext context) {
    return PhotoScope(
      child: _CustomGenerationForm(
        initialPrompt: initialPrompt,
        initialPhoto: initialPhoto,
      ),
    );
  }
}

class _CustomGenerationForm extends ConsumerStatefulWidget {
  const _CustomGenerationForm({
    required this.initialPrompt,
    required this.initialPhoto,
  });

  final String initialPrompt;
  final XFile? initialPhoto;

  @override
  ConsumerState<_CustomGenerationForm> createState() =>
      _CustomGenerationFormState();
}

class _CustomGenerationFormState extends ConsumerState<_CustomGenerationForm> {
  late final TextEditingController _controller = TextEditingController(
    text: widget.initialPrompt,
  );

  @override
  void initState() {
    super.initState();
    final photo = widget.initialPhoto;
    if (photo == null) return;
    // Riverpod refuses provider writes while the tree is being built.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) ref.read(selectedPhotoProvider.notifier).state = photo;
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final photo = ref.watch(selectedPhotoProvider);
    final isSubmitting = ref.watch(submitControllerProvider);
    final prompt = _controller.text;
    final isTooLong = prompt.length > AppConfig.maxPromptChars;
    final canSubmit =
        photo != null &&
        prompt.trim().isNotEmpty &&
        !isTooLong &&
        !isSubmitting;

    return Scaffold(
      appBar: AppBar(title: const Text('Create your own')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            controller: _controller,
            minLines: _promptMinLines,
            maxLines: _promptMaxLines,
            keyboardType: TextInputType.multiline,
            decoration: InputDecoration(
              labelText: 'Describe the image you want',
              border: const OutlineInputBorder(),
              alignLabelWithHint: true,
              errorText: isTooLong
                  ? 'Prompt must be ${AppConfig.maxPromptChars} characters or fewer.'
                  : null,
              helperText: '${prompt.length}/${AppConfig.maxPromptChars}',
            ),
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 16),
          PhotoPickerField(origin: PickOrigin.custom(() => _controller.text)),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: canSubmit
                ? () => submitAndOpenStatus(
                    context,
                    ref,
                    GenerationRequest(photo: photo, prompt: prompt.trim()),
                  )
                : null,
            child: isSubmitting
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Generate'),
          ),
        ],
      ),
    );
  }
}
