import 'package:image_picker/image_picker.dart';

class GenerationRequest {
  GenerationRequest({required this.photo, this.templateId, this.prompt})
      : assert(
          (templateId == null) != (prompt == null),
          'provide exactly one of templateId or prompt',
        );

  final XFile photo;
  final String? templateId;
  final String? prompt;
}
