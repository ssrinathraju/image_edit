/// A finished generation kept on the device.
class Creation {
  const Creation({
    required this.jobId,
    required this.label,
    required this.finishedAt,
  });

  factory Creation.fromJson(Map<String, dynamic> json) => Creation(
        jobId: json['jobId'] as String,
        label: json['label'] as String,
        finishedAt: DateTime.parse(json['finishedAt'] as String),
      );

  final String jobId;
  final String label;
  final DateTime finishedAt;

  Map<String, dynamic> toJson() => {
        'jobId': jobId,
        'label': label,
        'finishedAt': finishedAt.toUtc().toIso8601String(),
      };
}

/// A submitted generation that has not been saved yet.
class PendingGeneration {
  const PendingGeneration({
    required this.jobId,
    required this.label,
    required this.submittedAt,
  });

  factory PendingGeneration.fromJson(Map<String, dynamic> json) =>
      PendingGeneration(
        jobId: json['jobId'] as String,
        label: json['label'] as String,
        submittedAt: DateTime.parse(json['submittedAt'] as String),
      );

  final String jobId;
  final String label;
  final DateTime submittedAt;

  Map<String, dynamic> toJson() => {
        'jobId': jobId,
        'label': label,
        'submittedAt': submittedAt.toUtc().toIso8601String(),
      };
}
