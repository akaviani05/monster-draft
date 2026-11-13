from pathlib import Path
import tempfile
import unittest

from arena.service import APIError, Service
from arena.worker import execute
from runner.referee import run_match
from tests.test_service import Fixture


class DebugServiceTests(Fixture):
    def test_test_run_preserves_final_code_and_private_diagnostics_across_restart(self):
        before = self.db.active_submission(self.a['id'])['id']
        source = "import sys\nprint('<student-debug>', file=sys.stderr)\n" + (Path('B.py').read_text())
        job = self.service.create_debug(self.a, {'source': source, 'filename': 'draft.py', 'bot': 'greedy'})
        self.assertEqual(self.db.active_submission(self.a['id'])['id'], before)
        with self.assertRaises(APIError):
            self.service.diagnostics(self.a, job['id'])
        execute(self.db, self.db.one('SELECT * FROM jobs WHERE id=?', (job['id'],)))
        report = Service(self.db).diagnostics(self.a, job['id'])
        self.assertEqual(report['result']['reason'], 'completed')
        self.assertIn('<student-debug>', ''.join(e['text'] for e in report['events'] if e['stream'] == 'stderr'))
        stdout = ''.join(e['text'] for e in report['events'] if e['stream'] == 'stdout')
        self.assertEqual(len(stdout.splitlines()), 15)
        replay = self.service.replay(self.a, job['id'])
        self.assertNotIn('stderr', replay)
        self.assertNotIn('_diagnostics', replay)
        for outsider in (self.b, self.admin):
            with self.assertRaises(APIError) as error:
                self.service.diagnostics(outsider, job['id'])
            self.assertEqual(error.exception.status, 404)
        self.assertEqual(self.service.dashboard(self.a)['stats']['played'], 0)
        self.assertTrue(all(r['played'] == 0 for r in self.service.scoreboard(self.a)['items']))
        self.assertEqual(self.service.list_submissions(self.a)['total'], 1)

    def test_compiler_and_runtime_errors_are_reported_without_changing_final(self):
        before = self.db.active_submission(self.a['id'])['id']
        with self.assertRaises(APIError) as error:
            self.service.create_debug(self.a, {'source': 'int main( {', 'language': 'cpp', 'bot': 'random'})
        self.assertIn('کامپایل', error.exception.message)
        job = self.service.create_debug(self.a, {'source': "input()\nraise RuntimeError('synthetic failure')\n", 'bot': 'random'})
        execute(self.db, self.db.one('SELECT * FROM jobs WHERE id=?', (job['id'],)))
        report = self.service.diagnostics(self.a, job['id'])
        self.assertNotEqual(report['result']['reason'], 'completed')
        self.assertIn('RuntimeError: synthetic failure', ''.join(e['text'] for e in report['events'] if e['stream'] == 'stderr'))
        self.assertEqual(self.db.active_submission(self.a['id'])['id'], before)

    def test_debug_validates_bot_role_source_and_queue_quota(self):
        for body in ({'bot': 'unknown', 'source': 'pass'}, {'bot': 'random', 'source': 'bad syntax!'}):
            with self.assertRaises(APIError):
                self.service.create_debug(self.a, body)
        with self.assertRaises(APIError):
            self.service.create_debug(self.admin, {'bot': 'random', 'source': 'pass'})
        for _ in range(10):
            self.service.create_practice(self.a, {'bot': 'random'})
        with self.assertRaises(APIError) as error:
            self.service.create_debug(self.a, {'bot': 'random', 'source': 'pass'})
        self.assertEqual(error.exception.status, 429)


class DebugTraceTests(unittest.TestCase):
    def test_trace_matches_exact_protocol_and_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'bot.py'
            path.write_text("import sys\nprint('x'*30000, file=sys.stderr)\n" + Path('B.py').read_text())
            replay = run_match(('python', path), ('python', Path('bots/greedy.py').resolve()), seed=41, debug_seat=0)
        self.assertEqual(replay['result']['reason'], 'completed')
        report = replay['_diagnostics']
        self.assertTrue(report['truncated'])
        self.assertLessEqual(len(report['events']), 512)
        expected = str(replay['banner'])+'\n'
        for turn in replay['turns']:
            expected += ('YOURTURN\n' if turn['seat'] == 0 else 'OPPTURN\n') + '\n'.join(turn['market'])+'\n'
            if turn['seat'] != 0:
                expected += str(turn['choice'])+'\n'
        self.assertEqual(''.join(e['text'] for e in report['events'] if e['stream'] == 'stdin'), expected)
        self.assertEqual(''.join(e['text'] for e in report['events'] if e['stream'] == 'stdout'), ''.join(str(t['choice'])+'\n' for t in replay['turns'] if t['seat'] == 0))
        self.assertLessEqual(sum(len(e['text']) for e in report['events'] if e['stream'] == 'stderr'), 16384)
