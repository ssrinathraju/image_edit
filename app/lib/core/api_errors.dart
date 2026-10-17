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

/// Seconds from the `Retry-After` header of a failed response, if it sent one.
int? retryAfterSecondsOf(Object error) {
  if (error is! DioException) return null;
  final value = error.response?.headers.value('retry-after');
  final seconds = value == null ? null : int.tryParse(value);
  return seconds != null && seconds > 0 ? seconds : null;
}

const String quotaExceededCode = 'quota_exceeded';

bool isQuotaExceeded(Object error) => errorCodeOf(error) == quotaExceededCode;

const String emailNotVerifiedCode = 'email_not_verified';
const String invalidCodeCode = 'invalid_code';
const String codeExpiredCode = 'code_expired';
const String alreadyVerifiedCode = 'already_verified';
const String tooManyRequestsCode = 'too_many_requests';

bool isEmailNotVerified(Object error) => errorCodeOf(error) == emailNotVerifiedCode;
bool isInvalidCode(Object error) => errorCodeOf(error) == invalidCodeCode;
bool isCodeExpired(Object error) => errorCodeOf(error) == codeExpiredCode;
bool isAlreadyVerified(Object error) => errorCodeOf(error) == alreadyVerifiedCode;
bool isTooManyRequests(Object error) => errorCodeOf(error) == tooManyRequestsCode;
