"""Change an account's plan (operator tooling; there is no public endpoint).

Run from server/:
    uv run python scripts/set_plan.py --email ana@example.com --plan premium
"""
from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from image_edit_server.configs.settings import Settings
from image_edit_server.core.plans import ALL_PLANS
from image_edit_server.repos.user_store import SqliteUserStore, auth_db_path
from image_edit_server.services.auth_service import normalize_email


def set_plan(email: str, plan: str, settings: Optional[Settings] = None) -> int:
    """Apply the plan; returns a process exit code and prints the outcome."""
    if plan not in ALL_PLANS:
        print(f"unknown plan {plan!r}; choose one of: {', '.join(ALL_PLANS)}", file=sys.stderr)
        return 2
    store = SqliteUserStore(auth_db_path(settings or Settings()))
    try:
        if not store.set_plan(normalize_email(email), plan):
            print(f"no account with email {email!r}", file=sys.stderr)
            return 1
    finally:
        store.close()
    print(f"{email} is now on the {plan} plan")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--email", required=True)
    parser.add_argument("--plan", required=True)
    args = parser.parse_args(argv)
    return set_plan(args.email, args.plan)


if __name__ == "__main__":
    sys.exit(main())
