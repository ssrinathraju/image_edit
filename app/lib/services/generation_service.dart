import 'dart:typed_data';

import '../core/api_client.dart';
import '../features/common/generation_request.dart';
import '../schemas/job.dart';
import '../schemas/template.dart';

class GenerationService {
  const GenerationService(this._client);

  final GenerationApiClient _client;

  Future<List<TemplateSummary>> listTemplates({String? query}) =>
      _client.listTemplates(query: query);

  Future<String> submit(GenerationRequest request) =>
      _client.submitGeneration(request);

  Future<GenerationJob> getStatus(String jobId) =>
      _client.getJobStatus(jobId);

  Future<Uint8List> fetchImageBytes(String url) =>
      _client.fetchImageBytes(url);
}
