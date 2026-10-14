import 'dart:typed_data';

import 'package:image_edit/core/api_client.dart';
import 'package:image_edit/features/common/generation_request.dart';
import 'package:image_edit/schemas/job.dart';
import 'package:image_edit/schemas/session.dart';
import 'package:image_edit/schemas/template.dart';

class FakeApiClient implements GenerationApiClient {
  Future<List<TemplateSummary>> Function(String? query) onListTemplates =
      (_) async => const [];
  Future<String> Function(GenerationRequest request) onSubmit =
      (_) async => 'job-1';
  Future<GenerationJob> Function(String jobId) onStatus =
      (id) async => GenerationJob(jobId: id, status: JobStatus.queued);
  Future<Uint8List> Function(String url) onFetchBytes =
      (_) async => Uint8List.fromList([1, 2, 3]);

  Future<Session> Function(String email, String password) onRegister =
      (email, _) async => Session(token: 'token-new', userId: 'user-1', email: email);
  Future<Session> Function(String email, String password) onLogin =
      (email, _) async => Session(token: 'token-1', userId: 'user-1', email: email);
  Future<void> Function() onLogout = () async {};
  Future<UserProfile> Function() onFetchMe =
      () async => const UserProfile(id: 'user-1', email: 'ana@example.com');
  Future<void> Function(String password) onDeleteAccount = (_) async {};

  final queries = <String?>[];
  final registered = <String>[];
  final loggedIn = <String>[];
  var logoutCalls = 0;
  final deletedWith = <String>[];
  final submitted = <GenerationRequest>[];
  final statusCalls = <String>[];

  @override
  Future<List<TemplateSummary>> listTemplates({String? query}) {
    queries.add(query);
    return onListTemplates(query);
  }

  @override
  Future<String> submitGeneration(GenerationRequest request) {
    submitted.add(request);
    return onSubmit(request);
  }

  @override
  Future<GenerationJob> getJobStatus(String jobId) {
    statusCalls.add(jobId);
    return onStatus(jobId);
  }

  @override
  Future<Uint8List> fetchImageBytes(String url) => onFetchBytes(url);

  @override
  String resolveUrl(String path) => 'http://fake$path';

  @override
  Future<Session> register({required String email, required String password}) {
    registered.add(email);
    return onRegister(email, password);
  }

  @override
  Future<Session> login({required String email, required String password}) {
    loggedIn.add(email);
    return onLogin(email, password);
  }

  @override
  Future<void> logout() {
    logoutCalls++;
    return onLogout();
  }

  @override
  Future<UserProfile> fetchMe() => onFetchMe();

  @override
  Future<void> deleteAccount({required String password}) {
    deletedWith.add(password);
    return onDeleteAccount(password);
  }
}

TemplateSummary fakeTemplate(String id, {String? title, List<String> tags = const []}) =>
    TemplateSummary(
      id: id,
      title: title ?? id,
      tags: tags,
      previewUrl: 'http://fake/template-previews/$id.webp',
    );
