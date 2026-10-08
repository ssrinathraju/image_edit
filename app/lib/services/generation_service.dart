import 'package:image_picker/image_picker.dart';

import '../core/api_client.dart';
import '../schemas/job.dart';

class GenerationService {
  const GenerationService(this._client);

  final GenerationApiClient _client;

  Future<String> submit(List<XFile> faces, String prompt) =>
      _client.submitGeneration(faces, prompt);

  Future<GenerationJob> getStatus(String jobId) =>
      _client.getJobStatus(jobId);
}
