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


from scripts.login_cards import render_login_cards, CREDENTIAL_DIR


def credential_pdf(username, name, password):
    """Use the same ten-card A4 layout as batch creation and CSV reprinting."""
    return render_login_cards([{"username": username, "name": name, "password": password}])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username", help="3..32 ASCII letters, digits, dots, underscores or hyphens")
    parser.add_argument("name", help="Team display name, 1..60 characters")
    parser.add_argument("--data", type=Path, help="Defaults to ARENA_DATA or repository var/")
    parser.add_argument("--output", type=Path, required=True, help="New private CSV file; never overwritten")
    parser.add_argument("--pdf", nargs="?", type=Path, const=CREDENTIAL_DIR / "single-team-login-card.pdf", help="Also export a cut-out card; optional path overrides the central default")
    args = parser.parse_args()
    db = Database(args.data)
    admin = db.one("SELECT * FROM users WHERE role='admin' AND active=1 LIMIT 1")
    if not admin:
        parser.error("Initialize an administrator with python3 -m arena init first")
    if args.pdf and args.pdf.parent == CREDENTIAL_DIR:
        CREDENTIAL_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    password = secrets.token_urlsafe(18)
    # Render before creating files/accounts, so missing PDF dependencies are harmless.
    try:
        pdf = credential_pdf(args.username.strip(), args.name.strip(), password) if args.pdf else None
    except RuntimeError as exc:
        parser.error(str(exc))
    created = []
    try:
        # Write both artifacts before the database mutation; never overwrite files.
        for path, binary in [(args.output, False)] + ([(args.pdf, True)] if args.pdf else []):
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created.append(path)
            with os.fdopen(fd, "wb" if binary else "w", **({} if binary else {"encoding": "utf-8", "newline": ""})) as handle:
                if binary:
                    handle.write(pdf)
                else:
                    writer = csv.writer(handle)
                    writer.writerow(["username", "name", "password"])
                    writer.writerow([args.username.strip(), args.name.strip(), password])
                handle.flush()
                os.fsync(handle.fileno())
    except OSError as exc:
        for path in created:
            path.unlink(missing_ok=True)
        parser.error(f"Cannot write credential files: {exc}")
    try:
        Service(db).create_team(admin, {"username": args.username, "name": args.name, "password": password})
    except APIError as exc:
        for path in created:
            path.unlink(missing_ok=True)
        parser.error(str(exc))
    print("Team created. Credentials saved to the requested private files.")


if __name__ == "__main__":
    main()
