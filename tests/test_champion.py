from contextlib import ExitStack
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from arena.storage import ROOT
from arena.worker import BOTS, execute
from runner.game import deck, result, score
from runner.referee import prepare_bot, run_match, sandbox_process
from scripts.evaluate_bot import selected_submissions
from tests.test_service import Fixture


class ChampionStrategyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = ExitStack()
        cls.addClassCleanup(cls.stack.close)
        cls.bot = cls.stack.enter_context(prepare_bot(ROOT/'bots/champion.cpp'))
        directory = Path(cls.stack.enter_context(tempfile.TemporaryDirectory()))
        harness = directory/'check.cpp'
        harness.write_text('#define CHAMPION_TEST\n' + (ROOT/'bots/champion.cpp').read_text() + r'''
int main() {
    using namespace duel;
    int mode, n, m, turn;
    while (cin >> mode >> banner >> my_seat >> turn >> n >> m) {
        --banner; initialize(); Bot bot; string card;
        for (int p = 0; p < 2; ++p) for (int i = 0; i < (p ? m : n); ++i) {
            cin >> card; bot.state.h[p].add((card[0]-'A')*5 + card[1]-'1');
        }
        for (int& c : bot.state.market) {
            cin >> card; c = (card[0]-'A')*5 + card[1]-'1';
        }
        if (mode) cout << bot.choose(turn) << endl;
        else cout << score(bot.state, 0) << ' ' << score(bot.state, 1)
                  << ' ' << winner(bot.state) << endl;
    }
}
''')
        cls.harness = cls.stack.enter_context(prepare_bot(harness))

    def check_positions(self, positions):
        process = sandbox_process(*self.harness)
        self.addCleanup(lambda: process.poll() is None and process.kill())
        output, error = process.communicate(('\n'.join(positions)+'\n').encode(), timeout=5)
        self.assertEqual(process.returncode, 0, error.decode())
        self.assertEqual(error, b'')
        return output.decode().splitlines()

    def test_exact_scoring_and_tiebreaks_match_authoritative_engine(self):
        rng = random.Random(187)
        positions, expected = [], []
        # Include an exact draw as well as random squads, spectra and banners.
        hands = [[f'{species}{k}' for species in 'ABC' for k in range(1,6)]]*2
        cases = [(hands, 2)]
        for _ in range(100):
            cards = deck(); rng.shuffle(cards)
            cases.append(([cards[:15], cards[15:30]], rng.randrange(1,6)))
        for hands, banner in cases:
            positions.append(f'0 {banner} 0 30 15 15 ' + ' '.join(hands[0]+hands[1]+['E5']*6))
            outcome = result(hands, banner)
            win = 0 if outcome['winner'] is None else 1 if outcome['winner'] == 0 else -1
            expected.append(f"{outcome['scores'][0]['total']} {outcome['scores'][1]['total']} {win}")
        self.assertEqual(self.check_positions(positions), expected)

    def test_last_pick_optimizes_all_bonuses_and_tiebreaks(self):
        rng = random.Random(821)
        positions, optimal = [], []
        for _ in range(80):
            cards = deck(); rng.shuffle(cards)
            a, b, market = cards[:14], cards[14:29], cards[29:35]
            banner = rng.randrange(1,6)
            positions.append(f'1 {banner} 1 29 14 15 ' + ' '.join(a+b+market))
            def key(i):
                hand = a+[market[i]]
                outcome = result([hand,b],banner)
                win = 0 if outcome['winner'] is None else 1 if outcome['winner'] == 0 else -1
                return (win,score(hand,b,banner)['total']-score(b,hand,banner)['total'])
            best = max(map(key, range(6)))
            optimal.append({i for i in range(6) if key(i) == best})
        for line, legal in zip(self.check_positions(positions), optimal):
            self.assertIn(int(line), legal)

    def test_persistent_protocol_both_seats_and_reproducibility(self):
        other = ('python', ROOT/'bots/guardian.py')
        traces = []
        for pair in ((self.bot,other),(other,self.bot),(self.bot,other)):
            replay = run_match(*pair, seed=83)
            self.assertEqual(replay['result']['reason'], 'completed')
            self.assertEqual(len(replay['turns']), 30)
            self.assertTrue(all(len(hand) == 15 for hand in replay['hands']))
            self.assertTrue(all(t['elapsed_ms'] < 300 for t in replay['turns']))
            self.assertTrue(all(t['wall_ms'] < 2000 and t['cpu_ms'] <= 2000 for t in replay['timing']))
            traces.append([t['choice'] for t in replay['turns']])
        self.assertEqual(traces[0], traces[2])


class ChampionWorkerTests(Fixture):
    def test_cpp_practice_bot_runs_in_both_seats_and_keeps_final_source(self):
        before = self.db.active_submission(self.a['id'])['id']
        self.assertEqual(BOTS['champion']['file'], 'champion.cpp')
        for seat in (0,1):
            with self.subTest(seat=seat), patch('arena.service.secrets.randbelow', return_value=seat):
                jid = self.service.create_practice(self.a, {'bot':'champion'})['id']
                execute(self.db, self.db.one('SELECT * FROM jobs WHERE id=?', (jid,)))
                job = self.db.one('SELECT * FROM jobs WHERE id=?', (jid,))
                self.assertEqual(job['status'], 'completed')
                self.assertEqual(job['reason'], 'completed')
                self.assertEqual(job[f's{seat}'], before)
                replay = self.service.replay(self.a, jid)
                self.assertEqual(len(replay['turns']), 30)
                self.assertEqual(replay['players'][1-seat], BOTS['champion']['name'])
                self.assertEqual(self.db.active_submission(self.a['id'])['id'], before)

    def test_evaluator_freezes_selected_versions_without_mutating_database(self):
        older = self.db.active_submission(self.a['id'])['id']
        self.submit(self.a)
        self.service.activate_submission(self.a, older, {})
        with self.db.connect() as con:
            before = '\n'.join(con.iterdump())
        frozen = selected_submissions(self.temp.name)
        self.assertEqual(len(frozen), 3)
        self.assertEqual(next(r['submission_id'] for r in frozen if r['team_id'] == self.a['id']), older)
        self.assertTrue(all(set(r) == {'team_id','submission_id','language','path','digest'} for r in frozen))
        with self.db.connect() as con:
            self.assertEqual('\n'.join(con.iterdump()), before)
        newer = self.submit(self.a)['id']
        archived = selected_submissions(self.temp.name, [older])
        self.assertEqual([row['submission_id'] for row in archived], [older])
        self.assertNotEqual(newer, older)

    def test_evaluator_uses_existing_cpp_binary(self):
        cpp = self.service.submit(self.a, {'source':(ROOT/'A.cpp').read_text(), 'language':'cpp', 'filename':'synthetic.cpp'})
        frozen = next(r for r in selected_submissions(self.temp.name) if r['team_id'] == self.a['id'])
        self.assertEqual(frozen['submission_id'], cpp['id'])
        self.assertEqual(frozen['language'], 'binary')
        self.assertEqual(frozen['path'], self.db.active_submission(self.a['id'])['path'])

    def test_evaluator_does_not_create_a_missing_database(self):
        missing = Path(self.temp.name)/'absent'
        with self.assertRaisesRegex(ValueError, 'does not exist'):
            selected_submissions(missing)
        self.assertFalse(missing.exists())
