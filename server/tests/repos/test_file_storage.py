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


def _touch(path, data=b"x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_list_output_files_returns_only_regular_png_files(tmp_path):
    from image_edit_server.repos.file_storage import list_output_files

    _touch(tmp_path / "outputs" / "a.png")
    _touch(tmp_path / "outputs" / "b.png")
    _touch(tmp_path / "outputs" / "notes.txt")
    _touch(tmp_path / "outputs" / "nested" / "c.png")
    (tmp_path / "outputs" / "dir.png").mkdir()
    target = _touch(tmp_path / "elsewhere.png")
    (tmp_path / "outputs" / "link.png").symlink_to(target)

    names = sorted(p.name for p in list_output_files(str(tmp_path)))

    assert names == ["a.png", "b.png"]


def test_list_input_job_ids_returns_only_real_directories(tmp_path):
    from image_edit_server.repos.file_storage import list_input_job_ids

    _touch(tmp_path / "inputs" / "job-1" / "face_0.jpg")
    _touch(tmp_path / "inputs" / "job-2" / "face_0.jpg")
    _touch(tmp_path / "inputs" / "stray-file.txt")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (tmp_path / "inputs" / "linked").symlink_to(elsewhere, target_is_directory=True)

    assert sorted(list_input_job_ids(str(tmp_path))) == ["job-1", "job-2"]


def test_listing_a_missing_folder_is_empty(tmp_path):
    from image_edit_server.repos.file_storage import list_input_job_ids, list_output_files

    assert list_output_files(str(tmp_path)) == []
    assert list_input_job_ids(str(tmp_path)) == []


def test_delete_output_removes_the_file_and_tolerates_a_missing_one(tmp_path):
    from image_edit_server.repos.file_storage import delete_output

    path = _touch(tmp_path / "outputs" / "job-1.png")

    delete_output("job-1", str(tmp_path))
    delete_output("job-1", str(tmp_path))

    assert not path.exists()
