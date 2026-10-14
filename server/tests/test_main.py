import pytest

from tests.helpers import TEST_TEMPLATES, build_templates_dir
from image_edit_server.configs.settings import Settings
from image_edit_server.main import create_app
from image_edit_server.repos.template_catalog import CatalogError


def test_create_app_fails_on_duplicate_template_id(tmp_path):
    entries = [TEST_TEMPLATES[0], {**TEST_TEMPLATES[1], "id": TEST_TEMPLATES[0]["id"]}]
    templates_dir = build_templates_dir(tmp_path / "t", entries)
    settings = Settings(TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(tmp_path / "s"))

    with pytest.raises(CatalogError, match=TEST_TEMPLATES[0]["id"]):
        create_app(settings)
