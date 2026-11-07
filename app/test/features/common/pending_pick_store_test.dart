import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/common/pending_pick_store.dart';

final _started = DateTime.utc(2026, 1, 1, 12);

PendingPick _note({PendingPickKind kind = PendingPickKind.custom}) =>
    PendingPick(
      userId: 'user-1',
      kind: kind,
      templateId: kind == PendingPickKind.template ? 'golden-hour-beach' : null,
      prompt: kind == PendingPickKind.custom ? 'astronaut on a beach' : null,
      startedAt: _started,
    );

void main() {
  late Directory root;
  late PendingPickStore store;

  setUp(() {
    root = Directory.systemTemp.createTempSync('pending_pick_store_test');
    addTearDown(() => root.deleteSync(recursive: true));
    store = PendingPickStore(resolveRoot: () async => root);
  });

  test('a custom note round trips', () async {
    await store.write(_note());

    final read = await store.read();

    expect(read!.userId, 'user-1');
    expect(read.kind, PendingPickKind.custom);
    expect(read.prompt, 'astronaut on a beach');
    expect(read.templateId, isNull);
    expect(read.startedAt, _started);
  });

  test('a template note round trips', () async {
    await store.write(_note(kind: PendingPickKind.template));

    final read = await store.read();

    expect(read!.kind, PendingPickKind.template);
    expect(read.templateId, 'golden-hour-beach');
    expect(read.prompt, isNull);
  });

  test('the write goes through a rename and leaves no temp file', () async {
    await store.write(_note());

    final names = root.listSync().map((e) => e.uri.pathSegments.last).toList();
    expect(names, ['pending_pick.json']);
  });

  test(
    'a half-written temp file from a crash never reads as the note',
    () async {
      File('${root.path}/pending_pick.json.tmp')
          .writeAsStringSync('{"userId":');

      expect(await store.read(), isNull);
    },
  );

  test('a second write replaces the first', () async {
    await store.write(_note());
    await store.write(_note(kind: PendingPickKind.template));

    expect((await store.read())!.kind, PendingPickKind.template);
  });

  test('no file reads as absent', () async {
    expect(await store.read(), isNull);
  });

  test('a corrupt file reads as absent and is deleted', () async {
    final file = File('${root.path}/pending_pick.json')
      ..writeAsStringSync('not json');

    expect(await store.read(), isNull);
    expect(file.existsSync(), isFalse);
  });

  test('a note missing its fields reads as absent and is deleted', () async {
    final file = File('${root.path}/pending_pick.json')
      ..writeAsStringSync(
        '{"userId":"user-1","kind":"template","startedAt":"2026-01-01T12:00:00Z"}',
      );

    expect(await store.read(), isNull);
    expect(file.existsSync(), isFalse);
  });

  test('delete removes the note and tolerates a missing one', () async {
    await store.write(_note());
    await store.delete();
    await store.delete();

    expect(await store.read(), isNull);
  });

  test('a store that cannot reach its folder never throws', () async {
    final broken = PendingPickStore(
      resolveRoot: () async => throw StateError('no'),
    );

    await broken.write(_note());
    expect(await broken.read(), isNull);
    await broken.delete();
  });

  test('a note is expired after an hour, not at 59 minutes', () {
    final note = _note();

    expect(
      note.isExpiredAt(_started.add(const Duration(minutes: 59))),
      isFalse,
    );
    expect(
      note.isExpiredAt(_started.add(const Duration(minutes: 60))),
      isFalse,
    );
    expect(note.isExpiredAt(_started.add(const Duration(minutes: 61))), isTrue);
    expect(
      note.isExpiredAt(_started.subtract(const Duration(minutes: 1))),
      isTrue,
    );
  });
}
