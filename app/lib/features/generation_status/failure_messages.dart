const _pipelineFailedMessage =
    "We couldn't create your image this time. This one wasn't counted, so try again.";
const _contentBlockedMessage =
    "This image was blocked by our content rules and wasn't counted.";
const _generalFailureMessage =
    "Something went wrong and this one wasn't counted. Please try again.";

/// Plain-language text for a failed job; the raw server code is never shown.
String failureMessageFor(String? errorCode) {
  return switch (errorCode) {
    'pipeline_failed' => _pipelineFailedMessage,
    'content_blocked' => _contentBlockedMessage,
    _ => _generalFailureMessage,
  };
}
