/// A creation that was just saved on this device for [userId].
class ResultReady {
  const ResultReady({required this.jobId, required this.userId});

  final String jobId;
  final String userId;

  @override
  bool operator ==(Object other) =>
      other is ResultReady && other.jobId == jobId && other.userId == userId;

  @override
  int get hashCode => Object.hash(jobId, userId);
}
