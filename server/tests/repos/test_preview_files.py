from image_edit_server.repos.preview_files import remove_unreferenced_previews, write_preview_file


def test_write_leaves_only_the_final_file(tmp_path):
    target = tmp_path / "previews"

    write_preview_file(target, "a-123.webp", b"data")

    assert [p.name for p in target.iterdir()] == ["a-123.webp"]
    assert (target / "a-123.webp").read_bytes() == b"data"


def test_sweep_removes_only_unreferenced_files(tmp_path, user_store, templates_dir):
    from image_edit_server.services.template_seed import load_template_catalog

    previews = tmp_path / "previews"
    load_template_catalog(user_store, templates_dir, previews)
    (previews / "stray.webp").write_bytes(b"x")

    assert remove_unreferenced_previews(user_store, previews) == 1
    assert not (previews / "stray.webp").exists()
