import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/generation_status/failure_messages.dart';

void main() {
  test('pipeline_failed says it could not be created, was not counted, and to try again', () {
    final message = failureMessageFor('pipeline_failed');

    expect(message, contains("couldn't create your image"));
    expect(message, contains("wasn't counted"));
    expect(message, contains('try again'));
    expect(message, isNot(contains('pipeline_failed')));
  });

  test('unknown and missing codes get the general message without the code', () {
    expect(failureMessageFor(null), failureMessageFor('something_new'));
    expect(failureMessageFor('something_new'), isNot(contains('something_new')));
    expect(failureMessageFor(null), contains("wasn't counted"));
  });
}
