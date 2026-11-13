import json
from pathlib import Path
import zipfile
import threading
import tempfile
import time
from tests import test_service as fixtures
from arena.service import APIError
from arena.storage import Database
from arena.worker import run_worker


class AdminTests(fixtures.Fixture):
    def test_archive_team_names_and_mixed_language_contents(self):
        self.service.submit(self.a,{'source':'print("alpha")','filename':'ربات.py','language':'python'})
        self.submit(self.c,'print("gamma")')
        cpp='#include <iostream>\nint main(){std::cout << 0 << std::endl;}\n'
        cpp_id=self.service.submit(self.b,{'source':cpp,'filename':'solution.cpp','language':'cpp'})['id']
        self.service.update_team(self.admin,self.a['id'],{'name':'تیم آفتاب'})
        self.service.update_team(self.admin,self.b['id'],{'name':'تیم آفتاب'})
        self.service.update_team(self.admin,self.c['id'],{'name':'../تیم\\آزمایش\u202e'})
        for scope in ('all','final'):
            with self.service.submission_archive(self.admin,scope) as stream, zipfile.ZipFile(stream) as bundle:
                manifest=json.loads(bundle.read('manifest.json'))
                folders={r['team_id']:Path(r['file']).parts[0] for r in manifest}
                self.assertEqual(folders[self.a['id']],f"تیم آفتاب--team-{self.a['id']}")
                self.assertEqual(folders[self.b['id']],f"تیم آفتاب--team-{self.b['id']}")
                self.assertNotEqual(folders[self.a['id']],folders[self.b['id']])
                entry=next(r for r in manifest if r['submission_id']==cpp_id)
                self.assertEqual(Path(entry['file']).name,f'solution--submission-{cpp_id}.cpp')
                self.assertTrue(bundle.getinfo(entry['file']).flag_bits & 0x800)
                self.assertEqual(bundle.read(entry['file']).decode(),cpp)
                self.assertNotIn('bot',bundle.namelist())
                with tempfile.TemporaryDirectory() as directory:
                    bundle.extractall(directory)
                    for row in manifest:
                        path=Path(directory,row['file'])
                        self.assertTrue(path.resolve().is_relative_to(Path(directory).resolve()))
                        self.assertNotIn('\\',row['file']);self.assertNotIn('\u202e',row['file'])
                        self.assertEqual(len(Path(row['file']).parts),2)
                        source=self.db.one('SELECT path,language FROM submissions WHERE id=?',(row['submission_id'],))
                        extension='py' if source['language']=='python' else 'cpp'
                        self.assertEqual(path.read_bytes(),(Path(source['path']).parent/f'source.{extension}').read_bytes())

    def test_submission_archives_include_history_or_selected_finals(self):
        old = self.db.latest(self.a['id'])['id']
        newer = self.submit(self.a, 'print(1)')['id']
        local = self.service.submit(self.a, {'source':'print(2)', 'filename':'local.py', 'language':'python'}, kind='local')['id']
        self.service.activate_submission(self.a, old, {})
        with self.db.transaction() as con:
            con.execute('UPDATE users SET active=0 WHERE id=?', (self.a['id'],))
            con.execute("UPDATE submissions SET filename='../../same.py' WHERE user_id=?", (self.a['id'],))
        for scope, expected in [('all', {old, newer}), ('final', {old})]:
            with self.service.submission_archive(self.admin, scope) as stream, zipfile.ZipFile(stream) as bundle:
                manifest = json.loads(bundle.read('manifest.json'))
                own = [r for r in manifest if r['team_id'] == self.a['id']]
                self.assertEqual({r['submission_id'] for r in own}, expected)
                self.assertNotIn(local, {r['submission_id'] for r in manifest})
                self.assertEqual(len(bundle.namelist()), len(manifest)+1)
                self.assertTrue(all('..' not in name and not name.startswith('/') for name in bundle.namelist()))
                for row in manifest:
                    extension = 'py' if row['language'] == 'python' else 'cpp'
                    source = self.db.one('SELECT path FROM submissions WHERE id=?', (row['submission_id'],))
                    self.assertEqual(bundle.read(row['file']), (Path(source['path']).parent/f'source.{extension}').read_bytes())
        for scope in ('all', 'final'):
            with self.assertRaises(APIError) as error:self.service.submission_archive(self.a, scope)
            self.assertEqual(error.exception.status, 403)
        with self.assertRaises(APIError):self.service.submission_archive(self.admin, 'invalid')

    def test_empty_submission_archive(self):
        with self.db.transaction() as con:
            con.execute('UPDATE users SET active_submission_id=NULL')
        with self.service.submission_archive(self.admin, 'final') as stream, zipfile.ZipFile(stream) as bundle:
            self.assertEqual(bundle.namelist(), ['manifest.json'])
            self.assertEqual(json.loads(bundle.read('manifest.json')), [])

    def test_overview_is_admin_only_and_excludes_private_material(self):
        with self.assertRaises(APIError) as err:self.service.admin_overview(self.a)
        self.assertEqual(err.exception.status,403)
        overview=self.service.admin_overview(self.admin)
        self.assertEqual(overview['counts'],{'teams':3,'active':3,'ready':3})
        encoded=json.dumps(overview)
        self.assertNotIn('password',encoded);self.assertNotIn(self.temp.name,encoded)
        self.assertNotIn('source',encoded)

    def test_worker_controls_validate_role_and_types(self):
        with self.assertRaises(APIError):self.service.configure_worker(self.a,{'paused':True})
        for body in ({'slots':True},{'slots':0},{'slots':129},{'slots':'6'},{'paused':'false'},{'command':'ls'},{}):
            with self.subTest(body=body),self.assertRaises(APIError):self.service.configure_worker(self.admin,body)
        self.service.configure_worker(self.admin,{'slots':3,'paused':True})
        self.service.configure_worker(self.admin,{'slots':2})
        reopened=Database(self.temp.name)
        settings=json.loads(reopened.one("SELECT value FROM meta WHERE key='worker_settings'")['value'])
        self.assertEqual(settings,{'slots':2,'paused':True})

    def test_rename_validates_and_keeps_sessions(self):
        token,_=self.service.login({'username':'alpha','password':'TestPassword123!'},'ip')
        self.service.update_team(self.admin,self.a['id'],{'name':'نام تازه'})
        self.assertEqual(self.service.authenticate(token)['name'],'نام تازه')
        for name in ('',None,False,'a'*61):
            with self.assertRaises(APIError):self.service.update_team(self.admin,self.a['id'],{'name':name})

    def test_retry_only_failed_friendly_and_preserves_input(self):
        jid=self.service.create_practice(self.a,{'bot':'greedy'})['id']
        original=self.db.one('SELECT * FROM jobs WHERE id=?',(jid,))
        with self.assertRaises(APIError):self.service.retry_job(self.admin,jid,{'action':'retry'})
        with self.db.transaction() as con:con.execute("UPDATE jobs SET status='failed',error='infrastructure',finished=1 WHERE id=?",(jid,))
        with self.assertRaises(APIError):self.service.retry_job(self.a,jid,{'action':'retry'})
        self.service.retry_job(self.admin,jid,{'action':'retry'})
        retried=self.db.one('SELECT * FROM jobs WHERE id=?',(jid,))
        self.assertEqual(retried['status'],'queued');self.assertIsNone(retried['error']);self.assertIsNone(retried['finished'])
        for key in ('seed','s0','s1','p0','p1'):self.assertEqual(retried[key],original[key])

    def test_protocol_losses_and_tournament_failures_cannot_use_friendly_retry(self):
        jid=self.service.create_practice(self.a,{'bot':'greedy'})['id']
        with self.db.transaction() as con:con.execute("UPDATE jobs SET status='completed',reason='turn_timeout',winner=1 WHERE id=?",(jid,))
        with self.assertRaises(APIError):self.service.retry_job(self.admin,jid,{'action':'retry'})
        tid=self.tournament()
        with self.db.transaction() as con:con.execute("UPDATE jobs SET status='failed',tournament_id=? WHERE id=?",(tid,jid))
        with self.assertRaises(APIError):self.service.retry_job(self.admin,jid,{'action':'retry'})

    def test_queue_status_filter(self):
        first=self.service.create_practice(self.a,{'bot':'greedy'})['id']
        self.service.create_practice(self.b,{'bot':'random'})
        with self.db.transaction() as con:con.execute("UPDATE jobs SET status='failed' WHERE id=?",(first,))
        jobs=self.service.matches(self.admin,status='failed')
        self.assertEqual(jobs['total'],1);self.assertEqual(jobs['items'][0]['id'],first)
        with self.assertRaises(APIError):self.service.matches(self.admin,status='unknown')

    def test_worker_pause_resume_and_live_capacity(self):
        self.service.configure_worker(self.admin,{'paused':True,'slots':1})
        source='''import sys,time
r=sys.stdin.readline()
for h in sys.stdin:
 m=[sys.stdin.readline() for _ in range(6)]
 if h.strip()=='YOURTURN':time.sleep(.025);print(0,flush=True)
 else:sys.stdin.readline()
'''
        self.submit(self.a,source)
        first=self.service.create_practice(self.a,{'bot':'greedy'})['id']
        second=self.service.create_practice(self.a,{'bot':'greedy'})['id']
        stop=threading.Event();worker=threading.Thread(target=run_worker,args=(self.db,6,stop));worker.start()
        def wait_for(predicate):
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                if predicate():return
                time.sleep(.02)
            self.fail('Worker state did not update')
        try:
            wait_for(lambda:self.db.one("SELECT value FROM meta WHERE key='worker_heartbeat'"))
            self.assertEqual(self.db.one('SELECT status FROM jobs WHERE id=?',(first,))['status'],'queued')
            self.service.configure_worker(self.admin,{'paused':False})
            wait_for(lambda:self.db.one('SELECT status FROM jobs WHERE id=?',(first,))['status']=='running')
            self.service.configure_worker(self.admin,{'paused':True,'slots':2})
            wait_for(lambda:json.loads(self.db.one("SELECT value FROM meta WHERE key='worker_heartbeat'")['value'])['paused'])
            wait_for(lambda:self.db.one('SELECT status FROM jobs WHERE id=?',(first,))['status']=='completed')
            self.assertEqual(self.db.one('SELECT status FROM jobs WHERE id=?',(second,))['status'],'queued')
            self.service.configure_worker(self.admin,{'paused':False})
            wait_for(lambda:self.db.one('SELECT status FROM jobs WHERE id=?',(second,))['status']=='completed')
            heartbeat=json.loads(self.db.one("SELECT value FROM meta WHERE key='worker_heartbeat'")['value'])
            self.assertEqual(heartbeat['slots'],2)
        finally:stop.set();worker.join(timeout=15)
