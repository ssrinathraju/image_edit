import 'package:image_edit/core/session_storage.dart';
import 'package:image_edit/schemas/session.dart';

class FakeSessionStorage implements SessionStorage {
  FakeSessionStorage([this.saved]);

  Session? saved;
  var clearCalls = 0;

  @override
  Future<Session?> read() async => saved;

  @override
  Future<void> write(Session session) async => saved = session;

  @override
  Future<void> clear() async {
    clearCalls++;
    saved = null;
  }
}

const savedSession =
    Session(token: 'saved-token', userId: 'user-1', email: 'ana@example.com');
