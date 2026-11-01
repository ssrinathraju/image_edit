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

  group('source', () {
    Creation withSource(CreationSource? source) => Creation(
      jobId: 'j',
      label: 'x',
      finishedAt: DateTime.utc(2026),
      source: source,
    );

    test('a template source survives a round-trip', () {
      final back = Creation.fromJson(
        withSource(const CreationSource.template('golden-hour-beach')).toJson(),
      );

      expect(back.source?.templateId, 'golden-hour-beach');
      expect(back.source?.prompt, isNull);
    });

    test(
      'a prompt source survives a round-trip on creations and pending entries',
      () {
        final back = Creation.fromJson(
          withSource(const CreationSource.prompt('astronaut on a beach'))
              .toJson(),
        );
        final pending = PendingGeneration.fromJson(
          PendingGeneration(
            jobId: 'j',
            label: 'x',
            submittedAt: DateTime.utc(2026),
            source: const CreationSource.prompt('astronaut on a beach'),
          ).toJson(),
        );

        expect(back.source?.prompt, 'astronaut on a beach');
        expect(back.source?.templateId, isNull);
        expect(pending.source?.prompt, 'astronaut on a beach');
      },
    );

    test('JSON without a source reads as null', () {
      final json = withSource(null).toJson();

      expect(json.containsKey('source'), isFalse);
      expect(Creation.fromJson(json).source, isNull);
      expect(
        PendingGeneration.fromJson({
          'jobId': 'j',
          'label': 'x',
          'submittedAt': '2026-01-01T00:00:00.000Z',
        }).source,
        isNull,
      );
    });

    final malformed = <String, Object?>{
      'unknown kind': {'kind': 'video', 'prompt': 'p'},
      'template without id': {'kind': 'template'},
      'prompt without text': {'kind': 'prompt'},
      'template id of the wrong type': {'kind': 'template', 'templateId': 7},
      'prompt of the wrong type': {
        'kind': 'prompt',
        'prompt': ['p'],
      },
      'a string': 'template',
      'null': null,
    };
    malformed.forEach((name, source) {
      test('malformed source ($name) reads as null and does not throw', () {
        final json = withSource(null).toJson()..['source'] = source;
        final pendingJson = {
          'jobId': 'j',
          'label': 'x',
          'submittedAt': '2026-01-01T00:00:00.000Z',
          'source': source,
        };

        expect(Creation.fromJson(json).source, isNull);
        expect(PendingGeneration.fromJson(pendingJson).source, isNull);
      });
    });
  });
}
