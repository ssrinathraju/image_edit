/// A signed-in user's credentials as kept on the device.
class Session {
  const Session({
    required this.token,
    required this.userId,
    required this.email,
  });

  factory Session.fromJson(Map<String, dynamic> json) => Session(
        token: json['token'] as String,
        userId: json['id'] as String,
        email: json['email'] as String,
      );

  final String token;
  final String userId;
  final String email;

  Map<String, dynamic> toJson() =>
      {'token': token, 'id': userId, 'email': email};

  @override
  bool operator ==(Object other) =>
      other is Session &&
      other.token == token &&
      other.userId == userId &&
      other.email == email;

  @override
  int get hashCode => Object.hash(token, userId, email);
}

/// The account behind a session, as returned by `GET /me`.
class UserProfile {
  const UserProfile({required this.id, required this.email});

  final String id;
  final String email;
}
