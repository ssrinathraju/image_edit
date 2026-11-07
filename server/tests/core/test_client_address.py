from image_edit_server.core.client_address import client_address

CONNECTION = "10.0.0.1"


def test_zero_hops_uses_the_connection_even_with_a_forwarded_header():
    assert client_address(CONNECTION, "1.1.1.1, 2.2.2.2", 0) == CONNECTION


def test_one_hop_takes_the_last_entry_not_the_spoofed_first():
    assert client_address(CONNECTION, "6.6.6.6, 9.9.9.9", 1) == "9.9.9.9"


def test_two_hops_take_the_second_entry_from_the_right():
    assert client_address(CONNECTION, "6.6.6.6, 9.9.9.9, 10.1.1.1", 2) == "9.9.9.9"


def test_a_header_shorter_than_the_hops_falls_back_to_the_connection():
    assert client_address(CONNECTION, "9.9.9.9", 2) == CONNECTION


def test_whitespace_around_entries_is_stripped():
    assert client_address(CONNECTION, "  6.6.6.6 ,   9.9.9.9  ", 1) == "9.9.9.9"


def test_an_empty_or_absent_header_falls_back_to_the_connection():
    assert client_address(CONNECTION, "", 1) == CONNECTION
    assert client_address(CONNECTION, " , ", 1) == CONNECTION
    assert client_address(CONNECTION, None, 1) == CONNECTION


def test_no_connection_gives_a_stable_placeholder():
    assert client_address(None, None, 0) == "unknown"
