#!/usr/bin/env python3
"""Create one team with a generated password; run once per team or from a roster loop."""
import argparse
import csv
import os
from pathlib import Path
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from arena.service import APIError, Service
from arena.storage import Database


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username", help="3..32 ASCII letters, digits, dots, underscores or hyphens")
    parser.add_argument("name", help="Team display name, 1..60 characters")
    parser.add_argument("--data", type=Path, help="Defaults to ARENA_DATA or repository var/")
    parser.add_argument("--output", type=Path, required=True, help="New private CSV file; never overwritten")
    args = parser.parse_args()
    db = Database(args.data)
    admin = db.one("SELECT * FROM users WHERE role='admin' AND active=1 LIMIT 1")
    if not admin:
        parser.error("Initialize an administrator with python3 -m arena init first")
    password = secrets.token_urlsafe(18)
    # Persist credentials before the mutation so a disk error cannot lose a password.
    # Exclusive creation protects existing credentials; mode 0600 applies immediately.
    try:
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as exc:
        parser.error(f"Cannot create output file: {exc}")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["username", "name", "password"])
            writer.writerow([args.username.strip(), args.name.strip(), password])
            handle.flush()
            os.fsync(handle.fileno())
        Service(db).create_team(admin, {"username": args.username, "name": args.name, "password": password})
    except APIError as exc:
        args.output.unlink()
        parser.error(str(exc))
    print("Team created. Credentials saved to the requested private CSV file.")


if __name__ == "__main__":
    main()
