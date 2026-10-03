from image_edit_server.schemas.job import JobStatus


def test_enum_values_match_spec():
    assert JobStatus.queued.value == "queued"
    assert JobStatus.running.value == "running"
    assert JobStatus.succeeded.value == "succeeded"
    assert JobStatus.failed.value == "failed"
