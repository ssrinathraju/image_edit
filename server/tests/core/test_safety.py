import pytest

from image_edit_server.core.safety import TermMatcher, load_terms, normalize_text


@pytest.fixture
def matcher() -> TermMatcher:
    return TermMatcher(["nude", "ass", "child porn", "Gore"])


@pytest.mark.parametrize(
    "prompt", ["nude", "N-U-D-3", "Nüde", "NUDE!!", "n.u.d.e", "a nud3 portrait", "n u d e"]
)
def test_disguised_terms_are_caught(matcher, prompt):
    assert matcher.matches(prompt)


def test_term_inside_a_longer_harmless_word_is_allowed(matcher):
    assert not matcher.matches("a classic portrait in a grassy field")


def test_term_as_its_own_word_is_caught(matcher):
    assert matcher.matches("a big ass donkey")


def test_multi_word_phrase_matches_across_separators(matcher):
    assert matcher.matches("Child---Porn")
    assert matcher.matches("child   p0rn")


def test_phrase_words_apart_do_not_match(matcher):
    assert not matcher.matches("a child enjoying a porn-free evening")


def test_swapped_letters_in_terms_are_normalised(matcher):
    assert matcher.matches("g0r3")
    assert matcher.matches("an @ss")


def test_spelled_out_run_only_matches_single_word_terms(matcher):
    assert matcher.matches("g o r e")
    assert not matcher.matches("c h i l d p o r n")


def test_harmless_prompt_passes(matcher):
    assert not matcher.matches("a portrait on a sunny beach, 4k")


def test_normalize_text_strips_accents_and_collapses_separators():
    assert normalize_text("  Café--B1ZARRE  ") == "cafe bizarre"


def test_load_terms_skips_comments_and_blank_lines(tmp_path):
    path = tmp_path / "terms.txt"
    path.write_text("# comment\n\nnude\n  child porn  \n#another\n")

    assert load_terms(str(path)) == ["nude", "child porn"]


def test_an_empty_list_refuses_to_load(tmp_path):
    path = tmp_path / "terms.txt"
    path.write_text("# only comments\n\n")

    with pytest.raises(ValueError, match="no terms"):
        load_terms(str(path))


def test_a_missing_file_refuses_to_load(tmp_path):
    with pytest.raises(ValueError, match="cannot be read"):
        load_terms(str(tmp_path / "missing.txt"))


def test_shipped_starter_list_loads_and_blocks_its_own_terms():
    terms = load_terms("seed/safety/blocked_terms.txt")
    matcher = TermMatcher(terms)

    assert len(terms) < 80
    assert all(matcher.matches(term) for term in terms)
    assert not matcher.matches("a portrait in front of a mountain at sunset")
