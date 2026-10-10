import 'package:dio/dio.dart';
import 'package:image_picker/image_picker.dart';

import '../configs/app_config.dart';
import '../schemas/job.dart';

abstract class GenerationApiClient {
  Future<String> submitGeneration(List<XFile> faces, String prompt);
  Future<GenerationJob> getJobStatus(String jobId);
  String getResultImageUrl(String resultPath);
}

class DioApiClient implements GenerationApiClient {
  DioApiClient() : _dio = Dio(BaseOptions(baseUrl: AppConfig.apiBaseUrl));

  final Dio _dio;

  @override
  Future<String> submitGeneration(List<XFile> faces, String prompt) async {
    final formData = FormData.fromMap({
      'prompt': prompt,
      'faces': [
        for (final f in faces)
          MultipartFile.fromBytes(await f.readAsBytes(), filename: f.name),
      ],
    });
    final response = await _dio.post<Map<String, dynamic>>(
      '/generations',
      data: formData,
    );
    return response.data!['job_id'] as String;
  }

  @override
  Future<GenerationJob> getJobStatus(String jobId) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/generations/$jobId',
    );
    final data = response.data!;
    final resultPath = data['result_url'] as String?;
    return GenerationJob(
      jobId: data['job_id'] as String,
      status: JobStatus.values.byName(data['status'] as String),
      resultUrl: resultPath != null ? getResultImageUrl(resultPath) : null,
      error: data['error'] as String?,
    );
  }

  @override
  String getResultImageUrl(String resultPath) =>
      '${AppConfig.apiBaseUrl}$resultPath';
}
