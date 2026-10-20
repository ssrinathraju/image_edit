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

final _dob = DateTime(1990, 1, 31);

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

  group('submitReport', () {
    test('posts the job id, category, note and image as multipart', () async {
      final adapter = _FakeAdapter({'report_id': 'r1'});

      await _client(adapter).submitReport(
        jobId: 'job-1',
        category: 'violence',
        note: 'looks wrong',
        imageBytes: Uint8List.fromList([1, 2, 3]),
      );

      final form = adapter.last!.data as FormData;
      expect(adapter.last!.path, '/reports');
      expect(adapter.last!.method, 'POST');
      expect({for (final f in form.fields) f.key: f.value},
          {'job_id': 'job-1', 'category': 'violence', 'note': 'looks wrong'});
      expect(form.files.single.key, 'image');
      expect(form.files.single.value.contentType.toString(), 'image/png');
    });

    test('omits an empty note', () async {
      final adapter = _FakeAdapter({'report_id': 'r1'});

      await _client(adapter).submitReport(
        jobId: 'job-1',
        category: 'other',
        note: '',
        imageBytes: Uint8List.fromList([1]),
      );

      final form = adapter.last!.data as FormData;
      expect(form.fields.map((f) => f.key), ['job_id', 'category']);
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
        client.register(email: 'a@b.co', password: 'x', dateOfBirth: _dob),
        throwsA(isA<DioException>()),
      );
      expect(fired, 0);
    });

    test('register posts the credentials and returns nothing', () async {
      final adapter = _FakeAdapter(<String, dynamic>{});

      await _client(adapter).register(
        email: 'a@b.co',
        password: 'password-1',
        dateOfBirth: _dob,
      );

      expect(adapter.last!.method, 'POST');
      expect(adapter.last!.path, '/auth/register');
      expect(adapter.last!.data, {
        'email': 'a@b.co',
        'password': 'password-1',
        'date_of_birth': '1990-01-31',
      });
    });

    test('register sends a trimmed referral code and omits a blank one', () async {
      final adapter = _FakeAdapter(<String, dynamic>{});
      final client = _client(adapter);

      await client.register(
        email: 'a@b.co',
        password: 'password-1',
        dateOfBirth: _dob,
        referralCode: '  k7m2qx9p ',
      );
      expect(adapter.last!.data['referral_code'], 'k7m2qx9p');

      await client.register(
        email: 'a@b.co',
        password: 'password-1',
        dateOfBirth: _dob,
        referralCode: '  ',
      );
      expect(adapter.last!.data, {
        'email': 'a@b.co',
        'password': 'password-1',
        'date_of_birth': '1990-01-31',
      });
    });

    test('confirmRegistration posts the code and parses the session', () async {
      final adapter = _FakeAdapter({'token': 't', 'id': 'u', 'email': 'a@b.co'});

      final session =
          await _client(adapter).confirmRegistration(
            email: 'a@b.co',
            code: '123456',
            password: 'password-1',
          );

      expect(adapter.last!.method, 'POST');
      expect(adapter.last!.path, '/auth/register/confirm');
      expect(adapter.last!.data, {
        'email': 'a@b.co',
        'code': '123456',
        'password': 'password-1',
      });
      expect((session.token, session.userId, session.email), ('t', 'u', 'a@b.co'));
    });

    test('login posts credentials and parses the session', () async {
      final adapter = _FakeAdapter({'token': 't', 'id': 'u', 'email': 'a@b.co'});

      final session = await _client(adapter).login(email: 'a@b.co', password: 'password-1');

      expect(adapter.last!.path, '/auth/login');
      expect(adapter.last!.data, {'email': 'a@b.co', 'password': 'password-1'});
      expect(session.token, 't');
    });

    test('requestPasswordReset posts the email', () async {
      final adapter = _FakeAdapter(<String, dynamic>{});

      await _client(adapter).requestPasswordReset(email: 'a@b.co');

      expect(adapter.last!.path, '/auth/password-reset/request');
      expect(adapter.last!.data, {'email': 'a@b.co'});
    });

    test('confirmPasswordReset posts the code and parses the new session', () async {
      final adapter = _FakeAdapter({
        'token': 'fresh',
        'id': 'u',
        'email': 'a@b.co',
      });

      final session = await _client(adapter).confirmPasswordReset(
        email: 'a@b.co',
        code: '123456',
        newPassword: 'new password 1',
      );

      expect(adapter.last!.path, '/auth/password-reset/confirm');
      expect(adapter.last!.data, {
        'email': 'a@b.co',
        'code': '123456',
        'new_password': 'new password 1',
      });
      expect(session.token, 'fresh');
      expect(session.email, 'a@b.co');
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

  group('provider sign-in', () {
    final sessionBody = {
      'token': 'tok',
      'id': 'u1',
      'email': 'gina@example.com',
      'email_verified': true,
      'created': true,
    };

    test('signInWithGoogle posts the id token and parses created', () async {
      final adapter = _FakeAdapter(sessionBody);

      final result = await _client(adapter).signInWithGoogle(idToken: 'g-id');

      expect(adapter.last!.method, 'POST');
      expect(adapter.last!.path, '/auth/oauth/google');
      expect(adapter.last!.data, {'id_token': 'g-id'});
      expect(result.created, isTrue);
      expect(result.session.token, 'tok');
    });

    test('signInWithApple posts the token, raw nonce and code', () async {
      final adapter = _FakeAdapter({...sessionBody, 'created': false});

      final result = await _client(adapter).signInWithApple(
        identityToken: 'a-id',
        nonce: 'raw',
        authorizationCode: 'code',
      );

      expect(adapter.last!.path, '/auth/oauth/apple');
      expect(adapter.last!.data, {
        'identity_token': 'a-id',
        'nonce': 'raw',
        'authorization_code': 'code',
      });
      expect(result.created, isFalse);
    });

    test('a 401 from a provider endpoint does not expire the session', () async {
      var expired = false;
      final adapter = _FakeAdapter({
        'detail': {'error': 'invalid_provider_token', 'detail': 'x'},
      }, status: 401);
      final client = _client(adapter, onUnauthorized: () => expired = true);

      await expectLater(client.signInWithGoogle(idToken: 'bad'), throwsA(isA<DioException>()));
      await expectLater(
        client.signInWithApple(identityToken: 'bad', nonce: 'n', authorizationCode: 'c'),
        throwsA(isA<DioException>()),
      );

      expect(expired, isFalse);
    });

    test('redeemReferral posts the code', () async {
      final adapter = _FakeAdapter(<String, dynamic>{});

      await _client(adapter).redeemReferral(code: 'K7M2QX9P');

      expect(adapter.last!.method, 'POST');
      expect(adapter.last!.path, '/me/referral');
      expect(adapter.last!.data, {'code': 'K7M2QX9P'});
    });

    test('deleteAccount sends the provider form without a password', () async {
      final adapter = _FakeAdapter(<String, dynamic>{});

      await _client(adapter).deleteAccount(
        provider: 'apple',
        token: 'fresh',
        nonce: 'raw',
      );

      expect(adapter.last!.method, 'DELETE');
      expect(adapter.last!.path, '/me');
      expect(adapter.last!.data, {'provider': 'apple', 'token': 'fresh', 'nonce': 'raw'});
    });

    test('deleteAccount with google sends no nonce', () async {
      final adapter = _FakeAdapter(<String, dynamic>{});

      await _client(adapter).deleteAccount(provider: 'google', token: 'fresh');

      expect(adapter.last!.data, {'provider': 'google', 'token': 'fresh'});
    });

    test('fetchMe parses providers and hasPassword', () async {
      final adapter = _FakeAdapter({
        'id': 'u',
        'email': 'a@b.co',
        'providers': ['google'],
        'has_password': false,
      });

      final me = await _client(adapter).fetchMe();

      expect(me.providers, ['google']);
      expect(me.hasPassword, isFalse);
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
        dateOfBirth: _dob,
        referralCode: ' k7m2qx9p ',
      );

      expect(adapter.last!.data, {
        'email': 'a@b.co',
        'password': 'password-1',
        'date_of_birth': '1990-01-31',
        'referral_code': 'k7m2qx9p',
      });
    });

    test('register omits a blank or missing referral code', () async {
      final adapter = _FakeAdapter({'token': 't', 'id': 'u', 'email': 'a@b.co'});
      final client = _client(adapter);

      await client.register(
        email: 'a@b.co',
        password: 'password-1',
        dateOfBirth: _dob,
      );
      expect(adapter.last!.data, {
        'email': 'a@b.co',
        'password': 'password-1',
        'date_of_birth': '1990-01-31',
      });

      await client.register(
        email: 'a@b.co',
        password: 'password-1',
        dateOfBirth: _dob,
        referralCode: '   ',
      );
      expect(adapter.last!.data, {
        'email': 'a@b.co',
        'password': 'password-1',
        'date_of_birth': '1990-01-31',
      });
    });
  });

  group('age and consent calls', () {
    test('register sends the date of birth as YYYY-MM-DD, zero-padded', () async {
      final adapter = _FakeAdapter(<String, dynamic>{});

      await _client(adapter).register(
        email: 'a@b.co',
        password: 'password-1',
        dateOfBirth: DateTime(2001, 3, 4),
      );

      expect(adapter.last!.data['date_of_birth'], '2001-03-04');
    });

    test('provider sign-ins send the date only when given', () async {
      final adapter = _FakeAdapter({
        'token': 'tok',
        'id': 'u1',
        'email': 'gina@example.com',
        'created': true,
      });
      final client = _client(adapter);

      await client.signInWithGoogle(idToken: 'g-id');
      expect(adapter.last!.data, {'id_token': 'g-id'});

      await client.signInWithGoogle(idToken: 'g-id', dateOfBirth: _dob);
      expect(adapter.last!.data, {'id_token': 'g-id', 'date_of_birth': '1990-01-31'});

      await client.signInWithApple(
        identityToken: 'a-id',
        nonce: 'raw',
        authorizationCode: 'code',
        dateOfBirth: _dob,
      );
      expect(adapter.last!.data, {
        'identity_token': 'a-id',
        'nonce': 'raw',
        'authorization_code': 'code',
        'date_of_birth': '1990-01-31',
      });
    });

    test('confirmAge posts the date to /me/age', () async {
      final adapter = _FakeAdapter(<String, dynamic>{});

      await _client(adapter).confirmAge(dateOfBirth: _dob);

      expect(adapter.last!.method, 'POST');
      expect(adapter.last!.path, '/me/age');
      expect(adapter.last!.data, {'date_of_birth': '1990-01-31'});
    });

    test('acceptConsent posts the version and withdrawConsent deletes', () async {
      final adapter = _FakeAdapter(<String, dynamic>{});
      final client = _client(adapter);

      await client.acceptConsent(version: '2');
      expect(adapter.last!.method, 'POST');
      expect(adapter.last!.path, '/me/consent');
      expect(adapter.last!.data, {'version': '2'});

      await client.withdrawConsent();
      expect(adapter.last!.method, 'DELETE');
      expect(adapter.last!.path, '/me/consent');
    });

    test('a 401 from the age and consent calls expires the session', () async {
      var expired = 0;
      final client = _client(
        _FakeAdapter({'detail': {'error': 'unauthorized'}}, status: 401),
        onUnauthorized: () => expired++,
      );

      await expectLater(
        client.confirmAge(dateOfBirth: _dob),
        throwsA(isA<DioException>()),
      );
      expect(expired, 1);
    });
  });

  test('the real client has connect and receive timeouts', () {
    final options = apiBaseOptions('http://api.test');

    expect(options.baseUrl, 'http://api.test');
    expect(options.connectTimeout, connectTimeout);
    expect(options.receiveTimeout, receiveTimeout);
    expect(connectTimeout, greaterThan(Duration.zero));
    expect(receiveTimeout, greaterThan(Duration.zero));
  });
}
