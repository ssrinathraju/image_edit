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
    );
  }

  final String id;
  final String email;
  final bool emailVerified;
  final Plan plan;
  final Usage? usage;
  final Referral? referral;
}
