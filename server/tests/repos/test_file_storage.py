from pathlib import Path

from image_edit_server.repos.file_storage import save_upload, delete_inputs, input_dir


def test_save_upload_round_trip(tmp_path):
    data = b"fake-image-bytes"
    saved = save_upload("job-1", 0, data, storage_root=str(tmp_path))
    assert saved.exists()
    assert saved.read_bytes() == data


def test_save_upload_creates_directories(tmp_path):
    save_upload("job-2", 1, b"x", storage_root=str(tmp_path))
    assert (tmp_path / "inputs" / "job-2").is_dir()


def test_delete_inputs_removes_directory(tmp_path):
    save_upload("job-3", 0, b"y", storage_root=str(tmp_path))
    assert input_dir("job-3", str(tmp_path)).exists()

    delete_inputs("job-3", storage_root=str(tmp_path))

    assert not input_dir("job-3", str(tmp_path)).exists()


def test_delete_inputs_noop_when_missing(tmp_path):
    delete_inputs("nonexistent", storage_root=str(tmp_path))
