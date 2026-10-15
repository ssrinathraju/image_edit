import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/core/api_client.dart';
import 'package:image_edit/features/common/generation_request.dart';
import 'package:image_picker/image_picker.dart';

class _FakeAdapter implements HttpClientAdapter {
  _FakeAdapter(this.body, {this.status = 200});

  final Object body;
  final int status;
  RequestOptions? last;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    last = options;
    return ResponseBody.fromString(
      jsonEncode(body),
      status,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

DioApiClient _client(
  _FakeAdapter adapter, {
  String? Function()? tokenProvider,
  void Function()? onUnauthorized,
}) {
  final dio = Dio(BaseOptions(baseUrl: 'http://api.test'))
    ..httpClientAdapter = adapter;
  return DioApiClient(
    dio: dio,
    baseUrl: 'http://api.test',
    tokenProvider: tokenProvider,
    onUnauthorized: onUnauthorized,
  );
}

XFile _photo(String name, {String? mime}) =>
    XFile.fromData(Uint8List.fromList([1, 2, 3]), name: name, mimeType: mime);

void main() {
  group('submitGeneration', () {
    test('template request sends template_id and one faces part', () async {
      final adapter = _FakeAdapter({'job_id': 'job-1'});
      final jobId = await _client(adapter).submitGeneration(
        GenerationRequest(
          photo: _photo('me.png', mime: 'image/png'),
          templateId: 'beach',
        ),
      );

      final form = adapter.last!.data as FormData;
      expect(jobId, 'job-1');
      expect(adapter.last!.path, '/generations');
      expect(form.fields.map((e) => e.key), ['template_id']);
      expect(form.fields.single.value, 'beach');
      expect(form.files, hasLength(1));
      expect(form.files.single.key, 'faces');
      expect(form.files.single.value.contentType.toString(), 'image/png');
    });

    test('prompt request sends prompt and defaults to jpeg', () async {
      final adapter = _FakeAdapter({'job_id': 'job-2'});
      await _client(adapter).submitGeneration(
        GenerationRequest(photo: _photo('blob'), prompt: 'hello'),
      );

      final form = adapter.last!.data as FormData;
      expect(form.fields.map((e) => e.key), ['prompt']);
      expect(form.files.single.value.contentType.toString(), 'image/jpeg');
    });

    test('falls back to the file extension when no mime type is known', () async {
      final dir = Directory.systemTemp.createTempSync('api_client_test');
      addTearDown(() => dir.deleteSync(recursive: true));
      final file = File('${dir.path}/Selfie.PNG')..writeAsBytesSync([1, 2, 3]);

      final adapter = _FakeAdapter({'job_id': 'job-4'});
      await _client(adapter).submitGeneration(
        GenerationRequest(photo: XFile(file.path), prompt: 'p'),
      );
      final form = adapter.last!.data as FormData;
      expect(form.files.single.value.contentType.toString(), 'image/png');
    });

    test('declared mime type wins over the file name', () async {
      final adapter = _FakeAdapter({'job_id': 'job-3'});
      await _client(adapter).submitGeneration(
        GenerationRequest(
          photo: _photo('x.jpg', mime: 'image/webp'),
          prompt: 'p',
        ),
      );
      final form = adapter.last!.data as FormData;
      expect(form.files.single.value.contentType.toString(), 'image/webp');
    });
  });

  group('listTemplates', () {
    final payload = [
      {
        'id': 'a',
        'title': 'A',
        'tags': ['t'],
        'preview_url': '/template-previews/a.webp',
      },
    ];

    test('resolves preview urls and omits blank queries', () async {
      final adapter = _FakeAdapter(payload);
      final templates = await _client(adapter).listTemplates(query: '  ');

      expect(adapter.last!.queryParameters, isEmpty);
      expect(templates.single.previewUrl,
          'http://api.test/template-previews/a.webp');
    });

    test('sends a trimmed query', () async {
      final adapter = _FakeAdapter(payload);
      await _client(adapter).listTemplates(query: ' beach ');
      expect(adapter.last!.queryParameters, {'q': 'beach'});
    });
  });

  test('getJobStatus resolves the result url', () async {
    final adapter = _FakeAdapter({
      'job_id': 'j',
      'status': 'succeeded',
      'result_url': '/images/j.png',
      'error': null,
    });
    final job = await _client(adapter).getJobStatus('j');
    expect(job.resultUrl, 'http://api.test/images/j.png');
  });

  group('authentication', () {
    test('sends the bearer token when one is available', () async {
      final adapter = _FakeAdapter({'job_id': 'j', 'status': 'queued'});
      await _client(adapter, tokenProvider: () => 'tok-1').getJobStatus('j');

      expect(adapter.last!.headers['Authorization'], 'Bearer tok-1');
    });

    test('sends no Authorization header without a token', () async {
      final adapter = _FakeAdapter({'job_id': 'j', 'status': 'queued'});
      await _client(adapter, tokenProvider: () => null).getJobStatus('j');

      expect(adapter.last!.headers.containsKey('Authorization'), isFalse);
    });

    test('a 401 from a protected call fires onUnauthorized', () async {
      var fired = 0;
      final client = _client(
        _FakeAdapter({'detail': {'error': 'unauthorized'}}, status: 401),
        onUnauthorized: () => fired++,
      );

      await expectLater(client.getJobStatus('j'), throwsA(isA<DioException>()));
      expect(fired, 1);
    });

    test('a 401 from login or register does not fire onUnauthorized', () async {
      var fired = 0;
      final client = _client(
        _FakeAdapter({'detail': {'error': 'invalid_credentials'}}, status: 401),
        onUnauthorized: () => fired++,
      );

      await expectLater(
        client.login(email: 'a@b.co', password: 'x'),
        throwsA(isA<DioException>()),
      );
      await expectLater(
        client.register(email: 'a@b.co', password: 'x'),
        throwsA(isA<DioException>()),
      );
      expect(fired, 0);
    });

    test('register and login post credentials and parse the session', () async {
      final adapter = _FakeAdapter({'token': 't', 'id': 'u', 'email': 'a@b.co'});
      final client = _client(adapter);

      final registered =
          await client.register(email: 'a@b.co', password: 'password-1');
      expect(adapter.last!.method, 'POST');
      expect(adapter.last!.path, '/auth/register');
      expect(adapter.last!.data, {'email': 'a@b.co', 'password': 'password-1'});
      expect(registered.token, 't');
      expect(registered.userId, 'u');

      await client.login(email: 'a@b.co', password: 'password-1');
      expect(adapter.last!.path, '/auth/login');
      expect(adapter.last!.data, {'email': 'a@b.co', 'password': 'password-1'});
    });

    test('logout, fetchMe and deleteAccount hit the documented routes', () async {
      final adapter = _FakeAdapter({'id': 'u', 'email': 'a@b.co'});
      final client = _client(adapter);

      await client.logout();
      expect(adapter.last!.method, 'POST');
      expect(adapter.last!.path, '/auth/logout');

      final me = await client.fetchMe();
      expect(adapter.last!.method, 'GET');
      expect(adapter.last!.path, '/me');
      expect(me.email, 'a@b.co');

      await client.deleteAccount(password: 'password-1');
      expect(adapter.last!.method, 'DELETE');
      expect(adapter.last!.path, '/me');
      expect(adapter.last!.data, {'password': 'password-1'});
    });
  });

  group('account details', () {
    test('fetchMe parses plan, usage and referral', () async {
      final adapter = _FakeAdapter({
        'id': 'u',
        'email': 'a@b.co',
        'plan': 'free',
        'usage': {
          'daily_limit': 3,
          'used_today': 1,
          'bonus_credits': 5,
          'remaining': 7,
          'resets_at': '2026-10-17T00:00:00+00:00',
          'plan_limits': {'free': 3, 'premium': 30},
        },
        'referral': {
          'code': 'ABCD2345',
          'rewards': 0,
          'max_rewards': 10,
          'bonus_per_referral': 5,
        },
      });

      final me = await _client(adapter).fetchMe();

      expect(me.usage!.remaining, 7);
      expect(me.referral!.code, 'ABCD2345');
    });

    test('fetchMe tolerates a minimal payload', () async {
      final adapter = _FakeAdapter({'id': 'u', 'email': 'a@b.co'});

      final me = await _client(adapter).fetchMe();

      expect(me.usage, isNull);
      expect(me.referral, isNull);
    });

    test('register sends the referral code when given, trimmed', () async {
      final adapter = _FakeAdapter({'token': 't', 'id': 'u', 'email': 'a@b.co'});

      await _client(adapter).register(
        email: 'a@b.co',
        password: 'password-1',
        referralCode: ' k7m2qx9p ',
      );

      expect(adapter.last!.data, {
        'email': 'a@b.co',
        'password': 'password-1',
        'referral_code': 'k7m2qx9p',
      });
    });

    test('register omits a blank or missing referral code', () async {
      final adapter = _FakeAdapter({'token': 't', 'id': 'u', 'email': 'a@b.co'});
      final client = _client(adapter);

      await client.register(email: 'a@b.co', password: 'password-1');
      expect(adapter.last!.data, {'email': 'a@b.co', 'password': 'password-1'});

      await client.register(
        email: 'a@b.co',
        password: 'password-1',
        referralCode: '   ',
      );
      expect(adapter.last!.data, {'email': 'a@b.co', 'password': 'password-1'});
    });
  });
}
