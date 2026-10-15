import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:image_picker/image_picker.dart';

import '../configs/app_config.dart';
import '../features/common/generation_request.dart';
import '../schemas/job.dart';
import '../schemas/session.dart';
import '../schemas/template.dart';

abstract class GenerationApiClient {
  Future<List<TemplateSummary>> listTemplates({String? query});
  Future<String> submitGeneration(GenerationRequest request);
  Future<GenerationJob> getJobStatus(String jobId);
  Future<Uint8List> fetchImageBytes(String url);
  String resolveUrl(String path);

  Future<Session> register({required String email, required String password});
  Future<Session> login({required String email, required String password});
  Future<void> logout();
  Future<UserProfile> fetchMe();
  Future<void> deleteAccount({required String password});
}

const String _loginPath = '/auth/login';
const String _registerPath = '/auth/register';

class DioApiClient implements GenerationApiClient {
  /// [tokenProvider] supplies the bearer token for every request;
  /// [onUnauthorized] fires on a 401 from anywhere except the credential
  /// endpoints, where 401 only means a wrong password.
  DioApiClient({
    Dio? dio,
    String? baseUrl,
    String? Function()? tokenProvider,
    void Function()? onUnauthorized,
  })  : _baseUrl = baseUrl ?? AppConfig.apiBaseUrl,
        _dio = dio ?? Dio(BaseOptions(baseUrl: baseUrl ?? AppConfig.apiBaseUrl)) {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          final token = tokenProvider?.call();
          if (token != null) options.headers['Authorization'] = 'Bearer $token';
          handler.next(options);
        },
        onError: (error, handler) {
          final path = error.requestOptions.path;
          final isCredentialCall = path == _loginPath || path == _registerPath;
          if (error.response?.statusCode == 401 && !isCredentialCall) {
            onUnauthorized?.call();
          }
          handler.next(error);
        },
      ),
    );
  }

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

  @override
  Future<Session> register({required String email, required String password}) =>
      _authenticate(_registerPath, email, password);

  @override
  Future<Session> login({required String email, required String password}) =>
      _authenticate(_loginPath, email, password);

  @override
  Future<void> logout() => _dio.post<void>('/auth/logout');

  @override
  Future<UserProfile> fetchMe() async {
    final response = await _dio.get<Map<String, dynamic>>('/me');
    final data = response.data!;
    return UserProfile(id: data['id'] as String, email: data['email'] as String);
  }

  @override
  Future<void> deleteAccount({required String password}) =>
      _dio.delete<void>('/me', data: {'password': password});

  Future<Session> _authenticate(String path, String email, String password) async {
    final response = await _dio.post<Map<String, dynamic>>(
      path,
      data: {'email': email, 'password': password},
    );
    return Session.fromJson(response.data!);
  }
}

String _imageMimeType(XFile photo) {
  final declared = photo.mimeType;
  if (declared != null && declared.startsWith('image/')) return declared;
  final name = photo.name.toLowerCase();
  if (name.endsWith('.png')) return 'image/png';
  if (name.endsWith('.webp')) return 'image/webp';
  return 'image/jpeg';
}
