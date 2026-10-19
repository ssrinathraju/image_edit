enum Plan {
  free,
  premium;

  /// Unknown or missing plans read as free, the most restrictive one.
  static Plan parse(String? value) =>
      Plan.values.firstWhere((p) => p.name == value, orElse: () => Plan.free);
}

class Usage {
  const Usage({
    required this.dailyLimit,
    required this.usedToday,
    required this.bonusCredits,
    required this.remaining,
    required this.resetsAt,
    required this.planLimits,
  });

  factory Usage.fromJson(Map<String, dynamic> json) => Usage(
        dailyLimit: json['daily_limit'] as int,
        usedToday: json['used_today'] as int,
        bonusCredits: json['bonus_credits'] as int,
        remaining: json['remaining'] as int,
        resetsAt: DateTime.parse(json['resets_at'] as String),
        planLimits: {
          for (final entry in (json['plan_limits'] as Map<String, dynamic>).entries)
            entry.key: entry.value as int,
        },
      );

  final int dailyLimit;
  final int usedToday;
  final int bonusCredits;
  final int remaining;
  final DateTime resetsAt;
  final Map<String, int> planLimits;
}

/// Whether the account accepted the face-photo consent the server currently asks for.
class ConsentState {
  const ConsentState({
    required this.currentVersion,
    this.acceptedVersion,
    this.acceptedAt,
  });

  factory ConsentState.fromJson(Map<String, dynamic> json) => ConsentState(
        currentVersion: json['current_version'] as String,
        acceptedVersion: json['accepted_version'] as String?,
        acceptedAt: json['accepted_at'] == null
            ? null
            : DateTime.parse(json['accepted_at'] as String),
      );

  final String currentVersion;
  final String? acceptedVersion;
  final DateTime? acceptedAt;

  bool get isCurrentVersionAccepted => acceptedVersion == currentVersion;
}

class Referral {
  const Referral({
    required this.code,
    required this.rewards,
    required this.maxRewards,
    required this.bonusPerReferral,
  });

  factory Referral.fromJson(Map<String, dynamic> json) => Referral(
        code: json['code'] as String,
        rewards: json['rewards'] as int,
        maxRewards: json['max_rewards'] as int,
        bonusPerReferral: json['bonus_per_referral'] as int,
      );

  final String code;
  final int rewards;
  final int maxRewards;
  final int bonusPerReferral;
}
