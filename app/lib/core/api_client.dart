import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:image_picker/image_picker.dart';

import '../configs/app_config.dart';
import '../features/common/generation_request.dart';
import '../schemas/job.dart';
import '../schemas/template.dart';

abstract class GenerationApiClient {
  Future<List<TemplateSummary>> listTemplates({String? query});
  Future<String> submitGeneration(GenerationRequest request);
  Future<GenerationJob> getJobStatus(String jobId);
  Future<Uint8List> fetchImageBytes(String url);
  String resolveUrl(String path);
}

class DioApiClient implements GenerationApiClient {
  DioApiClient({Dio? dio, String? baseUrl})
      : _baseUrl = baseUrl ?? AppConfig.apiBaseUrl,
        _dio = dio ?? Dio(BaseOptions(baseUrl: baseUrl ?? AppConfig.apiBaseUrl));

  final Dio _dio;
  final String _baseUrl;

  @override
  Future<List<TemplateSummary>> listTemplates({String? query}) async {
    final trimmed = query?.trim();
    final response = await _dio.get<List<dynamic>>(
      '/templates',
      queryParameters: {if (trimmed != null && trimmed.isNotEmpty) 'q': trimmed},
    );
    final templates = [
      for (final item in response.data!.cast<Map<String, dynamic>>())
        TemplateSummary.fromJson(item),
    ];
    return [
      for (final t in templates) t.withPreviewUrl(resolveUrl(t.previewUrl)),
    ];
  }

  @override
  Future<String> submitGeneration(GenerationRequest request) async {
    final photo = request.photo;
    final formData = FormData.fromMap({
      if (request.templateId != null) 'template_id': request.templateId,
      if (request.prompt != null) 'prompt': request.prompt,
      'faces': [
        MultipartFile.fromBytes(
          await photo.readAsBytes(),
          filename: photo.name,
          contentType: DioMediaType.parse(_imageMimeType(photo)),
        ),
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
      resultUrl: resultPath != null ? resolveUrl(resultPath) : null,
      error: data['error'] as String?,
    );
  }

  @override
  Future<Uint8List> fetchImageBytes(String url) async {
    final response = await _dio.get<List<int>>(
      url,
      options: Options(responseType: ResponseType.bytes),
    );
    return Uint8List.fromList(response.data!);
  }

  @override
  String resolveUrl(String path) => '$_baseUrl$path';
}

String _imageMimeType(XFile photo) {
  final declared = photo.mimeType;
  if (declared != null && declared.startsWith('image/')) return declared;
  final name = photo.name.toLowerCase();
  if (name.endsWith('.png')) return 'image/png';
  if (name.endsWith('.webp')) return 'image/webp';
  return 'image/jpeg';
}
