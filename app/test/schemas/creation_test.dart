import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/schemas/creation.dart';

void main() {
  test('a creation survives a JSON round-trip', () {
    final creation = Creation(
      jobId: 'job-1',
      label: 'astronaut on a beach',
      finishedAt: DateTime.utc(2026, 10, 19, 8, 30),
    );

    final back = Creation.fromJson(creation.toJson());

    expect(back.jobId, 'job-1');
    expect(back.label, 'astronaut on a beach');
    expect(back.finishedAt, DateTime.utc(2026, 10, 19, 8, 30));
  });

  test('an empty label is kept as empty', () {
    final back = Creation.fromJson(
      Creation(jobId: 'j', label: '', finishedAt: DateTime.utc(2026)).toJson(),
    );

    expect(back.label, '');
  });

  test('timestamps are written as UTC ISO-8601', () {
    final json = Creation(
      jobId: 'j',
      label: 'x',
      finishedAt: DateTime.parse('2026-10-19T10:00:00+02:00'),
    ).toJson();

    expect(json['finishedAt'], '2026-10-19T08:00:00.000Z');
  });

  test('a pending generation survives a JSON round-trip', () {
    final pending = PendingGeneration(
      jobId: 'job-2',
      label: 'Golden Hour Beach',
      submittedAt: DateTime.utc(2026, 10, 19, 7),
    );

    final back = PendingGeneration.fromJson(pending.toJson());

    expect(back.jobId, 'job-2');
    expect(back.label, 'Golden Hour Beach');
    expect(back.submittedAt, DateTime.utc(2026, 10, 19, 7));
    expect(pending.toJson()['submittedAt'], '2026-10-19T07:00:00.000Z');
  });

  test('a pending generation keeps an empty label', () {
    final back = PendingGeneration.fromJson(
      PendingGeneration(jobId: 'j', label: '', submittedAt: DateTime.utc(2026))
          .toJson(),
    );

    expect(back.label, '');
  });
}
