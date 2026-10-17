import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/schemas/account.dart';
import 'package:image_edit/schemas/session.dart';

void main() {
  test('a full /me payload is parsed', () {
    final profile = UserProfile.fromJson({
      'id': 'u1',
      'email': 'ana@example.com',
      'created_at': '2026-01-01T00:00:00+00:00',
      'plan': 'premium',
      'usage': {
        'daily_limit': 30,
        'used_today': 4,
        'bonus_credits': 5,
        'remaining': 31,
        'resets_at': '2026-10-17T00:00:00+00:00',
        'plan_limits': {'free': 3, 'premium': 30},
      },
      'referral': {
        'code': 'K7M2QX9P',
        'rewards': 3,
        'max_rewards': 10,
        'bonus_per_referral': 5,
      },
    });

    expect(profile.plan, Plan.premium);
    expect(profile.usage!.remaining, 31);
    expect(profile.usage!.resetsAt, DateTime.utc(2026, 10, 17));
    expect(profile.usage!.planLimits, {'free': 3, 'premium': 30});
    expect(profile.referral!.code, 'K7M2QX9P');
    expect(profile.referral!.rewards, 3);
    expect(profile.referral!.maxRewards, 10);
  });

  test('an old server payload without the new fields still parses', () {
    final profile = UserProfile.fromJson({'id': 'u1', 'email': 'ana@example.com'});

    expect(profile.plan, Plan.free);
    expect(profile.usage, isNull);
    expect(profile.referral, isNull);
  });

  test('email_verified is read when present and defaults to true when absent', () {
    final unverified = UserProfile.fromJson(
      {'id': 'u1', 'email': 'ana@example.com', 'email_verified': false},
    );
    final verified = UserProfile.fromJson(
      {'id': 'u1', 'email': 'ana@example.com', 'email_verified': true},
    );
    final oldServer = UserProfile.fromJson({'id': 'u1', 'email': 'ana@example.com'});

    expect(unverified.emailVerified, isFalse);
    expect(verified.emailVerified, isTrue);
    expect(oldServer.emailVerified, isTrue);
  });

  test('a session parses email_verified and defaults it to true when absent', () {
    final base = {'token': 't', 'id': 'u1', 'email': 'ana@example.com'};

    expect(Session.fromJson({...base, 'email_verified': false}).emailVerified, isFalse);
    expect(Session.fromJson({...base, 'email_verified': true}).emailVerified, isTrue);
    expect(Session.fromJson(base).emailVerified, isTrue);
  });

  test('an unknown plan reads as free', () {
    expect(Plan.parse('gold'), Plan.free);
    expect(Plan.parse(null), Plan.free);
  });

  test('providers and has_password are parsed', () {
    final profile = UserProfile.fromJson({
      'id': 'u1',
      'email': 'ana@example.com',
      'providers': ['apple', 'google'],
      'has_password': false,
    });

    expect(profile.providers, ['apple', 'google']);
    expect(profile.hasPassword, isFalse);
  });

  test('providers default to empty and has_password to true when absent', () {
    final profile = UserProfile.fromJson({'id': 'u1', 'email': 'ana@example.com'});

    expect(profile.providers, isEmpty);
    expect(profile.hasPassword, isTrue);
  });

  test('a provider sign-in response parses created and defaults it to false', () {
    final base = {'token': 't', 'id': 'u1', 'email': 'ana@example.com'};

    expect(ProviderSession.fromJson({...base, 'created': true}).created, isTrue);
    expect(ProviderSession.fromJson({...base, 'created': false}).created, isFalse);
    expect(ProviderSession.fromJson(base).created, isFalse);
    expect(ProviderSession.fromJson(base).session.token, 't');
  });
}
