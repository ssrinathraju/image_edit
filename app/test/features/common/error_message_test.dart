import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/common/error_message.dart';

DioException _dio({Response<dynamic>? response}) => DioException(
      requestOptions: RequestOptions(path: '/generations'),
      response: response,
    );

void main() {
  test('uses the server detail for API errors', () {
    final error = _dio(
      response: Response(
        requestOptions: RequestOptions(path: '/generations'),
        statusCode: 400,
        data: {
          'detail': {'error': 'invalid_template', 'detail': "unknown template_id 'x'"},
        },
      ),
    );
    expect(describeError(error), "unknown template_id 'x'");
  });

  test('uses a plain-string detail', () {
    final error = _dio(
      response: Response(
        requestOptions: RequestOptions(path: '/generations'),
        statusCode: 404,
        data: {'detail': 'Not Found'},
      ),
    );
    expect(describeError(error), 'Not Found');
  });

  test('uses the first message of a 422 validation list', () {
    final error = _dio(
      response: Response(
        requestOptions: RequestOptions(path: '/generations'),
        statusCode: 422,
        data: {
          'detail': [
            {'loc': ['body', 'photo'], 'msg': 'Field required', 'type': 'missing'},
          ],
        },
      ),
    );
    expect(describeError(error), 'Field required');
  });

  test('explains connection failures', () {
    expect(describeError(_dio()), contains('Could not reach the server'));
  });

  test('falls back to a generic message', () {
    expect(describeError(StateError('boom')), contains('Something went wrong'));
  });
}
