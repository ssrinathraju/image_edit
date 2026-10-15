from image_edit_server.core.referral_codes import ALPHABET, CODE_LENGTH, generate_code, normalize_code


def test_generated_codes_use_only_the_unambiguous_alphabet():
    for _ in range(200):
        code = generate_code()
        assert len(code) == CODE_LENGTH == 8
        assert set(code) <= set(ALPHABET)


def test_alphabet_has_no_lookalikes():
    assert not set("01OI") & set(ALPHABET)
    assert len(ALPHABET) == 32


def test_normalization_ignores_case_and_surrounding_spaces():
    assert normalize_code("  k7m2qx9p ") == "K7M2QX9P"
