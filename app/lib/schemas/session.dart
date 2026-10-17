import 'account.dart';

/// A signed-in user's credentials as kept on the device.
class Session {
  const Session({
    required this.token,
    required this.userId,
    required this.email,
    this.emailVerified = true,
  });

  /// [emailVerified] reads as true when absent, so a server that predates
  /// email verification never makes the app nag.
  factory Session.fromJson(Map<String, dynamic> json) => Session(
        token: json['token'] as String,
        userId: json['id'] as String,
        email: json['email'] as String,
        emailVerified: json['email_verified'] as bool? ?? true,
      );

  final String token;
  final String userId;
  final String email;
  final bool emailVerified;

  Map<String, dynamic> toJson() => {
        'token': token,
        'id': userId,
        'email': email,
        'email_verified': emailVerified,
      };

  @override
  bool operator ==(Object other) =>
      other is Session &&
      other.token == token &&
      other.userId == userId &&
      other.email == email &&
      other.emailVerified == emailVerified;

  @override
  int get hashCode => Object.hash(token, userId, email, emailVerified);
}

/// A sign-in through Google or Apple: the session plus whether it made a new account.
class ProviderSession {
  const ProviderSession({required this.session, required this.created});

  factory ProviderSession.fromJson(Map<String, dynamic> json) => ProviderSession(
        session: Session.fromJson(json),
        created: json['created'] as bool? ?? false,
      );

  final Session session;
  final bool created;
}

/// The account behind a session, as returned by `GET /me`. [usage] and
/// [referral] are null when talking to a server that predates them.
class UserProfile {
  const UserProfile({
    required this.id,
    required this.email,
    this.emailVerified = true,
    this.plan = Plan.free,
    this.usage,
    this.referral,
    this.providers = const [],
    this.hasPassword = true,
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    final usage = json['usage'];
    final referral = json['referral'];
    return UserProfile(
      id: json['id'] as String,
      email: json['email'] as String,
      emailVerified: json['email_verified'] as bool? ?? true,
      plan: Plan.parse(json['plan'] as String?),
      usage: usage is Map<String, dynamic> ? Usage.fromJson(usage) : null,
      referral:
          referral is Map<String, dynamic> ? Referral.fromJson(referral) : null,
      providers: [
        for (final name in (json['providers'] as List<dynamic>? ?? const []))
          name as String,
      ],
      hasPassword: json['has_password'] as bool? ?? true,
    );
  }

  final String id;
  final String email;
  final bool emailVerified;
  final Plan plan;
  final Usage? usage;
  final Referral? referral;

  /// Sign-in providers linked to the account (`google`, `apple`); empty on an old server.
  final List<String> providers;

  /// Reads as true when absent, so an old server never sends the user to a provider flow.
  final bool hasPassword;
}
