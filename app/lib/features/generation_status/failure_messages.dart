const _pipelineFailedMessage =
    "We couldn't create your image this time. This one wasn't counted, so try again.";
const _generalFailureMessage =
    "Something went wrong and this one wasn't counted. Please try again.";

/// Plain-language text for a failed job; the raw server code is never shown.
String failureMessageFor(String? errorCode) {
  return switch (errorCode) {
    'pipeline_failed' => _pipelineFailedMessage,
    _ => _generalFailureMessage,
  };
}
