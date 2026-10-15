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
}
