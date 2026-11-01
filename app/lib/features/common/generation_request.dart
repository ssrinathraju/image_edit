import 'package:image_picker/image_picker.dart';

import '../../schemas/creation.dart';

class GenerationRequest {
  GenerationRequest({
    required this.photo,
    this.templateId,
    this.prompt,
    this.templateTitle,
  }) : assert(
         (templateId == null) != (prompt == null),
         'provide exactly one of templateId or prompt',
       );

  final XFile photo;
  final String? templateId;
  final String? prompt;

  /// Shown in My creations; falls back to the template id when not loaded.
  final String? templateTitle;

  String get historyLabel => prompt ?? templateTitle ?? templateId!;

  /// What a new creation records so "Make another" can rebuild this request.
  CreationSource get source => prompt != null
      ? CreationSource.prompt(prompt!)
      : CreationSource.template(templateId!);
}
