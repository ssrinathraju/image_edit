import 'package:dio/dio.dart';

const String _unreachableMessage =
    'Could not reach the server. Check your connection and try again.';
const String _genericMessage = 'Something went wrong. Please try again.';

/// Turns a failed request into a message that is safe to show to the user.
String describeError(Object error) {
  if (error is DioException) {
    final data = error.response?.data;
    if (data is Map && data['detail'] is Map) {
      final detail = (data['detail'] as Map)['detail'];
      if (detail is String && detail.isNotEmpty) return detail;
    }
    if (error.response == null) return _unreachableMessage;
  }
  return _genericMessage;
}
