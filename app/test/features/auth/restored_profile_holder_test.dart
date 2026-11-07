import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/auth/session_notifier.dart';
import 'package:image_edit/schemas/session.dart';

void main() {
  const profile = UserProfile(id: 'u1', email: 'a@b.com');

  test('take returns the kept profile once', () {
    final holder = RestoredProfileHolder()..keep(profile);

    expect(holder.take(), profile);
    expect(holder.take(), isNull);
  });

  test('take after clear returns null', () {
    final holder = RestoredProfileHolder()
      ..keep(profile)
      ..clear();

    expect(holder.take(), isNull);
  });
}
