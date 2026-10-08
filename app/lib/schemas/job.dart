enum JobStatus { queued, running, succeeded, failed }

class GenerationJob {
  const GenerationJob({
    required this.jobId,
    required this.status,
    this.resultUrl,
    this.error,
  });

  final String jobId;
  final JobStatus status;
  final String? resultUrl;
  final String? error;

  factory GenerationJob.fromJson(Map<String, dynamic> json) {
    return GenerationJob(
      jobId: json['job_id'] as String,
      status: JobStatus.values.byName(json['status'] as String),
      resultUrl: json['result_url'] as String?,
      error: json['error'] as String?,
    );
  }
}
