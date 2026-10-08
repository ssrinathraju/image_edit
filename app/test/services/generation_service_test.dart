import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';

import 'package:image_edit/core/api_client.dart';
import 'package:image_edit/schemas/job.dart';
import 'package:image_edit/services/generation_service.dart';

class _FakeClient implements GenerationApiClient {
  String? lastPrompt;
  List<XFile>? lastFaces;

  @override
  Future<String> submitGeneration(List<XFile> faces, String prompt) async {
    lastFaces = faces;
    lastPrompt = prompt;
    return 'test-job-id';
  }

  @override
  Future<GenerationJob> getJobStatus(String jobId) async {
    return GenerationJob(jobId: jobId, status: JobStatus.queued);
  }

  @override
  String getResultImageUrl(String resultPath) => 'http://localhost$resultPath';
}

void main() {
  group('GenerationService', () {
    late _FakeClient client;
    late GenerationService service;

    setUp(() {
      client = _FakeClient();
      service = GenerationService(client);
    });

    test('submit delegates to client and returns job id', () async {
      final jobId = await service.submit([], 'a portrait');
      expect(jobId, 'test-job-id');
      expect(client.lastPrompt, 'a portrait');
    });

    test('getStatus delegates to client', () async {
      final job = await service.getStatus('test-job-id');
      expect(job.jobId, 'test-job-id');
      expect(job.status, JobStatus.queued);
    });
  });
}
