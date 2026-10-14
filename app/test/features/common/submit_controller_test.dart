import 'dart:async';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/core/api_client.dart';
import 'package:image_edit/features/common/generation_request.dart';
import 'package:image_edit/features/common/submit_controller.dart';
import 'package:image_edit/schemas/job.dart';
import 'package:image_edit/schemas/template.dart';
import 'package:image_edit/services/generation_providers.dart';
import 'package:image_edit/services/generation_service.dart';
import 'package:image_picker/image_picker.dart';

class _ControlledClient implements GenerationApiClient {
  Completer<String> submission = Completer<String>();

  @override
  Future<String> submitGeneration(GenerationRequest request) => submission.future;

  @override
  Future<List<TemplateSummary>> listTemplates({String? query}) async => const [];

  @override
  Future<GenerationJob> getJobStatus(String jobId) async =>
      GenerationJob(jobId: jobId, status: JobStatus.queued);

  @override
  Future<Uint8List> fetchImageBytes(String url) async => Uint8List(0);

  @override
  String resolveUrl(String path) => path;
}

void main() {
  late _ControlledClient client;
  late ProviderContainer container;
  late GenerationRequest request;

  setUp(() {
    client = _ControlledClient();
    container = ProviderContainer(
      overrides: [
        generationServiceProvider.overrideWithValue(GenerationService(client)),
      ],
    );
    addTearDown(container.dispose);
    request = GenerationRequest(
      photo: XFile.fromData(Uint8List(0), name: 'p.jpg'),
      templateId: 'beach',
    );
  });

  test('success stores the last request and clears the flag', () async {
    final future = container.read(submitControllerProvider.notifier).submit(request);
    expect(container.read(submitControllerProvider), isTrue);

    client.submission.complete('job-1');

    expect(await future, 'job-1');
    expect(container.read(submitControllerProvider), isFalse);
    expect(container.read(lastRequestProvider), (jobId: 'job-1', request: request));
  });

  test('failure rethrows, resets the flag, and keeps the previous request', () async {
    final future = container.read(submitControllerProvider.notifier).submit(request);
    client.submission.completeError(StateError('boom'));

    await expectLater(future, throwsStateError);
    expect(container.read(submitControllerProvider), isFalse);
    expect(container.read(lastRequestProvider), isNull);
  });
}
