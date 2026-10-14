import 'package:dio/dio.dart';

const String _unreachableMessage =
    'Could not reach the server. Check your connection and try again.';
const String _genericMessage = 'Something went wrong. Please try again.';

/// Turns a failed request into a message that is safe to show to the user.
String describeError(Object error) {
  if (error is DioException) {
    final serverMessage = _serverDetail(error.response?.data);
    if (serverMessage != null) return serverMessage;
    if (error.response == null) return _unreachableMessage;
  }
  return _genericMessage;
}

/// Extracts the server's explanation from the error shapes FastAPI produces:
/// `{detail: {detail: str}}`, `{detail: str}` and 422's `{detail: [{msg: str}]}`.
String? _serverDetail(Object? data) {
  if (data is! Map) return null;
  final detail = data['detail'];
  final text = switch (detail) {
    String() => detail,
    Map() => detail['detail'],
    List() when detail.isNotEmpty && detail.first is Map =>
      (detail.first as Map)['msg'],
    _ => null,
  };
  return text is String && text.isNotEmpty ? text : null;
}
