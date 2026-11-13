import sqlite3
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tests import test_service as fixtures
from arena.storage import Database, SCHEMA
from arena.service import APIError
from arena.scheduling import start_due


class SubmissionSelectionTests(fixtures.Fixture):
    def test_new_upload_selected_and_previous_version_can_be_restored(self):
        old=self.db.latest(self.a['id']);new=self.submit(self.a)
        self.assertEqual(self.db.active_submission(self.a['id'])['id'],new['id'])
        job=self.service.create_practice(self.a,{'bot':'greedy'})['id']
        self.service.activate_submission(self.a,old['id'],{})
        self.assertEqual(self.db.active_submission(self.a['id'])['id'],old['id'])
        frozen=self.db.one('SELECT * FROM jobs WHERE id=?',(job,))
        self.assertEqual(frozen['s0'] or frozen['s1'],new['id'])
        next_job=self.service.create_practice(self.a,{'bot':'greedy'})['id']
        job=self.db.one('SELECT * FROM jobs WHERE id=?',(next_job,))
        self.assertEqual(job['s0'] or job['s1'],old['id'])
        reopened=Database(self.temp.name)
        self.assertEqual(reopened.active_submission(self.a['id'])['id'],old['id'])

    def test_cannot_select_another_teams_or_local_code(self):
        with self.assertRaises(APIError):self.service.activate_submission(self.a,self.db.latest(self.b['id'])['id'],{})
        local=self.service.submit(self.a,{'source':'print(0)'},kind='local')
        with self.assertRaises(APIError):self.service.activate_submission(self.a,local['id'],{})

    def test_tournament_freezes_selected_version_and_admin_sees_it(self):
        old=self.db.latest(self.a['id']);self.submit(self.a)
        tid=self.tournament();self.service.activate_submission(self.a,old['id'],{});start_due(self.db)
        self.assertEqual(self.db.one('SELECT submission_id FROM entries WHERE user_id=? AND tournament_id=?',(self.a['id'],tid))['submission_id'],old['id'])
        row=next(t for t in self.service.admin_overview(self.admin)['teams'] if t['id']==self.a['id'])
        self.assertEqual(row['submission_id'],old['id'])

    def test_history_pagination_preserves_access_to_older_versions(self):
        old=self.db.latest(self.a['id'])
        with self.db.transaction() as con:
            con.executemany("INSERT INTO submissions(user_id,filename,language,digest,path,created) VALUES(?,'history.py','python',?,?,?)",[(self.a['id'],old['digest'],old['path'],time.time())]*30)
        page1=self.service.list_submissions(self.a,1);page2=self.service.list_submissions(self.a,2)
        self.assertEqual(page1['total'],31);self.assertEqual(len(page1['items']),25);self.assertEqual(len(page2['items']),6)
        self.assertIn(old['id'],[s['id'] for s in page2['items']])
        self.assertEqual(self.service.dashboard(self.a)['active_submission']['id'],old['id'])

    def test_upgrade_existing_database_selects_latest_official_once(self):
        with tempfile.TemporaryDirectory() as directory:
            with sqlite3.connect(Path(directory)/'arena.sqlite3') as con:
                con.executescript(SCHEMA)
                con.execute("INSERT INTO users(id,username,name,password,role,created) VALUES(1,'old','old','unused','team',0)")
                for kind in ('official','official','local'):
                    con.execute("INSERT INTO submissions(user_id,filename,language,digest,path,kind,created) VALUES(1,'old.py','python','hash','unused',?,0)",(kind,))
            with ThreadPoolExecutor(2) as pool:
                databases=list(pool.map(lambda _:Database(directory),range(2)))
            for db in databases:self.assertEqual(db.active_submission(1)['id'],2)
