#!/usr/bin/env python3
"""Create numbered teams and export their generated six-digit passwords privately."""
import argparse
import csv
import os
from pathlib import Path
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from arena.service import APIError, Service
from arena.storage import Database


# Compatibility aliases for callers and geometry regression checks.
from scripts.login_cards import (render_login_cards as roster_pdf, CREDENTIAL_DIR,
                                 PAGE_WIDTH, PAGE_HEIGHT, CARD_MARGIN, CARD_WIDTH, CARD_HEIGHT)


def create_batch(count, db, csv_path, pdf_path):
    if not 1 <= count <= 1000:
        raise ValueError("Team count must be 1..1000")
    admin = db.one("SELECT * FROM users WHERE role='admin' AND active=1 LIMIT 1")
    if not admin:
        raise ValueError("Initialize an administrator with python3 -m arena init first")
    teams = [{"username": f"team_{i:02d}", "name": f"team_{i:02d}",
              "password": str(100000 + secrets.randbelow(900000))} for i in range(1, count + 1)]
    pdf = roster_pdf(teams)
    created = []
    try:
        # Persist both exports before the atomic account import; reject all overwrites.
        for path, binary in [(Path(csv_path), False), (Path(pdf_path), True)]:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created.append(path)
            with os.fdopen(fd, "wb" if binary else "w", **({} if binary else {"encoding": "utf-8", "newline": ""})) as handle:
                if binary:
                    handle.write(pdf)
                else:
                    writer = csv.DictWriter(handle, fieldnames=["username", "name", "password"])
                    writer.writeheader()
                    writer.writerows(teams)
                handle.flush()
                os.fsync(handle.fileno())
        Service(db).provision_numbered_teams(admin, teams)
    except (OSError, APIError):
        for path in created:
            path.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("n", type=int, help="Number of teams, 1..1000; names start at team_01")
    parser.add_argument("--data", type=Path, help="Defaults to ARENA_DATA or repository var/")
    parser.add_argument("--csv", type=Path, default=CREDENTIAL_DIR / "team-credentials.csv", help="New private CSV roster (default: output/pdf/team-credentials/team-credentials.csv)")
    parser.add_argument("--pdf", type=Path, default=CREDENTIAL_DIR / "team-login-cards.pdf", help="New private PDF (default: output/pdf/team-credentials/team-login-cards.pdf)")
    args = parser.parse_args()
    if not 1 <= args.n <= 1000:
        parser.error("Team count must be 1..1000")
    if args.csv.parent == CREDENTIAL_DIR or args.pdf.parent == CREDENTIAL_DIR:
        CREDENTIAL_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        create_batch(args.n, Database(args.data), args.csv, args.pdf)
    except (ValueError, RuntimeError, OSError, APIError) as exc:
        parser.error(str(exc))
    print(f"Created {args.n} teams. Credentials saved privately to CSV and PDF.")


if __name__ == "__main__":
    main()
