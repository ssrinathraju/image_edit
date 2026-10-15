import base64

from image_edit_server.core.passwords import hash_password, verify_password

PASSWORD = "correct horse battery"


def test_round_trip():
    assert verify_password(PASSWORD, hash_password(PASSWORD))


def test_wrong_password_fails():
    assert not verify_password("wrong password", hash_password(PASSWORD))


def test_same_password_hashes_differently():
    assert hash_password(PASSWORD) != hash_password(PASSWORD)


def test_hash_does_not_contain_password():
    stored = hash_password(PASSWORD)
    assert PASSWORD not in stored
    assert base64.b64encode(PASSWORD.encode()).decode() not in stored


def test_malformed_stored_value_is_false_not_an_error():
    for stored in ["", "garbage", "pbkdf2_sha256$1$2", "bcrypt$1$2$3", "pbkdf2_sha256$x$!!$!!", "pbkdf2_sha256$0$AAAA$AAAA"]:
        assert verify_password(PASSWORD, stored) is False
