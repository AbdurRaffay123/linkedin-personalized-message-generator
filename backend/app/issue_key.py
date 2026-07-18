"""Issue an API key for a user (creating the user if needed).

Usage:
    python -m app.issue_key user@example.com ["key name"]

Prints the plaintext key ONCE — store it now; only its hash is kept.
"""
from __future__ import annotations

import sys

from app.core.auth import issue_key
from app.db.base import SessionLocal


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    email = argv[0]
    name = argv[1] if len(argv) > 1 else None
    db = SessionLocal()
    try:
        raw = issue_key(db, email, name)
    finally:
        db.close()
    print(f"user:  {email}")
    print(f"key:   {raw}")
    print("^ store this now — it will not be shown again.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
