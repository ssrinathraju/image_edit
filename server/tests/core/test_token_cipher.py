import base64

import pytest

from image_edit_server.core.token_cipher import TokenCipher
from tests.helpers import make_token_cipher

TOKEN = "apple-refresh-secret-value"
ACCOUNT = "01ACCOUNTA"


@pytest.fixture
def cipher() -> TokenCipher:
    return make_token_cipher()


def test_a_value_round_trips(cipher):
    assert cipher.decrypt(cipher.encrypt(TOKEN, ACCOUNT), ACCOUNT) == TOKEN


def test_output_is_versioned_and_hides_the_token(cipher):
    sealed = cipher.encrypt(TOKEN, ACCOUNT)

    assert sealed.startswith("v1:")
    assert TOKEN not in sealed
    assert base64.urlsafe_b64encode(TOKEN.encode()).decode() not in sealed


def test_two_encryptions_of_the_same_token_differ(cipher):
    assert cipher.encrypt(TOKEN, ACCOUNT) != cipher.encrypt(TOKEN, ACCOUNT)


def test_the_wrong_account_id_does_not_decrypt(cipher):
    assert cipher.decrypt(cipher.encrypt(TOKEN, ACCOUNT), "01ACCOUNTB") is None


def test_the_wrong_key_does_not_decrypt(cipher):
    assert make_token_cipher(8).decrypt(cipher.encrypt(TOKEN, ACCOUNT), ACCOUNT) is None


def test_one_changed_byte_does_not_decrypt(cipher):
    sealed = cipher.encrypt(TOKEN, ACCOUNT)
    raw = bytearray(base64.urlsafe_b64decode(sealed[3:]))
    raw[-1] ^= 1
    tampered = "v1:" + base64.urlsafe_b64encode(bytes(raw)).decode()

    assert cipher.decrypt(tampered, ACCOUNT) is None


@pytest.mark.parametrize(
    "value",
    [TOKEN, "v2:AAAA", "v1:%%%not-base64%%%", "v1:AAAA", "v1:", ""],
    ids=["no-prefix", "other-version", "bad-base64", "too-short", "empty-body", "empty"],
)
def test_malformed_values_return_none(cipher, value):
    assert cipher.decrypt(value, ACCOUNT) is None


def test_a_key_of_the_wrong_length_is_refused():
    with pytest.raises(ValueError, match="32 bytes"):
        TokenCipher(b"short")
