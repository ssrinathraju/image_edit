import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/common/generation_request.dart';
import 'package:image_edit/schemas/template.dart';
import 'package:image_picker/image_picker.dart';

void main() {
  group('TemplateSummary', () {
    test('parses the API payload', () {
      final t = TemplateSummary.fromJson({
        'id': 'golden-hour-beach',
        'title': 'Golden Hour Beach',
        'tags': ['beach', 'sunset'],
        'preview_url': '/template-previews/golden-hour-beach.webp',
      });
      expect(t.id, 'golden-hour-beach');
      expect(t.tags, ['beach', 'sunset']);
      expect(t.previewUrl, '/template-previews/golden-hour-beach.webp');
    });

    test('withPreviewUrl keeps other fields', () {
      const t = TemplateSummary(id: 'a', title: 'A', tags: ['x'], previewUrl: '/p');
      final resolved = t.withPreviewUrl('http://h/p');
      expect(resolved.previewUrl, 'http://h/p');
      expect(resolved.title, 'A');
    });
  });

  group('GenerationRequest', () {
    final photo = XFile.fromData(Uint8List(0), name: 'p.jpg');

    test('accepts a template id alone', () {
      expect(GenerationRequest(photo: photo, templateId: 't').templateId, 't');
    });

    test('accepts a prompt alone', () {
      expect(GenerationRequest(photo: photo, prompt: 'p').prompt, 'p');
    });

    test('rejects both or neither', () {
      expect(
        () => GenerationRequest(photo: photo, templateId: 't', prompt: 'p'),
        throwsAssertionError,
      );
      expect(() => GenerationRequest(photo: photo), throwsAssertionError);
    });
  });
}
