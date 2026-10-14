import pytest
from pydantic import ValidationError

from image_edit_server.schemas.template import Template, TemplateSummary


def _entry(**overrides):
    base = {
        "id": "golden-hour-beach",
        "title": "Golden Hour Beach",
        "tags": ["beach"],
        "popularity": 90,
        "preview": "golden-hour-beach.webp",
        "prompt": "A person on a beach at sunset.",
    }
    base.update(overrides)
    return base


def test_valid_entry_parses():
    t = Template(**_entry())
    assert t.id == "golden-hour-beach"
    assert t.popularity == 90


@pytest.mark.parametrize("bad_id", ["Golden Beach", "-leading", "trailing-", "UPPER", "a_b", ""])
def test_bad_id_is_rejected(bad_id):
    with pytest.raises(ValidationError):
        Template(**_entry(id=bad_id))


@pytest.mark.parametrize("popularity", [-1, 101])
def test_out_of_range_popularity_is_rejected(popularity):
    with pytest.raises(ValidationError):
        Template(**_entry(popularity=popularity))


def test_summary_has_no_prompt_field():
    assert "prompt" not in TemplateSummary.model_fields
