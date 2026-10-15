import pytest

from image_edit_server.repos.in_memory_job_store import InMemoryJobStore
from image_edit_server.schemas.job import Job, JobStatus


@pytest.fixture
def store() -> InMemoryJobStore:
    return InMemoryJobStore()


def test_create_assigns_ulid(store):
    job = Job(id="", prompt="test")
    job_id = store.create(job)
    assert job_id
    assert len(job_id) == 26  # ULID length


def test_get_returns_job(store):
    job = Job(id="", prompt="test")
    job_id = store.create(job)
    retrieved = store.get(job_id)
    assert retrieved is not None
    assert retrieved.id == job_id


def test_get_returns_none_for_unknown(store):
    assert store.get("does-not-exist") is None


def test_update_patches_fields(store):
    job = Job(id="", prompt="test")
    job_id = store.create(job)
    store.update(job_id, status=JobStatus.running)
    assert store.get(job_id).status == JobStatus.running


def test_list_queued_returns_only_queued(store):
    j1 = Job(id="", prompt="a")
    j2 = Job(id="", prompt="b")
    id1 = store.create(j1)
    id2 = store.create(j2)
    store.update(id2, status=JobStatus.running)

    queued_ids = {j.id for j in store.list_queued()}
    assert id1 in queued_ids
    assert id2 not in queued_ids


def test_list_for_user_returns_only_that_users_jobs(store):
    mine = store.create(Job(id="", prompt="a", user_id="u1"))
    store.create(Job(id="", prompt="b", user_id="u2"))

    assert [j.id for j in store.list_for_user("u1")] == [mine]
    assert list(store.list_for_user("nobody")) == []


def test_delete_removes_the_job_and_ignores_unknown_ids(store):
    job_id = store.create(Job(id="", prompt="a"))

    store.delete(job_id)
    store.delete("does-not-exist")

    assert store.get(job_id) is None
