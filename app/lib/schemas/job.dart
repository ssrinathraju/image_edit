enum JobStatus { queued, running, succeeded, failed }

class GenerationJob {
  const GenerationJob({
    required this.jobId,
    required this.status,
    this.resultUrl,
    this.error,
    this.expiresAt,
  });

  final String jobId;
  final JobStatus status;
  final String? resultUrl;
  final String? error;

  /// When the server deletes the image; null when absent or unreadable.
  final DateTime? expiresAt;

  factory GenerationJob.fromJson(Map<String, dynamic> json) {
    return GenerationJob(
      jobId: json['job_id'] as String,
      status: JobStatus.values.byName(json['status'] as String),
      resultUrl: json['result_url'] as String?,
      error: json['error'] as String?,
      expiresAt: DateTime.tryParse(json['expires_at'] as String? ?? ''),
    );
  }
}
