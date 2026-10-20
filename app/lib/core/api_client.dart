import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:image_picker/image_picker.dart';

import '../configs/app_config.dart';
import 'date_of_birth.dart';
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

  /// Starts a registration: the server emails a code and creates no account.
  Future<void> register({
    required String email,
    required String password,
    required DateTime dateOfBirth,
    String? referralCode,
  });
  Future<Session> confirmRegistration({
    required String email,
    required String code,
    required String password,
  });
  Future<Session> login({required String email, required String password});
  Future<void> logout();
  Future<UserProfile> fetchMe();
  Future<void> deleteAccount({
    String? password,
    String? provider,
    String? token,
    String? nonce,
  });

  /// [dateOfBirth] is sent only after the server answered `age_required`.
  Future<ProviderSession> signInWithGoogle({
    required String idToken,
    DateTime? dateOfBirth,
  });
  Future<ProviderSession> signInWithApple({
    required String identityToken,
    required String nonce,
    required String authorizationCode,
    DateTime? dateOfBirth,
  });
  Future<void> confirmAge({required DateTime dateOfBirth});
  Future<void> acceptConsent({required String version});
  Future<void> withdrawConsent();
  Future<void> redeemReferral({required String code});

  /// Reports a result; the server keeps its own copy of the image while it
  /// still has one, otherwise [imageBytes].
  Future<void> submitReport({
    required String jobId,
    required String category,
    required String note,
    required Uint8List imageBytes,
  });

  Future<void> requestPasswordReset({required String email});
  Future<Session> confirmPasswordReset({
    required String email,
    required String code,
    required String newPassword,
  });
}

const String _loginPath = '/auth/login';
const String _registerPath = '/auth/register';
const String _googlePath = '/auth/oauth/google';
const String _applePath = '/auth/oauth/apple';

const Duration connectTimeout = Duration(seconds: 10);
const Duration receiveTimeout = Duration(seconds: 60);

/// Default options for the real client: without timeouts a stalled server
/// would leave every awaiting screen waiting forever.
BaseOptions apiBaseOptions(String baseUrl) => BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: connectTimeout,
      receiveTimeout: receiveTimeout,
    );

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
        _dio = dio ?? Dio(apiBaseOptions(baseUrl ?? AppConfig.apiBaseUrl)) {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          final token = tokenProvider?.call();
          if (token != null) options.headers['Authorization'] = 'Bearer $token';
          handler.next(options);
        },
        onError: (error, handler) {
          final path = error.requestOptions.path;
          final isCredentialCall = const {
            _loginPath,
            _registerPath,
            _googlePath,
            _applePath,
          }.contains(path);
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
  Future<void> register({
    required String email,
    required String password,
    required DateTime dateOfBirth,
    String? referralCode,
  }) {
    final code = referralCode?.trim();
    return _dio.post<void>(
      _registerPath,
      data: {
        'email': email,
        'password': password,
        'date_of_birth': formatIsoDate(dateOfBirth),
        'referral_code': ?(code == null || code.isEmpty ? null : code),
      },
    );
  }

  @override
  Future<Session> confirmRegistration({
    required String email,
    required String code,
    required String password,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/auth/register/confirm',
      data: {'email': email, 'code': code, 'password': password},
    );
    return Session.fromJson(response.data!);
  }

  @override
  Future<Session> login({required String email, required String password}) =>
      _authenticate(_loginPath, email, password);

  @override
  Future<void> logout() => _dio.post<void>('/auth/logout');

  @override
  Future<UserProfile> fetchMe() async {
    final response = await _dio.get<Map<String, dynamic>>('/me');
    return UserProfile.fromJson(response.data!);
  }

  @override
  Future<void> deleteAccount({
    String? password,
    String? provider,
    String? token,
    String? nonce,
  }) =>
      _dio.delete<void>(
        '/me',
        data: {
          'password': ?password,
          'provider': ?provider,
          'token': ?token,
          'nonce': ?nonce,
        },
      );

  @override
  Future<ProviderSession> signInWithGoogle({
    required String idToken,
    DateTime? dateOfBirth,
  }) =>
      _signInWithProvider(_googlePath, {
        'id_token': idToken,
        'date_of_birth': ?_formatOptional(dateOfBirth),
      });

  @override
  Future<ProviderSession> signInWithApple({
    required String identityToken,
    required String nonce,
    required String authorizationCode,
    DateTime? dateOfBirth,
  }) =>
      _signInWithProvider(_applePath, {
        'identity_token': identityToken,
        'nonce': nonce,
        'authorization_code': authorizationCode,
        'date_of_birth': ?_formatOptional(dateOfBirth),
      });

  @override
  Future<void> confirmAge({required DateTime dateOfBirth}) => _dio.post<void>(
        '/me/age',
        data: {'date_of_birth': formatIsoDate(dateOfBirth)},
      );

  @override
  Future<void> acceptConsent({required String version}) =>
      _dio.post<void>('/me/consent', data: {'version': version});

  @override
  Future<void> withdrawConsent() => _dio.delete<void>('/me/consent');

  @override
  Future<void> redeemReferral({required String code}) =>
      _dio.post<void>('/me/referral', data: {'code': code});

  @override
  Future<void> submitReport({
    required String jobId,
    required String category,
    required String note,
    required Uint8List imageBytes,
  }) =>
      _dio.post<void>(
        '/reports',
        data: FormData.fromMap({
          'job_id': jobId,
          'category': category,
          if (note.isNotEmpty) 'note': note,
          'image': MultipartFile.fromBytes(
            imageBytes,
            filename: '$jobId.png',
            contentType: DioMediaType.parse('image/png'),
          ),
        }),
      );

  Future<ProviderSession> _signInWithProvider(
    String path,
    Map<String, String> body,
  ) async {
    final response = await _dio.post<Map<String, dynamic>>(path, data: body);
    return ProviderSession.fromJson(response.data!);
  }

  @override
  Future<void> requestPasswordReset({required String email}) =>
      _dio.post<void>('/auth/password-reset/request', data: {'email': email});

  @override
  Future<Session> confirmPasswordReset({
    required String email,
    required String code,
    required String newPassword,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/auth/password-reset/confirm',
      data: {'email': email, 'code': code, 'new_password': newPassword},
    );
    return Session.fromJson(response.data!);
  }

  Future<Session> _authenticate(String path, String email, String password) async {
    final response = await _dio.post<Map<String, dynamic>>(
      path,
      data: {'email': email, 'password': password},
    );
    return Session.fromJson(response.data!);
  }
}

String? _formatOptional(DateTime? date) =>
    date == null ? null : formatIsoDate(date);

String _imageMimeType(XFile photo) {
  final declared = photo.mimeType;
  if (declared != null && declared.startsWith('image/')) return declared;
  final name = photo.name.toLowerCase();
  if (name.endsWith('.png')) return 'image/png';
  if (name.endsWith('.webp')) return 'image/webp';
  return 'image/jpeg';
}
