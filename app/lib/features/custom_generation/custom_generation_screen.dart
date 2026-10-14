import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../configs/app_config.dart';
import '../common/generation_request.dart';
import '../common/photo_picker_field.dart';
import '../common/submit_controller.dart';
import '../common/submit_flow.dart';

const int _promptMinLines = 4;
const int _promptMaxLines = 8;

class CustomGenerationScreen extends ConsumerStatefulWidget {
  const CustomGenerationScreen({this.initialPrompt = '', super.key});

  final String initialPrompt;

  @override
  ConsumerState<CustomGenerationScreen> createState() =>
      _CustomGenerationScreenState();
}

class _CustomGenerationScreenState
    extends ConsumerState<CustomGenerationScreen> {
  late final TextEditingController _controller =
      TextEditingController(text: widget.initialPrompt);

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
        photo != null && prompt.trim().isNotEmpty && !isTooLong && !isSubmitting;

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
          const PhotoPickerField(),
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
