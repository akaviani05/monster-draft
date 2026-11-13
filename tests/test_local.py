import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from arena.storage import ROOT
from runner.local import play


class LocalPracticeTests(unittest.TestCase):
    def test_cpp_python_examples_complete_and_follow_first_card_rule(self):
        log=play(ROOT/'A.cpp',ROOT/'B.py',seed=42)
        self.assertEqual(log['result']['reason'],'completed');self.assertEqual(len(log['turns']),30)
        for turn in log['turns']:
            if turn['market'][0][0]=='A' or turn['market'][0][1]=='5':self.assertEqual(turn['choice'],0)
        self.assertEqual(log['runner'],'local-trusted')

    def test_local_and_isolated_rules_match_with_identical_greedy_choices(self):
        from runner.referee import run_match
        path=ROOT/'bots/greedy.py'
        local=play(path,path,seed=12);secure=run_match(('python',path),('python',path),seed=12)
        self.assertEqual(local['result'],secure['result']);self.assertEqual(local['hands'],secure['hands'])

    def test_hanging_local_code_is_terminated(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'loop.py';path.write_text('while True:pass')
            log=play(path,ROOT/'B.py',turn_limit=.05)
            self.assertEqual(log['result']['winner'],1);self.assertEqual(log['result']['reason'],'turn_timeout')

    def test_idler_style_launcher_resolves_paths_from_its_own_folder(self):
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);shutil.copytree(ROOT/'runner',folder/'runner');shutil.copy2(ROOT/'B.py',folder/'B.py')
            launcher=(ROOT/'play.py').read_text().replace('BOT1 = "A.cpp"','BOT1 = "B.py"')
            (folder/'play.py').write_text(launcher)
            process=subprocess.run([sys.executable,str(folder/'play.py')],cwd=ROOT,capture_output=True,text=True,timeout=5)
            self.assertEqual(process.returncode,0,process.stderr)
            replay=json.loads((folder/'replay.json').read_text())
            self.assertEqual(replay['result']['reason'],'completed');self.assertIn('Winner:',process.stdout) if replay['result']['winner'] is not None else self.assertIn('Draw',process.stdout)
