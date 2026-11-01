/// Where a creation came from, so "Make another" can start again.
class CreationSource {
  const CreationSource.template(String this.templateId) : prompt = null;
  const CreationSource.prompt(String this.prompt) : templateId = null;

  /// Reads leniently: a missing or malformed value is no source, never an error.
  static CreationSource? tryFromJson(Object? json) {
    if (json is! Map<String, dynamic>) return null;
    final kind = json['kind'];
    if (kind == _templateKind) {
      final id = json['templateId'];
      return id is String && id.isNotEmpty ? CreationSource.template(id) : null;
    }
    if (kind == _promptKind) {
      final prompt = json['prompt'];
      return prompt is String && prompt.isNotEmpty
          ? CreationSource.prompt(prompt)
          : null;
    }
    return null;
  }

  /// Set for a template source, null for a prompt source.
  final String? templateId;

  /// Set for a prompt source, null for a template source.
  final String? prompt;

  Map<String, dynamic> toJson() => templateId != null
      ? {'kind': _templateKind, 'templateId': templateId}
      : {'kind': _promptKind, 'prompt': prompt};
}

const String _templateKind = 'template';
const String _promptKind = 'prompt';

/// A finished generation kept on the device.
class Creation {
  const Creation({
    required this.jobId,
    required this.label,
    required this.finishedAt,
    this.source,
  });

  factory Creation.fromJson(Map<String, dynamic> json) => Creation(
    jobId: json['jobId'] as String,
    label: json['label'] as String,
    finishedAt: DateTime.parse(json['finishedAt'] as String),
    source: CreationSource.tryFromJson(json['source']),
  );

  final String jobId;
  final String label;
  final DateTime finishedAt;
  final CreationSource? source;

  Map<String, dynamic> toJson() => {
    'jobId': jobId,
    'label': label,
    'finishedAt': finishedAt.toUtc().toIso8601String(),
    if (source != null) 'source': source!.toJson(),
  };
}

/// A submitted generation that has not been saved yet.
class PendingGeneration {
  const PendingGeneration({
    required this.jobId,
    required this.label,
    required this.submittedAt,
    this.source,
  });

  factory PendingGeneration.fromJson(Map<String, dynamic> json) =>
      PendingGeneration(
        jobId: json['jobId'] as String,
        label: json['label'] as String,
        submittedAt: DateTime.parse(json['submittedAt'] as String),
        source: CreationSource.tryFromJson(json['source']),
      );

  final String jobId;
  final String label;
  final DateTime submittedAt;
  final CreationSource? source;

  Map<String, dynamic> toJson() => {
    'jobId': jobId,
    'label': label,
    'submittedAt': submittedAt.toUtc().toIso8601String(),
    if (source != null) 'source': source!.toJson(),
  };
}
