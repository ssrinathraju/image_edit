import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';

import '../../schemas/template.dart';
import '../../services/generation_providers.dart';
import '../common/generation_request.dart';
import '../common/photo_picker_field.dart';
import '../common/submit_controller.dart';
import '../common/submit_flow.dart';

const double _previewHeight = 200;

final templateByIdProvider = FutureProvider.autoDispose
    .family<TemplateSummary?, String>((ref, id) async {
      final templates = await ref
          .read(generationServiceProvider)
          .listTemplates();
      for (final template in templates) {
        if (template.id == id) return template;
      }
      return null;
    });

class TemplateScreen extends ConsumerWidget {
  const TemplateScreen({
    required this.templateId,
    this.template,
    this.initialPhoto,
    super.key,
  });

  final String templateId;
  final TemplateSummary? template;

  /// Pre-selects the photo when the form is reopened with a recovered pick.
  final XFile? initialPhoto;

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
            : PhotoScope(
                child: _TemplateBody(
                  template: found,
                  initialPhoto: initialPhoto,
                ),
              ),
      ),
    );
  }
}

class _TemplateBody extends ConsumerStatefulWidget {
  const _TemplateBody({required this.template, required this.initialPhoto});

  final TemplateSummary template;
  final XFile? initialPhoto;

  @override
  ConsumerState<_TemplateBody> createState() => _TemplateBodyState();
}

class _TemplateBodyState extends ConsumerState<_TemplateBody> {
  TemplateSummary get template => widget.template;

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
  Widget build(BuildContext context) {
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
        PhotoPickerField(origin: PickOrigin.template(template.id)),
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
