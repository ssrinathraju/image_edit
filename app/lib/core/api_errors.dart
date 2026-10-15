import 'package:dio/dio.dart';

/// The server's machine-readable error code (`detail.error`), if it sent one.
String? errorCodeOf(Object error) {
  if (error is! DioException) return null;
  final data = error.response?.data;
  if (data is! Map) return null;
  final detail = data['detail'];
  if (detail is! Map) return null;
  final code = detail['error'];
  return code is String ? code : null;
}

const String quotaExceededCode = 'quota_exceeded';

bool isQuotaExceeded(Object error) => errorCodeOf(error) == quotaExceededCode;
