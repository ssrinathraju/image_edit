"""Grant or remove an account's admin role (operator tooling; there is no public endpoint).

Run from server/:
    uv run python scripts/set_role.py --email <address> --role admin
    uv run python scripts/set_role.py --email <address> --role user
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from image_edit_server.configs.settings import Settings
from image_edit_server.core.roles import ALL_ROLES
from image_edit_server.repos.user_store import SqliteUserStore, auth_db_path
from image_edit_server.services.auth_service import normalize_email


def set_role(email: str, role: str, settings: Optional[Settings] = None) -> int:
    """Apply the role; returns a process exit code and prints the outcome, never the email."""
    if role not in ALL_ROLES:
        print(f"unknown role {role!r}; choose one of: {', '.join(ALL_ROLES)}", file=sys.stderr)
        return 2
    db_path = Path(auth_db_path(settings or Settings())).resolve()
    if not db_path.is_file():
        # The store would happily create and migrate an empty database here.
        print(
            f"no database at {db_path}; run from the server's directory or set "
            "IMAGE_EDIT_STORAGE_ROOT / IMAGE_EDIT_AUTH_DB_PATH",
            file=sys.stderr,
        )
        return 3
    store = SqliteUserStore(str(db_path))
    try:
        if not store.set_role(normalize_email(email), role):
            print(f"no account found for that email in {db_path}", file=sys.stderr)
            return 1
    finally:
        store.close()
    print(f"the account now has the {role} role (database: {db_path})")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", required=True)
    args = parser.parse_args(argv)
    return set_role(args.email, args.role)


if __name__ == "__main__":
    sys.exit(main())
