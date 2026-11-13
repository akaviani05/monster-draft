import csv
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.backup_contest import backup
from scripts.export_login_cards import export_cards
from scripts.login_cards import CREDENTIAL_DIR

ROOT = Path(__file__).resolve().parents[1]


class OperatorToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="arena-operator-tools-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_csv(self, rows):
        path = self.root / "credentials.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["username", "name", "password"])
            writer.writeheader()
            writer.writerows(rows)
        return path

    @unittest.skipUnless(importlib.util.find_spec("cairo"), "Optional python3-cairo unavailable")
    def test_reprint_cli_does_not_access_database_or_change_csv(self):
        rows = [{"username": "team_01", "name": "Synthetic team", "password": "123456"}]
        csv_path = self.write_csv(rows)
        original = csv_path.read_bytes()
        pdf = self.root / "cards.pdf"
        env = dict(os.environ, ARENA_DATA=str(self.root / "must-not-exist"))
        cmd = ["bash", str(ROOT / "scripts/contest.sh"), "cards", str(csv_path), "--pdf", str(pdf)]
        result = subprocess.run(cmd, env=env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / "must-not-exist").exists())
        self.assertEqual(csv_path.read_bytes(), original)
        self.assertEqual(pdf.stat().st_mode & 0o777, 0o600)
        original_pdf = pdf.read_bytes()
        self.assertNotEqual(subprocess.run(cmd, env=env, capture_output=True).returncode, 0)
        self.assertEqual(pdf.read_bytes(), original_pdf)
        if shutil.which("pdftotext"):
            text = subprocess.check_output(["pdftotext", str(pdf), "-"], text=True)
            self.assertIn("team_01", text)
            self.assertIn("123456", text)

    @unittest.skipUnless(importlib.util.find_spec("cairo"), "Optional python3-cairo unavailable")
    def test_numbered_defaults_share_central_directory(self):
        from arena.storage import Database
        from scripts import create_teams
        db = Database(self.root / "data")
        db.add_user("operator", "Synthetic operator", "synthetic-only-password", "admin")
        central = self.root / "private-exports"
        with patch.object(create_teams, "CREDENTIAL_DIR", central), patch.object(
                sys, "argv", ["create_teams.py", "2", "--data", str(db.directory)]):
            create_teams.main()
        self.assertEqual(central.stat().st_mode & 0o777, 0o700)
        self.assertEqual({p.name for p in central.iterdir()},
                         {"team-credentials.csv", "team-login-cards.pdf"})
        self.assertEqual(len(db.rows("SELECT id FROM users WHERE role='team'")), 2)

    def test_bad_csv_rejected_without_pdf(self):
        pdf = self.root / "cards.pdf"
        for rows in ([], [{"username": "bad user", "name": "test", "password": "123456"}],
                     [{"username": "team_01", "name": "test", "password": "line\nbreak"}],
                     [{"username": "team_01", "name": "test", "password": "123456"}] * 2):
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):
                    export_cards(self.write_csv(rows), pdf)
                self.assertFalse(pdf.exists())

    def test_backup_copies_whole_snapshot_and_refuses_existing_or_nested_output(self):
        data = self.root / "data"
        data.mkdir()
        (data / "arena.sqlite3").write_bytes(b"synthetic database placeholder")
        (data / "arena.sqlite3-wal").write_bytes(b"synthetic WAL")
        (data / "submissions").mkdir()
        (data / "submissions" / "synthetic.txt").write_text("synthetic source placeholder")
        (data / "replays").mkdir()
        (data / "replays" / "synthetic.json").write_text("{}")
        output = self.root / "backup"
        backup(data, output)
        self.assertEqual(output.stat().st_mode & 0o777, 0o700)
        for source in data.rglob("*"):
            if source.is_file():
                self.assertEqual(source.read_bytes(), (output / source.relative_to(data)).read_bytes())
        with self.assertRaises(FileExistsError):
            backup(data, output)
        with self.assertRaises(ValueError):
            backup(data, data / "backup")
        result = subprocess.run(["bash", str(ROOT / "scripts/contest.sh"), "backup",
                                 "--data", str(data), "--output", str(self.root / "unsafe")], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "unsafe").exists())

    def test_wrapper_rejects_unknown_commands_and_run_arguments(self):
        for args in (["unknown"], ["run", "--port", "9000"]):
            result = subprocess.run(["bash", str(ROOT / "scripts/contest.sh"), *args], capture_output=True)
            self.assertEqual(result.returncode, 2)
        self.assertEqual(CREDENTIAL_DIR, ROOT / "output/pdf/team-credentials")
