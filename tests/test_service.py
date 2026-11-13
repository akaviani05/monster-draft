from concurrent.futures import ThreadPoolExecutor
import hashlib
import http.client
import json
import re
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from arena.storage import Database, ROOT, password_valid
from arena.service import APIError, Service
from arena.scheduling import claim, finish_tournaments, standings, start_due
from arena.server import ArenaHTTPServer
from arena.worker import run_worker


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.db=Database(self.temp.name);self.service=Service(self.db)
        self.admin=self.make_user('admin','admin');self.a=self.make_user('alpha');self.b=self.make_user('beta');self.c=self.make_user('gamma')
        for user in (self.a,self.b,self.c):self.submit(user)

    def tearDown(self):self.temp.cleanup()

    def make_user(self,name,role='team'):
        uid=self.db.add_user(name,name,'TestPassword123!',role)
        return {'id':uid,'name':name,'username':name,'role':role}

    def submit(self,user,source=None):
        return self.service.submit(user,{'source':source or (ROOT/'bots/greedy.py').read_text(),'filename':'bot.py','language':'python'})

    def tournament(self,teams=None,start=None,paired=False):
        return self.service.create_tournament(self.admin,{'name':'جام آزمایشی','teams':teams or [self.a['id'],self.b['id'],self.c['id']],'starts_at':start or time.time(),'paired':paired})['id']


