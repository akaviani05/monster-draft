from concurrent.futures import ThreadPoolExecutor

from arena.service import APIError
from arena.storage import Database
from tests.test_service import Fixture


class ProfileScoreboardTests(Fixture):
    def test_profile_persists_and_labels_are_visible_without_changing_team_name(self):
        self.service.update_profile(self.a, {'student1': '  دانش‌آموز اول  ', 'student2': '<student>'})
        reopened = Database(self.temp.name)
        self.assertEqual(reopened.one('SELECT student1 FROM users WHERE id=?', (self.a['id'],))['student1'], 'دانش‌آموز اول')
        team = next(t for t in self.service.dashboard(self.b)['teams'] if t['id'] == self.a['id'])
        self.assertEqual(team['name'], 'alpha')
        self.assertEqual(team['display_name'], 'alpha (دانش‌آموز اول، <student>)')
        admin_team = next(t for t in self.service.admin_overview(self.admin)['teams'] if t['id'] == self.a['id'])
        self.assertEqual(admin_team['student2'], '<student>')
        self.service.update_profile(self.a, {'student1': '', 'student2': ''})
        self.assertEqual(self.service.profile(self.b)['student1'], '')

    def test_profile_rejects_extra_fields_invalid_names_and_admin_edits(self):
        for body in ({'student1': [], 'student2': ''}, {'student1': 'x'*81, 'student2': ''},
                     {'student1': 'a\nb', 'student2': ''}, {'student1': '', 'student2': '', 'id': self.b['id']}):
            with self.assertRaises(APIError):
                self.service.update_profile(self.a, body)
        with self.assertRaises(APIError):
            self.service.update_profile(self.admin, {'student1': 'a', 'student2': 'b'})

    def test_friendly_request_waits_for_acceptance_and_freezes_the_right_versions(self):
        sender_version = self.db.active_submission(self.a['id'])['id']
        invitation = self.service.create_friendly(self.a, {'team_id': self.b['id']})
        self.assertEqual(invitation['status'], 'pending')
        self.assertIsNone(invitation['job_id'])
        self.assertEqual(self.db.one('SELECT COUNT(*) AS n FROM jobs')['n'], 0)
        self.submit(self.a)
        recipient_version = self.submit(self.b)['id']
        response = self.service.respond(self.b, invitation['id'], {'action': 'accept'})
        job_id = response['job_id']
        row = self.db.one('SELECT * FROM jobs WHERE id=?', (job_id,))
        self.assertEqual({row['p0']: row['s0'], row['p1']: row['s1']}, {self.a['id']: sender_version, self.b['id']: recipient_version})
        self.assertIn(job_id, [j['id'] for j in self.service.matches(self.b)['items']])
        with self.assertRaises(APIError):
            self.service.job_status(self.c, job_id)
        with self.assertRaises(APIError):
            self.service.respond(self.b, invitation['id'], {'action': 'accept'})
        self.assertEqual(self.db.one('SELECT COUNT(*) AS n FROM jobs')['n'], 1)

    def test_friendly_request_validates_and_concurrent_requests_create_one_pending_invite(self):
        for target in (self.a['id'], self.admin['id'], True, 2**70):
            with self.assertRaises(APIError):
                self.service.create_friendly(self.a, {'team_id': target})
        with self.db.transaction() as con:
            con.execute('UPDATE users SET active=0 WHERE id=?', (self.b['id'],))
        with self.assertRaises(APIError):
            self.service.create_friendly(self.a, {'team_id': self.b['id']})
        with self.db.transaction() as con:
            con.execute('UPDATE users SET active=1,active_submission_id=NULL WHERE id=?', (self.b['id'],))
        with self.assertRaises(APIError):
            self.service.create_friendly(self.a, {'team_id': self.b['id']})
        self.submit(self.b)
        def request(_):
            try:
                self.service.create_friendly(self.a, {'team_id': self.b['id']})
                return 201
            except APIError as error:
                return error.status
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(request, range(8)))
        self.assertEqual(results.count(201), 1)
        self.assertEqual(results.count(409), 7)
        self.assertEqual(self.db.one('SELECT COUNT(*) AS n FROM jobs')['n'], 0)
        iid = self.db.one('SELECT id FROM invitations')['id']
        for _ in range(10):
            self.service.create_practice(self.b, {'bot': 'random'})
        with self.assertRaises(APIError) as error:
            self.service.respond(self.b, iid, {'action': 'accept'})
        self.assertEqual(error.exception.status, 429)
        self.assertEqual(self.db.one('SELECT status FROM invitations WHERE id=?', (iid,))['status'], 'pending')
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM jobs WHERE kind='friendly'")['n'], 0)

    def test_reset_friendly_counts_keeps_history_invitations_and_other_results(self):
        iid = self.service.create_friendly(self.a, {'team_id': self.b['id']})['id']
        jid = self.service.respond(self.b, iid, {'action': 'accept'})['job_id']
        bot = self.service.create_practice(self.a, {'bot': 'random'})['id']
        tid = self.tournament()
        pending = self.service.invite(self.c, {'team_id': self.b['id']})['id']
        with self.db.transaction() as con:
            con.execute("UPDATE jobs SET status='completed',winner=0,score0=10,score1=5 WHERE id IN (?,?)", (jid, bot))
            con.execute("INSERT INTO jobs(kind,status,p0,p1,tournament_id,winner,score0,score1,seed,created) VALUES('tournament','completed',?,?,?,0,10,5,1,0)", (self.a['id'],self.b['id'],tid))
        tables = ('users','submissions','jobs','invitations','tournaments','entries')
        counts = {t:self.db.one(f'SELECT COUNT(*) AS n FROM {t}')["n"] for t in tables}
        frozen = self.db.one('SELECT * FROM jobs WHERE id=?', (jid,))
        tournament_before = self.service.scoreboard(self.a,tid)
        before = self.service.dashboard(self.a)['stats']['played']
        with self.assertRaises(APIError):
            self.service.reset_friendly_counts(self.a)
        cutoff = self.service.reset_friendly_counts(self.admin)['after_job_id']
        restarted = type(self.service)(Database(self.temp.name))
        self.assertTrue(all(r['played']==0 for r in restarted.scoreboard(self.a)['items']))
        self.assertEqual(restarted.dashboard(self.a)['stats']['played'], before-1)
        self.assertEqual(restarted.scoreboard(self.a,tid), tournament_before)
        self.assertEqual(self.db.one('SELECT * FROM jobs WHERE id=?', (jid,)), frozen)
        self.assertEqual({t:self.db.one(f'SELECT COUNT(*) AS n FROM {t}')["n"] for t in tables}, counts)
        self.assertEqual(self.db.one('SELECT status FROM invitations WHERE id=?', (pending,))['status'], 'pending')
        new_job = self.service.respond(self.b, pending, {'action':'accept'})['job_id']
        self.assertGreater(new_job, cutoff)
        with self.db.transaction() as con:
            con.execute("UPDATE jobs SET status='completed',winner=0,score0=10,score1=5 WHERE id=?", (new_job,))
        self.assertEqual(sum(r['played'] for r in restarted.scoreboard(self.a)['items']), 2)

    def test_scoreboards_exclude_unfinished_bots_and_other_tournaments(self):
        tid = self.tournament()
        other = self.tournament()
        with self.db.transaction() as con:
            # Synthetic result setup exercises ranking, not judge throughput.
            for kind, status, tournament, winner in [('friendly', 'completed', None, 0),
                    ('friendly', 'completed', None, None), ('friendly', 'failed', None, 1),
                    ('bot', 'completed', None, 1), ('tournament', 'completed', tid, 1),
                    ('tournament', 'completed', other, 0)]:
                con.execute('INSERT INTO jobs(kind,status,p0,p1,winner,score0,score1,tournament_id,seed,created) VALUES(?,?,?,?,?,10,20,?,1,0)',
                            (kind, status, self.a['id'], self.b['id'], winner, tournament))
        friendly = self.service.scoreboard(self.c)['items']
        self.assertEqual(friendly[0]['id'], self.a['id'])
        self.assertEqual((friendly[0]['wins'], friendly[0]['draws'], friendly[0]['played']), (1, 1, 2))
        tournament = self.service.scoreboard(self.a, tid)['items']
        self.assertEqual(tournament[0]['id'], self.b['id'])
        self.assertEqual(tournament[0]['wins'], 1)
        with self.assertRaises(APIError):
            self.service.scoreboard(self.a, 99999)

    def test_win_ratio_ranking_qualifies_at_three_and_counts_draws(self):
        idle = self.make_user('idle')
        sink = self.make_user('sink')
        self.submit(idle)
        self.submit(sink)
        tid = self.tournament([self.a['id'],self.b['id'],self.c['id'],idle['id'],sink['id']])
        def add(con, team, winner, tournament=None):
            con.execute("INSERT INTO jobs(kind,status,p0,p1,winner,score0,score1,tournament_id,seed,created) VALUES(?,'completed',?,?,?,10,10,?,1,0)",
                        ('tournament' if tournament else 'friendly',team['id'],sink['id'],winner,tournament))
        for scope in (None, tid):
            with self.db.transaction() as con:
                for team, results in [(self.a,[0,0,None]),(self.b,[0,0,0,1,1,1]),(self.c,[0,0])]:
                    for winner in results:
                        add(con,team,winner,scope)
            rows = self.service.scoreboard(self.a,scope)['items']
            ranked = [r for r in rows if r['eligible']]
            provisional = {r['id']:r for r in rows if not r['eligible']}
            self.assertEqual([r['id'] for r in ranked], [self.a['id'],self.b['id'],sink['id']])
            self.assertEqual([r['rank'] for r in ranked], [1,2,3])
            self.assertAlmostEqual(ranked[0]['win_ratio'],2/3)
            self.assertEqual(ranked[1]['win_ratio'],.5)
            self.assertEqual(provisional[self.c['id']]['win_ratio'],1)
            self.assertIsNone(provisional[self.c['id']]['rank'])
            self.assertIsNone(provisional[idle['id']]['win_ratio'])
            self.assertIsNone(provisional[idle['id']]['rank'])
            with self.db.transaction() as con:
                add(con,self.c,1,scope)
            promoted = next(r for r in self.service.scoreboard(self.a,scope)['items'] if r['id']==self.c['id'])
            self.assertTrue(promoted['eligible'])
            self.assertEqual(promoted['rank'],2)
            self.assertAlmostEqual(promoted['win_ratio'],2/3)
