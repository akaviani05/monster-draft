import csv
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from arena.storage import Database, password_valid

ROOT = Path(__file__).resolve().parents[1]


class CreateTeamTests(unittest.TestCase):
    def test_private_outputs_match_account_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="arena-credentials-test-") as work:
            directory = Path(work)
            db = Database(directory / "data")
            db.add_user("operator", "Synthetic operator", "synthetic-operator-only", "admin")
            csv_path = directory / "credentials.csv"
            pdf_path = directory / "credentials.pdf"
            cmd = [sys.executable, str(ROOT / "scripts/create_team.py"), "team01", "تیم آزمایشی",
                   "--data", str(db.directory), "--output", str(csv_path)]
            # CSV use remains independent of the optional renderer.
            subprocess.run(cmd, check=True, capture_output=True)
            with csv_path.open() as handle:
                credentials = next(csv.DictReader(handle))
            user = db.one("SELECT * FROM users WHERE username='team01'")
            self.assertTrue(password_valid(credentials["password"], user["password"]))
            self.assertEqual(csv_path.stat().st_mode & 0o777, 0o600)
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
            csv_path.unlink()
            if not (importlib.util.find_spec("cairo") and importlib.util.find_spec("gi")):
                return
            cmd[2] = "team02"
            pdf_path.write_bytes(b"existing")
            self.assertNotEqual(subprocess.run(cmd + ["--pdf", str(pdf_path)], capture_output=True).returncode, 0)
            self.assertFalse(csv_path.exists())
            self.assertEqual(pdf_path.read_bytes(), b"existing")
            self.assertIsNone(db.one("SELECT id FROM users WHERE username='team02'"))
            pdf_path.unlink()
            subprocess.run(cmd + ["--pdf", str(pdf_path)], check=True, capture_output=True)
            self.assertTrue(pdf_path.read_bytes().startswith(b"%PDF-"))
            self.assertEqual(pdf_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(len(db.rows("SELECT id FROM users WHERE role='team'")), 2)
            # Duplicate usernames clean up both new files, leaving existing users intact.
            csv_path.unlink()
            pdf_path.unlink()
            self.assertNotEqual(subprocess.run(cmd + ["--pdf", str(pdf_path)], capture_output=True).returncode, 0)
            self.assertFalse(csv_path.exists())
            self.assertFalse(pdf_path.exists())
