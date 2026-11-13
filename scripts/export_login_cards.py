#!/usr/bin/env python3
"""Reprint login cards from a saved private CSV without accessing any database."""
import argparse
import csv
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.login_cards import CREDENTIAL_DIR, render_login_cards


def export_cards(source, output):
    with Path(source).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {"username", "password"} <= set(reader.fieldnames):
            raise ValueError("CSV must have username and password columns")
        teams = list(reader)
    if not 1 <= len(teams) <= 1000:
        raise ValueError("CSV must contain 1..1000 teams")
    seen = set()
    for team in teams:
        username, password = team.get("username"), team.get("password")
        if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", username):
            raise ValueError("CSV contains an invalid username")
        if username in seen:
            raise ValueError("CSV contains duplicate usernames")
        seen.add(username)
        # Exports from both provisioning scripts fit this printable format.
        if not isinstance(password, str) or not 1 <= len(password) <= 32 or any(ord(c) < 33 or ord(c) > 126 for c in password):
            raise ValueError("CSV passwords must be 1..32 printable ASCII characters without spaces")
    pdf = render_login_cards(teams)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(pdf)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        Path(output).unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="Saved private credentials CSV")
    parser.add_argument("--pdf", type=Path, default=CREDENTIAL_DIR / "team-login-cards.pdf")
    args = parser.parse_args()
    try:
        if args.pdf.parent == CREDENTIAL_DIR:
            CREDENTIAL_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        export_cards(args.csv, args.pdf)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.error(str(exc))
    print("Login cards exported privately. No accounts or passwords were changed.")


if __name__ == "__main__":
    main()
