import inspect

from image_edit_server.core.user_store import UserStore
from image_edit_server.repos.user_store import SqliteUserStore

# Public methods that callers use but the UserStore protocol does not list.
EXTRA_PUBLIC_METHODS = [
    "close",
    "set_plan",
    "confirm_age",
    "set_consent",
    "clear_consent",
    "sign_in_with_identity",
    "has_identity",
    "list_providers",
    "set_apple_refresh_token",
    "get_apple_refresh_token",
    "redeem_referral",
    "delete_session",
]


def _public_names(cls: type) -> list[str]:
    return [
        name
        for name, member in inspect.getmembers(cls, callable)
        if not name.startswith("_")
    ]


def test_every_protocol_method_exists_on_the_sqlite_store():
    missing = [name for name in _public_names(UserStore) if not hasattr(SqliteUserStore, name)]
    assert missing == []


def test_every_other_public_store_method_still_exists():
    missing = [name for name in EXTRA_PUBLIC_METHODS if not callable(getattr(SqliteUserStore, name, None))]
    assert missing == []