class ServiceTests(Fixture):
    def test_admin_password_only_login_supports_custom_username(self):
        with self.db.transaction() as con:con.execute("UPDATE users SET username='organizer' WHERE id=?",(self.admin['id'],))
        token,response=self.service.admin_login({'password':'TestPassword123!'},'admin-test')
        self.assertEqual(response['user']['role'],'admin')
        self.assertEqual(response['user']['username'],'organizer')
        self.assertEqual(self.service.authenticate(token)['id'],self.admin['id'])

    def test_admin_login_ignores_student_username_and_rejects_student_password(self):
        from arena.storage import password_hash
        with self.db.transaction() as con:con.execute('UPDATE users SET password=? WHERE id=?',(password_hash('UniqueAdminPassword!'),self.admin['id']))
        with self.assertRaises(APIError) as err:
            self.service.admin_login({'username':'alpha','password':'TestPassword123!'},'admin-test')
        self.assertEqual(err.exception.status,401)
        self.assertEqual(self.db.one('SELECT COUNT(*) AS n FROM sessions')['n'],0)
        with self.assertRaises(APIError):self.service.login({'username':'alpha','password':'TestPassword123!'},'admin-test',required_role='admin')

    def test_admin_login_rejects_disabled_or_absent_administrator(self):
        with self.db.transaction() as con:con.execute('UPDATE users SET active=0 WHERE id=?',(self.admin['id'],))
        with self.assertRaises(APIError):self.service.admin_login({'password':'TestPassword123!'},'admin-test')
        with self.db.transaction() as con:con.execute("UPDATE users SET role='team',active=1 WHERE id=?",(self.admin['id'],))
        with self.assertRaises(APIError):self.service.admin_login({'password':'TestPassword123!'},'admin-test')
        self.assertEqual(self.db.one('SELECT COUNT(*) AS n FROM sessions')['n'],0)

    def test_admin_password_attempts_are_throttled(self):
        for _ in range(15):
            with self.assertRaises(APIError):self.service.admin_login({'password':'wrong'},'admin-test')
        with self.assertRaises(APIError) as err:self.service.admin_login({'password':'TestPassword123!'},'admin-test')
        self.assertEqual(err.exception.status,429)

    def test_password_salted_and_sessions_hashed(self):
        a=self.db.one('SELECT password FROM users WHERE id=?',(self.a['id'],))['password']
        b=self.db.one('SELECT password FROM users WHERE id=?',(self.b['id'],))['password']
        self.assertNotEqual(a,b);self.assertTrue(password_valid('TestPassword123!',a));self.assertFalse(password_valid('wrong',a))
        token,response=self.service.login({'username':'alpha','password':'TestPassword123!'},'test')
        self.assertEqual(self.service.authenticate(token)['id'],self.a['id'])
        self.assertIsNone(self.db.one('SELECT * FROM sessions WHERE token=?',(token,)))
        self.assertEqual(self.db.one('SELECT * FROM sessions WHERE token=?',(hashlib.sha256(token.encode()).hexdigest(),))['csrf'],response['csrf'])

    def test_login_throttling(self):
        for _ in range(15):
            with self.assertRaises(APIError):self.service.login({'username':'alpha','password':'bad'},'same-ip')
        with self.assertRaises(APIError) as error:self.service.login({'username':'alpha','password':'TestPassword123!'},'same-ip')
        self.assertEqual(error.exception.status,429)

    def test_invalid_login(self):
        for username in ('alpha','unknown'):
            with self.assertRaises(APIError) as error:self.service.login({'username':username,'password':'bad'},username)
            self.assertEqual(error.exception.status,401)

    def test_admin_only_and_unique_users(self):
        with self.assertRaises(APIError):self.service.create_team(self.a,{'username':'new','name':'new','password':'12345678'})
        self.service.create_team(self.admin,{'username':'new','name':'<script>alert(1)</script>','password':'12345678'})
        with self.assertRaises(APIError) as error:self.service.create_team(self.admin,{'username':'new','name':'new','password':'12345678'})
        self.assertEqual(error.exception.status,409)

    def test_team_password_whitespace_is_not_silently_changed(self):
        self.service.create_team(self.admin,{'username':'spaces','name':'Spaces','password':'  Fixture password  '})
        _,session=self.service.login({'username':'spaces','password':'  Fixture password  '},'space-test')
        self.assertEqual(session['user']['username'],'spaces')

    def test_surrogate_source_is_a_clean_validation_error(self):
        with self.assertRaises(APIError) as err:self.service.submit(self.a,{'source':'\ud800'})
        self.assertEqual(err.exception.status,400)

    def test_password_reset_revokes_sessions(self):
        token,_=self.service.login({'username':'alpha','password':'TestPassword123!'},'ip')
        self.service.update_team(self.admin,self.a['id'],{'password':'NewPassword123!'})
        self.assertIsNone(self.service.authenticate(token))

    def test_inactive_cannot_login(self):
        self.service.update_team(self.admin,self.a['id'],{'active':False})
        with self.assertRaises(APIError):self.service.login({'username':'alpha','password':'TestPassword123!'},'ip')

    def test_submission_immutable_and_no_source_leak(self):
        old=self.db.latest(self.a['id']);new=self.submit(self.a,'print("new version")')
        self.assertNotEqual(new['id'],old['id']);self.assertNotEqual(new['digest'],old['digest'])
        self.assertIn('market',Path(old['path']).read_text())
        data=self.service.dashboard(self.b)
        self.assertNotIn('source',json.dumps(data));self.assertNotIn('password',json.dumps(data));self.assertNotIn(self.temp.name,json.dumps(data))

    def test_submission_validation_and_size(self):
        for body in ({'source':''},{'source':'x'*65537},{'source':'if :'},{'source':'print(1)','language':'sh'}):
            with self.assertRaises(APIError):self.service.submit(self.a,body)

    def test_submission_daily_and_storage_quotas(self):
        with self.db.transaction() as con:
            con.execute('UPDATE submissions SET size_bytes=? WHERE user_id=?',(129*1024**2,self.a['id']))
        with self.assertRaises(APIError) as error:self.submit(self.a)
        self.assertEqual(error.exception.status,429)
        with self.db.transaction() as con:
            row=self.db.latest(self.b['id'],con)
            con.executemany("INSERT INTO submissions(user_id,filename,language,digest,path,kind,created) VALUES(?,'bot.py','python',?,?,'local',?)",[(self.b['id'],row['digest'],row['path'],time.time()-120)]*100)
        with self.assertRaises(APIError) as error:self.submit(self.b)
        self.assertEqual(error.exception.status,429)

    def test_malformed_local_code_and_bot_are_clean_errors(self):
        with self.assertRaises(APIError):self.service.local(self.a,{'codes':['bad','bad']})
        with self.assertRaises(APIError):self.service.create_practice(self.a,{'bot':[]})

    def test_practice_quota_and_frozen_submission(self):
        for _ in range(10):self.service.create_practice(self.a,{'bot':'random'})
        with self.assertRaises(APIError) as error:self.service.create_practice(self.a,{'bot':'random'})
        self.assertEqual(error.exception.status,429)
        job=self.db.one('SELECT * FROM jobs LIMIT 1');self.submit(self.a)
        self.assertNotEqual(job['s0'] or job['s1'],self.db.latest(self.a['id'])['id'])

    def test_minute_rate_limit_with_completed_jobs(self):
        for _ in range(10):
            self.service.create_practice(self.a,{'bot':'greedy'})
            with self.db.transaction() as con:con.execute("UPDATE jobs SET status='completed'")
        with self.assertRaises(APIError):self.service.create_practice(self.a,{'bot':'random'})

    def test_no_daily_game_quota(self):
        with self.db.transaction() as con:
            con.executemany("INSERT INTO jobs(kind,status,owner_id,seed,created) VALUES('bot','completed',?,0,?)",[(self.a['id'],time.time()-120)]*1000)
        for _ in range(10):
            self.service.create_practice(self.a,{'bot':'random'})
        with self.assertRaises(APIError) as error:
            self.service.create_practice(self.a,{'bot':'random'})
        self.assertEqual(error.exception.status,429)
        self.assertEqual(self.db.one('SELECT COUNT(*) AS n FROM jobs WHERE owner_id=?',(self.a['id'],))['n'],1010)

    def test_invitation_limit_is_per_minute(self):
        with self.db.transaction() as con:
            con.executemany("INSERT INTO invitations(sender,recipient,submission_id,status,created,expires) VALUES(?,?,?,'rejected',?,?)",
                [(self.a['id'], self.b['id'], self.db.latest(self.a['id'])['id'], time.time()-120, time.time()+600)]*10)
        for _ in range(10):
            iid=self.service.invite(self.a,{'team_id':self.b['id']})['id']
            self.service.respond(self.b,iid,{'action':'reject'})
        with self.assertRaises(APIError) as error:
            self.service.invite(self.a,{'team_id':self.b['id']})
        self.assertEqual(error.exception.status,429)

    def test_invite_accept_once_concurrently(self):
        iid=self.service.invite(self.a,{'team_id':self.b['id']})['id']
        def accept(_):
            try:return self.service.respond(self.b,iid,{'action':'accept'})
            except APIError as exc:return exc.status
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(accept,range(2)))
        self.assertEqual(sum(isinstance(r,dict) for r in results),1)
        self.assertEqual(self.db.one('SELECT COUNT(*) AS n FROM jobs')['n'],1)

    def test_reject_cancel_expiry_and_authorization(self):
        iid=self.service.invite(self.a,{'team_id':self.b['id']})['id']
        with self.assertRaises(APIError):self.service.respond(self.c,iid,{'action':'accept'})
        with self.assertRaises(APIError):self.service.invite(self.b,{'team_id':self.a['id']})
        self.service.respond(self.b,iid,{'action':'reject'})
        self.assertEqual(self.db.one('SELECT COUNT(*) AS n FROM jobs')['n'],0)
        iid=self.service.invite(self.a,{'team_id':self.b['id']})['id']
        self.service.respond(self.a,iid,{'action':'cancel'})
        iid=self.service.invite(self.a,{'team_id':self.b['id']})['id']
        with self.db.transaction() as con:con.execute('UPDATE invitations SET expires=0 WHERE id=?',(iid,))
        with self.assertRaises(APIError):self.service.respond(self.b,iid,{'action':'accept'})

    def test_local_does_not_replace_official(self):
        old=self.db.latest(self.a['id'])['id'];source=(ROOT/'bots/greedy.py').read_text()
        job=self.service.local(self.a,{'codes':[{'source':source},{'source':source}]})
        self.assertEqual(self.db.latest(self.a['id'])['id'],old)
        self.assertEqual(self.db.one('SELECT kind FROM jobs WHERE id=?',(job['id'],))['kind'],'local')

    def test_replay_access_control(self):
        jid=self.service.create_practice(self.a,{'bot':'random'})['id']
        with self.assertRaises(APIError) as error:self.service.replay(self.b,jid)
        self.assertEqual(error.exception.status,403)
        with self.assertRaises(APIError) as error:self.service.replay(self.a,jid)
        self.assertEqual(error.exception.status,409)


