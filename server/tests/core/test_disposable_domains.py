from pathlib import Path

import pytest

from image_edit_server.configs.settings import Settings
from image_edit_server.core.disposable_domains import load_disposable_domains
from image_edit_server.main import create_app

SEED_FILE = Path(__file__).parents[2] / "seed" / "abuse" / "disposable_domains.txt"


@pytest.fixture
def domains(tmp_path):
    path = tmp_path / "domains.txt"
    path.write_text(
        "# a comment\n\nMailinator.com\n  guerrillamail.com  \n# yopmail.com\n",
        encoding="utf-8",
    )
    return load_disposable_domains(str(path))


def test_a_listed_domain_is_disposable(domains):
    assert domains.is_disposable("someone@mailinator.com")
    assert domains.listed_domain("someone@mailinator.com") == "mailinator.com"


def test_a_subdomain_of_a_listed_domain_is_disposable(domains):
    assert domains.listed_domain("someone@mx.eu.mailinator.com") == "mailinator.com"


def test_matching_ignores_letter_case(domains):
    assert domains.is_disposable("Someone@MAILINATOR.COM")


def test_a_domain_that_only_shares_a_suffix_is_not_disposable(domains):
    assert not domains.is_disposable("someone@notmailinator.com")


def test_an_unlisted_domain_is_not_disposable(domains):
    assert not domains.is_disposable("someone@example.com")


def test_comments_and_blank_lines_are_ignored(domains):
    assert not domains.is_disposable("someone@yopmail.com")
    assert not domains.is_disposable("someone@")
    assert not domains.is_disposable("someone@a comment")


def test_the_seed_list_blocks_known_services_and_not_apple_relay_or_gmail():
    seeded = load_disposable_domains(str(SEED_FILE))

    assert seeded.is_disposable("x@mailinator.com")
    assert seeded.is_disposable("x@yopmail.com")
    assert not seeded.is_disposable("x@privaterelay.appleid.com")
    assert not seeded.is_disposable("x@gmail.com")


def test_a_missing_file_raises_an_error_naming_it(tmp_path):
    missing = tmp_path / "nope.txt"

    with pytest.raises(ValueError, match="nope.txt"):
        load_disposable_domains(str(missing))


def test_a_missing_list_file_fails_create_app_and_names_the_file(tmp_path, templates_dir):
    missing = tmp_path / "missing_domains.txt"
    settings = Settings(
        TEMPLATES_DIR=str(templates_dir),
        STORAGE_ROOT=str(tmp_path / "s"),
        DISPOSABLE_DOMAINS_FILE=str(missing),
    )

    with pytest.raises(ValueError, match="missing_domains.txt"):
        create_app(settings)
