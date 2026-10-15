from image_edit_server.repos import file_storage
from image_edit_server.repos.in_memory_job_store import InMemoryJobStore
from image_edit_server.schemas.job import Job
from image_edit_server.services.account_cleanup import purge_user_jobs


def _job_with_files(store, root, user_id: str) -> str:
    job_id = store.create(Job(id="", prompt="p", user_id=user_id))
    out = file_storage.output_path(job_id, str(root))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"png")
    file_storage.save_upload(job_id, 0, b"face", str(root))
    return job_id


def test_removes_jobs_outputs_and_inputs_of_the_user(tmp_path):
    store = InMemoryJobStore()
    job_id = _job_with_files(store, tmp_path, "u1")

    purge_user_jobs("u1", store, str(tmp_path))

    assert store.get(job_id) is None
    assert not file_storage.output_path(job_id, str(tmp_path)).exists()
    assert not file_storage.input_dir(job_id, str(tmp_path)).exists()


def test_leaves_other_users_files_untouched(tmp_path):
    store = InMemoryJobStore()
    _job_with_files(store, tmp_path, "u1")
    other = _job_with_files(store, tmp_path, "u2")

    purge_user_jobs("u1", store, str(tmp_path))

    assert store.get(other) is not None
    assert file_storage.output_path(other, str(tmp_path)).exists()
    assert file_storage.input_dir(other, str(tmp_path)).exists()


def test_missing_files_do_not_raise(tmp_path):
    store = InMemoryJobStore()
    job_id = store.create(Job(id="", prompt="p", user_id="u1"))

    purge_user_jobs("u1", store, str(tmp_path))

    assert store.get(job_id) is None