class QueueTests(Fixture):
    def test_top_ten_win_percentage_excludes_lower_ranks_and_counts_draws(self):
        ids=[self.a['id'],self.b['id'],self.c['id']]
        ids += [self.make_user('top-ten-'+str(i))['id'] for i in range(9)]
        tid=self.tournament(teams=ids[:3],start=time.time()+600)
        with self.db.transaction() as con:
            con.executemany('INSERT INTO entries(tournament_id,user_id) VALUES(?,?)',[(tid,uid) for uid in ids[3:]])
            for i,a in enumerate(ids):
                for b in ids[i+1:]:
                    con.execute("INSERT INTO jobs(kind,status,p0,p1,seed,tournament_id,created) VALUES('tournament','completed',?,?,0,?,0)",(a,b,tid))
            for b in (ids[1],ids[10],ids[11]):
                con.execute("INSERT INTO jobs(kind,status,p0,p1,winner,seed,tournament_id,created) VALUES('tournament','completed',?,?,0,0,?,0)",(ids[0],b,tid))
        rows=standings(self.db,tid);by_id={r['id']:r for r in rows}
        self.assertEqual({r['id'] for r in rows if r['rank']<=10},set(ids[:10]))
        self.assertEqual(by_id[ids[0]]['wins'],3)
        self.assertEqual(by_id[ids[0]]['top10_played'],10)
        self.assertAlmostEqual(by_id[ids[0]]['top10_win_ratio'],.1)
        self.assertEqual(by_id[ids[11]]['top10_played'],11)
        self.assertEqual(by_id[ids[11]]['top10_win_ratio'],0)
        empty=self.tournament(start=time.time()+600)
        self.assertTrue(all(r['top10_win_ratio'] is None for r in standings(self.db,empty)))

    def test_multiple_games_per_pair_and_persistence(self):
        from collections import Counter, defaultdict
        for count in (3, 6):
            with self.subTest(games_per_pair=count):
                tid=self.service.create_tournament(self.admin,{'name':'چند بازی','starts_at':time.time(),
                    'teams':[self.a['id'],self.b['id'],self.c['id']], 'games_per_pair':count})['id']
                with patch('arena.scheduling.secrets.randbits', side_effect=range(100,200)):
                    start_due(self.db)
                jobs=self.db.rows('SELECT * FROM jobs WHERE tournament_id=? ORDER BY round,id',(tid,))
                self.assertEqual(len(jobs),3*count)
                pairs=defaultdict(list)
                for job in jobs:pairs[tuple(sorted((job['p0'],job['p1'])))].append(job)
                self.assertEqual(len(pairs),3)
                for pair_jobs in pairs.values():
                    self.assertEqual(len(pair_jobs),count)
                    for index,job in enumerate(pair_jobs):
                        if index%2:
                            prev=pair_jobs[index-1]
                            self.assertEqual((job['p0'],job['p1'],job['seed']), (prev['p1'],prev['p0'],prev['seed']))
                    self.assertEqual(len({j['seed'] for j in pair_jobs}), (count+1)//2)
                starts=Counter(j['p0'] for j in jobs)
                self.assertLessEqual(max(starts.values())-min(starts.values()),1)
                snapshot=[(j['id'],j['s0'],j['s1'],j['seed']) for j in jobs]
                reopened=Database(self.temp.name);start_due(reopened)
                self.assertEqual(reopened.one('SELECT games_per_pair FROM tournaments WHERE id=?',(tid,))['games_per_pair'],count)
                self.assertEqual([(j['id'],j['s0'],j['s1'],j['seed']) for j in reopened.rows('SELECT * FROM jobs WHERE tournament_id=? ORDER BY round,id',(tid,))],snapshot)

    def test_games_per_pair_validation(self):
        for count in (0,-1,101,1.5,True,'6',None):
            with self.subTest(count=count),self.assertRaises(APIError):
                self.service.create_tournament(self.admin,{'name':'bad','starts_at':time.time(),
                    'teams':[self.a['id'],self.b['id']], 'games_per_pair':count})

    def test_legacy_tournament_count_migration(self):
        single=self.tournament(start=time.time()+600)
        paired=self.tournament(paired=True)
        start_due(self.db)
        before=self.db.rows('SELECT id,s0,s1,seed,status FROM jobs ORDER BY id')
        with self.db.transaction() as con:con.execute('ALTER TABLE tournaments DROP COLUMN games_per_pair')
        reopened=Database(self.temp.name)
        self.assertEqual(reopened.one('SELECT games_per_pair FROM tournaments WHERE id=?',(single,))['games_per_pair'],1)
        self.assertEqual(reopened.one('SELECT games_per_pair FROM tournaments WHERE id=?',(paired,))['games_per_pair'],2)
        self.assertEqual(reopened.rows('SELECT id,s0,s1,seed,status FROM jobs ORDER BY id'),before)

    def test_disabled_selected_team_fails_start_instead_of_silently_removing_it(self):
        tid=self.tournament()
        self.service.update_team(self.admin,self.c['id'],{'active':False})
        start_due(self.db)
        self.assertEqual(self.db.one('SELECT status FROM tournaments WHERE id=?',(tid,))['status'],'failed')
        self.assertEqual(self.db.one('SELECT COUNT(*) AS n FROM jobs')['n'],0)

    def test_schedule_future_freeze_and_pairs(self):
        start=time.time()+600;tid=self.tournament(start=start)
        start_due(self.db);self.assertEqual(self.db.one('SELECT COUNT(*) AS n FROM jobs')['n'],0)
        latest=self.submit(self.a)
        with patch('arena.scheduling.time.time',return_value=start+1):start_due(self.db)
        self.submit(self.a)
        self.assertEqual(self.db.one('SELECT submission_id FROM entries WHERE tournament_id=? AND user_id=?',(tid,self.a['id']))['submission_id'],latest['id'])
        self.assertEqual(self.db.one('SELECT COUNT(*) AS n FROM jobs')['n'],3)
        start_due(self.db);self.assertEqual(self.db.one('SELECT COUNT(*) AS n FROM jobs')['n'],3)

    def test_round_barrier(self):
        self.tournament();start_due(self.db)
        job=claim(self.db,'test');self.assertIsNotNone(job)
        self.assertIsNone(claim(self.db,'other'))
        with self.db.transaction() as con:con.execute("UPDATE jobs SET status='completed',score0=10,score1=9,winner=0 WHERE id=?",(job['id'],))
        next_job=claim(self.db,'next');self.assertEqual(next_job['round'],1)

    def test_paired_same_seed_and_swapped_seats(self):
        self.tournament(paired=True);start_due(self.db)
        jobs=self.db.rows('SELECT * FROM jobs ORDER BY id')
        self.assertEqual(len(jobs),6)
        for a,b in zip(jobs[::2],jobs[1::2]):
            self.assertEqual(a['seed'],b['seed']);self.assertEqual(a['p0'],b['p1']);self.assertEqual(a['p1'],b['p0'])

    def test_claim_unique_across_threads(self):
        with self.db.transaction() as con:
            con.executemany("INSERT INTO jobs(kind,seed,created) VALUES('local',?,?)",[(i,time.time()) for i in range(30)])
        with ThreadPoolExecutor(8) as pool:jobs=list(pool.map(lambda i:claim(self.db,str(i)),range(30)))
        self.assertEqual(len({j['id'] for j in jobs}),30)

    def test_missing_code_at_start_fails_cleanly(self):
        tid=self.tournament()
        with self.db.transaction() as con:con.execute("UPDATE submissions SET kind='local'")
        start_due(self.db)
        self.assertEqual(self.db.one('SELECT status FROM tournaments WHERE id=?',(tid,))['status'],'failed')

    def test_admin_cancel_and_start(self):
        tid=self.tournament(start=time.time()+500)
        self.service.tournament_action(self.admin,tid,{'action':'cancel'});start_due(self.db)
        self.assertEqual(self.db.one('SELECT COUNT(*) AS n FROM jobs')['n'],0)
        for user in (self.admin, self.a):
            self.assertNotIn(tid, [t['id'] for t in self.service.dashboard(user)['tournaments']])
        self.assertEqual(self.db.one('SELECT status FROM tournaments WHERE id=?',(tid,))['status'],'cancelled')
        tid=self.tournament(start=time.time()+500)
        self.service.tournament_action(self.admin,tid,{'action':'start'});start_due(self.db)
        self.assertEqual(self.db.one('SELECT status FROM tournaments WHERE id=?',(tid,))['status'],'running')

    def test_worker_runs_and_commits_replay_and_rankings(self):
        self.assert_worker_tournament(1)

    def test_worker_completes_six_games_per_pair(self):
        self.assert_worker_tournament(6)

    def assert_worker_tournament(self, games_per_pair):
        tid=self.service.create_tournament(self.admin,{'name':'worker','starts_at':time.time(),
            'teams':[self.a['id'],self.b['id'],self.c['id']], 'games_per_pair':games_per_pair})['id']
        stop=threading.Event()
        # Simulate a supervisor crash after a claim; startup must recover it.
        start_due(self.db);claim(self.db,'crashed')
        worker=threading.Thread(target=run_worker,args=(self.db,6,stop));worker.start()
        try:
            deadline=time.monotonic()+12
            while time.monotonic()<deadline:
                if self.db.one('SELECT status FROM tournaments WHERE id=?',(tid,))['status']=='completed':break
                time.sleep(.1)
            self.assertEqual(self.db.one('SELECT status FROM tournaments WHERE id=?',(tid,))['status'],'completed')
            rows=standings(self.db,tid)
            self.assertEqual([r['played'] for r in rows],[2*games_per_pair]*3)
            self.assertEqual(sum(r['wins']+r['draws']/2 for r in rows),3*games_per_pair)
            job=self.db.one('SELECT * FROM jobs LIMIT 1')
            log=self.service.replay(self.admin,job['id'])
            self.assertEqual(log['match_id'],job['id']);self.assertNotIn('stderr',log)
        finally:stop.set();worker.join(10)

    def test_infrastructure_failure_not_a_loss_and_retry(self):
        tid=self.tournament();start_due(self.db)
        with self.db.transaction() as con:con.execute("UPDATE jobs SET status='failed'")
        finish_tournaments(self.db)
        self.assertEqual(self.db.one('SELECT status FROM tournaments WHERE id=?',(tid,))['status'],'failed')
        self.assertTrue(all(r['played']==0 for r in standings(self.db,tid)))
        self.service.tournament_action(self.admin,tid,{'action':'retry'})
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM jobs WHERE status='queued'")['n'],3)


class HTTPTests(Fixture):
    def setUp(self):
        super().setUp();self.http=None;self.thread=None
        try:self.http=ArenaHTTPServer(('127.0.0.1',0),self.service)
        except PermissionError:pass
        if self.http:
            self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.cookie='';self.csrf=''

    def tearDown(self):
        if self.http:self.http.shutdown();self.http.server_close();self.thread.join()
        super().tearDown()

    def request(self,path,body=None,csrf=True,extra=None):
        headers={'Cookie':self.cookie,**(extra or {})}
        if body is not None:headers['Content-Type']='application/json'
        if csrf:headers['X-CSRF-Token']=self.csrf
        if not self.http:
            from arena.testing import request
            status,heads,raw=request(self.service,'POST' if body is not None else 'GET',path,json.dumps(body).encode() if body is not None else b'',headers)
            return status,heads,json.loads(raw) if heads.get('Content-Type','').startswith('application/json') else raw
        connection=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=25)
        connection.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,headers)
        response=connection.getresponse();raw=response.read();heads=dict(response.getheaders());status=response.status;connection.close()
        return status,heads,json.loads(raw) if heads.get('Content-Type','').startswith('application/json') else raw

    def login(self,username='alpha'):
        status,headers,body=self.request('/api/login',{'username':username,'password':'TestPassword123!'})
        self.assertEqual(status,200);self.cookie=headers['Set-Cookie'].split(';')[0];self.csrf=body['csrf']

    def test_admin_entry_has_a_separate_password_form(self):
        status,_,body=self.request('/admin')
        self.assertEqual(status,200)
        self.assertIn(b'id="admin-login-form"',body)
        self.assertIn(b'name="password"',body)
        self.assertNotIn(b'name="username"',body)
        self.assertIn(b'data-login-mode="admin"',body)

    def test_admin_password_endpoint_creates_an_admin_session(self):
        status,headers,body=self.request('/api/admin/login',{'password':'wrong'})
        self.assertEqual(status,401);self.assertNotIn('Set-Cookie',headers)
        status,headers,body=self.request('/api/admin/login',{'password':'TestPassword123!'})
        self.assertEqual(status,200);self.assertEqual(body['user']['role'],'admin')
        self.cookie=headers['Set-Cookie'].split(';')[0];self.csrf=body['csrf']
        self.assertEqual(self.request('/api/admin/overview')[0],200)

    def test_admin_submission_zip_permissions_and_response(self):
        import io
        import zipfile
        path='/api/admin/submissions.zip?scope=final'
        self.assertEqual(self.request(path)[0],401)
        self.login()
        self.assertEqual(self.request(path)[0],403)
        status,headers,body=self.request('/api/admin/login',{'password':'TestPassword123!'})
        self.cookie=headers['Set-Cookie'].split(';')[0]
        for scope in ('all','final'):
            status,headers,body=self.request('/api/admin/submissions.zip?scope='+scope)
            self.assertEqual(status,200)
            self.assertEqual(headers['Content-Type'],'application/zip')
            self.assertEqual(headers['Cache-Control'],'no-store')
            self.assertIn(f'submissions-{scope}.zip',headers['Content-Disposition'])
            self.assertEqual(int(headers['Content-Length']),len(body))
            with zipfile.ZipFile(io.BytesIO(body)) as bundle:
                self.assertEqual(len(json.loads(bundle.read('manifest.json'))),3)
        self.assertEqual(self.request('/api/admin/submissions.zip?scope=bad')[0],400)
        self.assertEqual(self.request(path,extra={'Origin':'https://evil.invalid'})[0],403)

    def test_admin_password_endpoint_rejects_cross_site_login(self):
        status,_,_=self.request('/api/admin/login',{'password':'TestPassword123!'},extra={'Origin':'https://evil.invalid'})
        self.assertEqual(status,403)
        self.assertEqual(self.db.one('SELECT COUNT(*) AS n FROM sessions')['n'],0)

    def test_static_security_headers_and_traversal(self):
        for path in ('/','/guide','/visualizer','/assets/style.css'):
            status,headers,body=self.request(path);self.assertEqual(status,200)
            self.assertIn("script-src 'self'",headers['Content-Security-Policy']);self.assertEqual(headers['X-Content-Type-Options'],'nosniff')
        self.assertEqual(self.request('/../arena/storage.py')[0],404)

    def test_html_versions_scripts_and_styles_from_content_and_revalidates_them(self):
        for path in ('/', '/admin', '/guide', '/visualizer'):
            status, headers, body = self.request(path)
            self.assertEqual(status, 200)
            self.assertEqual(headers['Cache-Control'], 'no-cache')
            links = re.findall(rb'(?:src|href)=["\']([^"\']+\.(?:js|css)\?v=[0-9a-f]{16})["\']', body)
            self.assertTrue(links, path)
            for link in links:
                url = link.decode()
                if not url.startswith('/'):
                    url = '/' + url
                status, asset_headers, _ = self.request(url)
                self.assertEqual(status, 200)
                self.assertEqual(asset_headers['Cache-Control'], 'no-cache')
        self.assertEqual(self.request('/assets/logo.svg')[1]['Cache-Control'], 'public, max-age=3600')

    def test_normal_html_reload_gets_new_asset_url_after_file_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'assets').mkdir()
            script = root/'assets/app.js'
            script.write_text('window.release = 1;')
            (root/'index.html').write_text('<script src="/assets/app.js?v=old" defer></script>')
            with patch('arena.server.WEB', root):
                first = self.request('/')[2]
                script.write_text('window.release = 2;')
                second = self.request('/')[2]
                self.assertNotEqual(first, second)
                self.assertNotIn(b'v=old', second)
                version = hashlib.sha256(script.read_bytes()).hexdigest()[:16].encode()
                self.assertIn(b'/assets/app.js?v='+version, second)

    def test_auth_csrf_and_origin(self):
        self.assertEqual(self.request('/api/dashboard')[0],401);self.login()
        self.assertEqual(self.request('/api/practice',{'bot':'random'},csrf=False)[0],403)
        self.assertEqual(self.request('/api/practice',{'bot':'random'},extra={'Origin':'https://evil.invalid'})[0],403)
        self.assertEqual(self.request('/api/dashboard')[0],200)
        self.assertEqual(self.request('/api/practice',{'bot':'random'})[0],201)
        self.assertEqual(self.request('/api/admin/teams',{'name':'bad','username':'bad','password':'12345678'})[0],403)

    def test_source_idor_and_match_idor(self):
        self.login('beta');sid=self.db.latest(self.a['id'])['id']
        self.assertEqual(self.request('/api/submissions/'+str(sid))[0],404)
        jid=self.service.create_practice(self.a,{'bot':'random'})['id']
        self.assertEqual(self.request(f'/api/matches/{jid}/replay')[0],403)
        self.assertEqual(self.request(f'/api/matches/{jid}')[0],403)

    def test_logout_and_cookie_flags(self):
        self.login();self.assertEqual(self.request('/api/logout',{})[0],200)
        self.assertEqual(self.request('/api/dashboard')[0],401)

    def test_http_invite_roundtrip(self):
        self.login('alpha');status,_,body=self.request('/api/invitations',{'team_id':self.b['id']});self.assertEqual(status,201)
        self.login('beta');status,_,accepted=self.request('/api/invitations/'+str(body['id']),{'action':'accept'})
        self.assertEqual(status,200);self.assertIsNotNone(accepted['job_id'])

    def test_proxy_header_is_ignored_unless_peer_is_trusted(self):
        with patch.dict('os.environ',{'ARENA_TRUSTED_PROXIES':''}):
            status,_,_=self.request('/api/login',{'username':'alpha','password':'bad'},extra={'X-Real-IP':'8.8.8.8'})
        self.assertEqual(status,401)
        self.assertTrue(self.db.one("SELECT 1 FROM login_attempts WHERE key='ip:127.0.0.1'"))
        with patch.dict('os.environ',{'ARENA_TRUSTED_PROXIES':'127.0.0.1'}):
            status,_,_=self.request('/api/login',{'username':'alpha','password':'bad'},extra={'X-Real-IP':'192.0.2.5'})
            self.assertEqual(status,401)
            self.assertTrue(self.db.one("SELECT 1 FROM login_attempts WHERE key='ip:192.0.2.5'"))
            status,_,_=self.request('/api/login',{'username':'alpha','password':'bad'},extra={'X-Real-IP':'fake, 192.0.2.5'})
            self.assertEqual(status,403)

    def test_admin_pages_and_worker_api_permissions(self):
        self.assertEqual(self.request('/admin')[0],200)
        self.assertEqual(self.request('/api/admin/overview')[0],401)
        self.login('alpha')
        for path in ('/api/admin/overview','/api/admin/queue'):
            self.assertEqual(self.request(path)[0],403)
        self.assertEqual(self.request('/api/admin/worker',{'slots':2})[0],403)
        self.login('admin')
        self.assertEqual(self.request('/api/admin/worker',{'paused':True},csrf=False)[0],403)
        self.assertEqual(self.request('/api/admin/worker',{'slots':2,'paused':True})[0],201)
        status,_,body=self.request('/api/admin/overview')
        self.assertEqual(status,200);self.assertEqual(body['settings'],{'slots':2,'paused':True})
        self.assertEqual(self.request('/api/admin/queue?status=unknown')[0],400)

    def test_team_can_select_own_final_submission_over_http(self):
        old=self.db.latest(self.a['id']);self.submit(self.a);self.login('alpha')
        self.assertEqual(self.request('/api/submissions')[0],200)
        self.assertEqual(self.request(f"/api/submissions/{old['id']}/activate",{})[0],200)
        self.assertEqual(self.request('/api/dashboard')[2]['active_submission_id'],old['id'])
        self.assertEqual(self.request(f"/api/submissions/{self.db.latest(self.b['id'])['id']}/activate",{})[0],404)

    def test_http_rejects_invalid_unicode_in_all_json_fields(self):
        self.login('admin')
        for path, body in (
            ('/api/login', {'username':'alpha','password':'bad\ud800password'}),
            ('/api/admin/teams', {'username':'unicode-team','name':'bad\ud800name','password':'FixtureOnly123!'}),
            (f"/api/admin/teams/{self.a['id']}", {'password':'bad\ud800password'}),
            ('/api/submissions', {'source':'print(0)','filename':'bad\ud800.py'}),
            ('/api/local', {'codes':[{'source':'print(0)','filename':'bad\ud800.py'},{'source':'print(0)'}]}),
        ):
            with self.subTest(path=path):
                status,_,data=self.request(path,body)
                self.assertEqual(status,400);self.assertIsInstance(data['error'],str)
        self.assertEqual(self.request('/api/admin/overview')[0],200)

    def test_http_rejects_non_ascii_csrf_without_mutating(self):
        self.login()
        self.assertEqual(self.request('/api/practice',{'bot':'random'},csrf=False,extra={'X-CSRF-Token':'forged-é'})[0],403)
        self.assertEqual(self.db.one('SELECT COUNT(*) n FROM jobs')['n'],0)

    def test_http_bounds_resource_ids_before_sqlite_binding(self):
        self.login('admin');huge='9'*40
        for path in ('/api/submissions/','/api/matches/','/api/tournaments/'):
            with self.subTest(path=path):self.assertEqual(self.request(path+huge)[0],404)
        self.assertEqual(self.request('/api/matches/'+huge+'/replay')[0],404)
        for path in ('/api/admin/teams/','/api/admin/jobs/','/api/admin/tournaments/','/api/invitations/'):
            with self.subTest(path=path):self.assertEqual(self.request(path+huge,{'action':'retry'})[0],404)
        self.assertEqual(self.request('/api/submissions/'+huge+'/activate',{})[0],404)
        self.assertEqual(self.request('/api/matches?tournament='+huge)[0],400)
        self.assertEqual(self.request('/api/invitations',{'team_id':10**40})[0],400)
        self.assertEqual(self.request('/api/admin/tournaments',{'name':'bounds','starts_at':time.time()+600,'teams':[self.a['id'],10**40]})[0],400)
        self.login('alpha');self.assertEqual(self.request('/api/admin/teams/'+huge,{'active':False})[0],403)
