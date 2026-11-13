import csv
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

from arena.service import APIError, Service
from arena.storage import Database, password_valid
from scripts.create_teams import (create_batch, roster_pdf, CARD_MARGIN, CARD_WIDTH,
                                  CARD_HEIGHT, PAGE_WIDTH, PAGE_HEIGHT)

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(importlib.util.find_spec("cairo"), "Optional PDF dependency python3-cairo unavailable")
class CreateTeamsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="arena-batch-teams-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = Database(self.root / "data")
        uid = self.db.add_user("operator", "Synthetic operator", "synthetic-only-password", "admin")
        self.admin = self.db.one("SELECT * FROM users WHERE id=?", (uid,))
        self.csv = self.root / "credentials.csv"
        self.pdf = self.root / "credentials.pdf"

    def team_count(self):
        return len(self.db.rows("SELECT id FROM users WHERE role='team'"))

    def test_real_cli_exports_all_credentials_and_accounts_can_login(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/create_teams.py"), "26",
                                 "--data", str(self.db.directory), "--csv", str(self.csv),
                                 "--pdf", str(self.pdf)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        with self.csv.open() as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([r["username"] for r in rows], [f"team_{i:02d}" for i in range(1, 27)])
        self.assertEqual(self.team_count(), 26)
        for row in rows:
            self.assertEqual(row["name"], row["username"])
            self.assertRegex(row["password"], r"^[1-9][0-9]{5}$")
            self.assertNotIn(row["password"], result.stdout + result.stderr)
            user = self.db.one("SELECT * FROM users WHERE username=?", (row["username"],))
            self.assertTrue(password_valid(row["password"], user["password"]))
            self.assertNotEqual(row["password"], user["password"])
        # Authenticate with the same service used by HTTP logins.
        Service(self.db).login({"username": rows[0]["username"], "password": rows[0]["password"]}, "127.0.0.1")
        for path in (self.csv, self.pdf):
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertTrue(self.pdf.read_bytes().startswith(b"%PDF-"))
        if shutil.which("pdftotext") and shutil.which("pdfinfo"):
            info = subprocess.check_output(["pdfinfo", str(self.pdf)], text=True)
            self.assertRegex(info, r"Pages:\s+3")
            self.assert_card_positions(self.pdf, rows)

    def assert_card_positions(self, pdf_path, teams):
        xml = subprocess.check_output(["pdftotext", "-bbox", str(pdf_path), "-"], text=True)
        tree = ET.fromstring(xml)
        pages = tree.findall(".//{*}page")
        self.assertEqual(len(pages), (len(teams) + 9) // 10)
        seen = []
        for page_index, page in enumerate(pages):
            self.assertAlmostEqual(float(page.attrib["width"]), PAGE_WIDTH, places=2)
            self.assertAlmostEqual(float(page.attrib["height"]), PAGE_HEIGHT, places=2)
            cells = [[] for _ in range(10)]
            for word in page.findall(".//{*}word"):
                x0, y0, x1, y1 = [float(word.attrib[key]) for key in ("xMin", "yMin", "xMax", "yMax")]
                column = int((x0 - CARD_MARGIN) // CARD_WIDTH)
                row = int((y0 - CARD_MARGIN) // CARD_HEIGHT)
                self.assertIn(column, (0, 1))
                self.assertIn(row, range(5))
                # Every word is safely inside its own card, away from cut lines.
                self.assertGreaterEqual(x0, CARD_MARGIN + column * CARD_WIDTH + 10)
                self.assertLessEqual(x1, CARD_MARGIN + (column + 1) * CARD_WIDTH - 10)
                self.assertGreaterEqual(y0, CARD_MARGIN + row * CARD_HEIGHT + 10)
                self.assertLessEqual(y1, CARD_MARGIN + (row + 1) * CARD_HEIGHT - 8)
                cells[row * 2 + column].append(word.text)
            for index, words in enumerate(cells):
                team_index = page_index * 10 + index
                if team_index >= len(teams):
                    self.assertEqual(words, [])
                else:
                    team = teams[team_index]
                    self.assertEqual(words.count(team["username"]), 1)
                    self.assertEqual(words.count(team["password"]), 1)
                    self.assertIn("Username", words)
                    self.assertIn("Password", words)
                    seen.append(team["username"])
        self.assertEqual(seen, [team["username"] for team in teams])

    @unittest.skipUnless(shutil.which("pdftotext"), "Poppler is required for card geometry checks")
    def test_card_pagination_and_safe_cut_margins(self):
        for count in (1, 10, 11, 50):
            with self.subTest(count=count):
                teams = [{"username": f"team_{i:02d}", "password": f"{100000+i}"}
                         for i in range(1, count + 1)]
                # Also exercise the longest supported username.
                teams[-1]["username"] = "team_1000"
                self.pdf.write_bytes(roster_pdf(teams))
                self.assert_card_positions(self.pdf, teams)

    def test_random_password_bounds_and_numbering_past_99(self):
        with patch("scripts.create_teams.secrets.randbelow", side_effect=[0, 899999] * 50):
            create_batch(100, self.db, self.csv, self.pdf)
        with self.csv.open() as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows[0]["password"], "100000")
        self.assertEqual(rows[1]["password"], "999999")
        self.assertEqual(rows[-1]["username"], "team_100")

    def test_collision_rolls_back_whole_batch_and_cleans_exports(self):
        self.db.add_user("team_02", "Existing synthetic team", "existing-test-password")
        with self.assertRaises(APIError):
            create_batch(3, self.db, self.csv, self.pdf)
        self.assertEqual(self.team_count(), 1)
        self.assertIsNone(self.db.one("SELECT id FROM users WHERE username='team_01'"))
        self.assertFalse(self.csv.exists())
        self.assertFalse(self.pdf.exists())

    def test_existing_output_or_missing_directory_creates_no_accounts(self):
        self.pdf.write_bytes(b"existing file")
        with self.assertRaises(FileExistsError):
            create_batch(2, self.db, self.csv, self.pdf)
        self.assertFalse(self.csv.exists())
        self.assertEqual(self.pdf.read_bytes(), b"existing file")
        self.assertEqual(self.team_count(), 0)
        with self.assertRaises(FileNotFoundError):
            create_batch(2, self.db, self.csv, self.root / "missing" / "credentials.pdf")
        self.assertFalse(self.csv.exists())
        self.assertEqual(self.team_count(), 0)

    def test_invalid_count_missing_admin_or_renderer_creates_no_exports(self):
        for count in (0, -1, 1001):
            with self.assertRaises(ValueError):
                create_batch(count, self.db, self.csv, self.pdf)
        with patch("scripts.create_teams.roster_pdf", side_effect=RuntimeError("Missing renderer")):
            with self.assertRaises(RuntimeError):
                create_batch(2, self.db, self.csv, self.pdf)
        with self.db.transaction() as con:
            con.execute("UPDATE users SET active=0 WHERE role='admin'")
        with self.assertRaises(ValueError):
            create_batch(2, self.db, self.csv, self.pdf)
        self.assertEqual(self.team_count(), 0)
        self.assertFalse(self.csv.exists())
        self.assertFalse(self.pdf.exists())

    def test_service_requires_admin_and_preserves_normal_password_policy(self):
        service = Service(self.db)
        teams = [{"username": "team_01", "name": "team_01", "password": "123456"}]
        with self.assertRaises(APIError):
            service.provision_numbered_teams({"role": "team"}, teams)
        with self.assertRaises(APIError):
            service.create_team(self.admin, teams[0])
        for password in ("012345", "12345", "abcdef", "1234567"):
            with self.assertRaises(APIError):
                service.provision_numbered_teams(self.admin, [dict(teams[0], password=password)])
        self.assertEqual(self.team_count(), 0)
