import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/schemas/job.dart';

Map<String, dynamic> _json(Object? expiresAt) => {
  'job_id': 'j1',
  'status': 'succeeded',
  'result_url': '/images/j1.png',
  'error': null,
  'expires_at': expiresAt,
};

void main() {
  test('expires_at is parsed as a UTC instant', () {
    final job = GenerationJob.fromJson(_json('2026-10-23T10:00:00Z'));

    expect(job.expiresAt, DateTime.utc(2026, 10, 23, 10));
  });

  test('a missing or null expires_at is null', () {
    expect(GenerationJob.fromJson(_json(null)).expiresAt, isNull);
    final withoutKey = _json(null)..remove('expires_at');
    expect(GenerationJob.fromJson(withoutKey).expiresAt, isNull);
  });

  test('an unparsable expires_at is null, not an error', () {
    expect(GenerationJob.fromJson(_json('tomorrow-ish')).expiresAt, isNull);
  });
}
