import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/core/api_errors.dart';

DioException _error(Object? data, {int status = 429}) => DioException(
      requestOptions: RequestOptions(path: '/generations'),
      response: Response(
        requestOptions: RequestOptions(path: '/generations'),
        statusCode: status,
        data: data,
      ),
    );

void main() {
  test('extracts quota_exceeded from a 429 response', () {
    final error = _error({
      'detail': {'error': 'quota_exceeded', 'detail': 'limit reached'},
    });

    expect(errorCodeOf(error), 'quota_exceeded');
    expect(isQuotaExceeded(error), isTrue);
  });

  test('other errors have no quota code', () {
    expect(errorCodeOf(_error('plain text')), isNull);
    expect(errorCodeOf(_error({'detail': 'Not Found'}, status: 404)), isNull);
    expect(errorCodeOf(StateError('boom')), isNull);
    expect(
      isQuotaExceeded(_error({'detail': {'error': 'invalid_prompt'}}, status: 400)),
      isFalse,
    );
  });

  test('each verification and reset error code is recognised', () {
    Object coded(String code) => _error({
          'detail': {'error': code, 'detail': 'x'},
        }, status: 400);

    expect(isEmailNotVerified(coded('email_not_verified')), isTrue);
    expect(isInvalidCode(coded('invalid_code')), isTrue);
    expect(isCodeExpired(coded('code_expired')), isTrue);
    expect(isAlreadyVerified(coded('already_verified')), isTrue);
    expect(isTooManyRequests(coded('too_many_requests')), isTrue);
    expect(isInvalidCode(coded('code_expired')), isFalse);
    expect(isTooManyRequests(StateError('boom')), isFalse);
  });

  test('Retry-After is read in seconds and ignored when missing or invalid', () {
    DioException withHeader(String? value) => DioException(
          requestOptions: RequestOptions(path: '/x'),
          response: Response(
            requestOptions: RequestOptions(path: '/x'),
            statusCode: 429,
            headers: Headers.fromMap({
              if (value != null) 'retry-after': [value],
            }),
          ),
        );

    expect(retryAfterSecondsOf(withHeader('40')), 40);
    expect(retryAfterSecondsOf(withHeader(null)), isNull);
    expect(retryAfterSecondsOf(withHeader('soon')), isNull);
    expect(retryAfterSecondsOf(withHeader('0')), isNull);
    expect(retryAfterSecondsOf(StateError('boom')), isNull);
  });
}
