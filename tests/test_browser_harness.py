"""Validate the browser-only fixture driver without needing network sockets."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from arena.service import Service
from arena.storage import Database
from arena.testing import request
from tests.browser.support.harness import guarded_directory, seed, state, PASSWORD


class BrowserHarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='arena-pw-')
        self.directory = Path(self.temp.name)
        self.marker = self.directory / '.playwright-test-data'
        self.marker.write_text('disposable-fixture-token')
        self.env = patch.dict(os.environ, {'ARENA_TEST_TOKEN':'disposable-fixture-token'})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_requires_matching_marker_token_and_directory_prefix(self):
        self.assertEqual(guarded_directory(self.directory), self.directory)
        with patch.dict(os.environ, {'ARENA_TEST_TOKEN':''}), self.assertRaises(RuntimeError):
            guarded_directory(self.directory)
        self.marker.write_text('wrong')
        with self.assertRaises(RuntimeError):guarded_directory(self.directory)
        self.marker.unlink()
        with self.assertRaises(RuntimeError):guarded_directory(self.directory)
        with self.assertRaises(RuntimeError):guarded_directory(Path(__file__).resolve().parents[1]/'var')

    def test_seed_is_idempotent_and_only_populates_the_disposable_database(self):
        db=Database(self.directory);seed(db);seed(db)
        self.assertEqual(db.one('SELECT COUNT(*) n FROM users')['n'],5)
        self.assertEqual(db.one('SELECT COUNT(*) n FROM submissions')['n'],3)
        self.assertIsNone(db.active_submission(db.one("SELECT id FROM users WHERE username='empty'")['id']))
        for source in db.rows('SELECT path FROM submissions'):
            self.assertTrue(Path(source['path']).is_relative_to(self.directory))
        service=Service(db)
        status,_,raw=request(service,'POST','/api/admin/login',json.dumps({'password':PASSWORD}).encode(),{'Content-Type':'application/json'})
        self.assertEqual(status,200);self.assertEqual(json.loads(raw)['user']['role'],'admin')

    def test_completed_fixture_has_viewable_valid_replays_and_pagination(self):
        db=Database(self.directory);seed(db);service=Service(db)
        user=db.one("SELECT * FROM users WHERE username='alpha'")
        state(db,{'action':'completed_jobs','count':30})
        first=service.matches(user);second=service.matches(user,page=2)
        self.assertEqual(first['total'],30);self.assertEqual(len(first['items']),25);self.assertEqual(len(second['items']),5)
        log=service.replay(user,first['items'][0]['id'])
        self.assertEqual(len(log['turns']),30);self.assertEqual(log['result']['reason'],'completed')
        with self.assertRaises(ValueError):state(db,{'action':'completed_jobs','count':1002})

    def test_history_expiry_and_failure_actions_exercise_real_services(self):
        db=Database(self.directory);seed(db);service=Service(db)
        user=db.one("SELECT * FROM users WHERE username='alpha'")
        before=db.active_submission(user['id'])['id'];state(db,{'action':'submission_history','count':30})
        self.assertEqual(service.list_submissions(user)['total'],31)
        self.assertEqual(db.active_submission(user['id'])['id'],before)
        token,_=service.login({'username':'alpha','password':PASSWORD},'fixture')
        state(db,{'action':'expire_sessions'});self.assertIsNone(service.authenticate(token))
        failed=state(db,{'action':'failed_job'})
        self.assertEqual(service.job_status(user,failed['id'])['status'],'failed')
        with self.assertRaises(ValueError):state(db,{'action':'unknown'})
