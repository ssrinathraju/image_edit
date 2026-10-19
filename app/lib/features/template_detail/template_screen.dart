import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../schemas/template.dart';
import '../../services/generation_providers.dart';
import '../common/generation_request.dart';
import '../common/photo_picker_field.dart';
import '../common/submit_controller.dart';
import '../common/submit_flow.dart';

const double _previewHeight = 200;

final templateByIdProvider =
    FutureProvider.autoDispose.family<TemplateSummary?, String>((ref, id) async {
  final templates = await ref.read(generationServiceProvider).listTemplates();
  for (final template in templates) {
    if (template.id == id) return template;
  }
  return null;
});

class TemplateScreen extends ConsumerWidget {
  const TemplateScreen({required this.templateId, this.template, super.key});

  final String templateId;
  final TemplateSummary? template;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final resolved = template != null
        ? AsyncData<TemplateSummary?>(template)
        : ref.watch(templateByIdProvider(templateId));
    return Scaffold(
      appBar: AppBar(title: const Text('Template')),
      body: resolved.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, _) => _Message(text: 'Could not load this template.'),
        data: (found) => found == null
            ? _Message(text: 'This template is no longer available.')
            : _TemplateBody(template: found),
      ),
    );
  }
}

class _TemplateBody extends ConsumerWidget {
  const _TemplateBody({required this.template});

  final TemplateSummary template;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final photo = ref.watch(selectedPhotoProvider);
    final isSubmitting = ref.watch(submitControllerProvider);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: SizedBox(
            height: _previewHeight,
            width: double.infinity,
            child: Image.network(
              template.previewUrl,
              fit: BoxFit.cover,
              errorBuilder: (_, _, _) => const ColoredBox(
                color: Colors.black12,
                child: Icon(Icons.image_not_supported_outlined),
              ),
            ),
          ),
        ),
        const SizedBox(height: 16),
        Text(template.title, style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 4),
        Text(
          'Your photo will be used as reference.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        const SizedBox(height: 16),
        const PhotoPickerField(),
        const SizedBox(height: 16),
        FilledButton(
          onPressed: photo == null || isSubmitting
              ? null
              : () => submitAndOpenStatus(
                    context,
                    ref,
                    GenerationRequest(
                      photo: photo,
                      templateId: template.id,
                      templateTitle: template.title,
                    ),
                  ),
          child: isSubmitting
              ? const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Generate'),
        ),
      ],
    );
  }
}

class _Message extends StatelessWidget {
  const _Message({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(text),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: () => context.go('/'),
            child: const Text('Back to home'),
          ),
        ],
      ),
    );
  }
}
