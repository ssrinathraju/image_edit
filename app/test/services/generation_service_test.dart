import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/core/api_client.dart';
import 'package:image_edit/features/common/generation_request.dart';
import 'package:image_edit/schemas/job.dart';
import 'package:image_edit/schemas/template.dart';
import 'package:image_edit/services/generation_service.dart';
import 'package:image_picker/image_picker.dart';

class _FakeClient implements GenerationApiClient {
  GenerationRequest? lastRequest;
  String? lastQuery;

  @override
  Future<List<TemplateSummary>> listTemplates({String? query}) async {
    lastQuery = query;
    return const [
      TemplateSummary(id: 'a', title: 'A', tags: [], previewUrl: '/p'),
    ];
  }

  @override
  Future<String> submitGeneration(GenerationRequest request) async {
    lastRequest = request;
    return 'test-job-id';
  }

  @override
  Future<GenerationJob> getJobStatus(String jobId) async =>
      GenerationJob(jobId: jobId, status: JobStatus.queued);

  @override
  Future<Uint8List> fetchImageBytes(String url) async => Uint8List.fromList([1]);

  @override
  String resolveUrl(String path) => 'http://localhost$path';
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
      final request = GenerationRequest(
        photo: XFile.fromData(Uint8List(0), name: 'p.jpg'),
        prompt: 'a portrait',
      );
      expect(await service.submit(request), 'test-job-id');
      expect(client.lastRequest, same(request));
    });

    test('getStatus delegates to client', () async {
      final job = await service.getStatus('test-job-id');
      expect(job.jobId, 'test-job-id');
      expect(job.status, JobStatus.queued);
    });

    test('listTemplates passes the query through', () async {
      final templates = await service.listTemplates(query: 'beach');
      expect(client.lastQuery, 'beach');
      expect(templates.single.id, 'a');
    });
  });
}
