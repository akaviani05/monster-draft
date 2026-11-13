import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile
from scripts.package_starter import build


class StudentDownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.path=build()

    def test_exact_student_allowlist_excludes_private_opponents_and_production_code(self):
        expected={'README.txt','A.cpp','B.py','play.py','runner/__init__.py','runner/game.py','runner/local.py','viewer/index.html',
                  'viewer/assets/common.js','viewer/assets/viewer.js','viewer/assets/style.css','viewer/assets/logo.svg',
                  'viewer/assets/Vazirmatn.ttf','viewer/assets/OFL.txt',*[f'viewer/assets/monster-{s}.svg' for s in 'abcde']}
        with ZipFile(self.path) as archive:self.assertEqual(set(archive.namelist()),expected)

    def test_offline_viewer_contains_no_server_calls_fixtures_or_account_forms(self):
        with ZipFile(self.path) as archive:
            js=archive.read('viewer/assets/viewer.js').decode();common=archive.read('viewer/assets/common.js').decode();html=archive.read('viewer/index.html').decode()
        for marker in ('fetch(', '/api/', 'local-codes', 'sample-replay', 'admin', 'password'):
            self.assertNotIn(marker,js+common+html)
        self.assertIn('تحلیل نوبت‌به‌نوبت',js)

    def test_extracted_minimal_package_plays_cpp_python_without_the_production_judge(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            with ZipFile(self.path) as archive:archive.extractall(folder)
            result=subprocess.run([sys.executable,str(folder/'play.py')],cwd=Path(directory).parent,capture_output=True,text=True,timeout=35)
            self.assertEqual(result.returncode,0,result.stderr)
            replay=json.loads((folder/'replay.json').read_text())
            self.assertEqual(replay['result']['reason'],'completed')
            self.assertEqual(len(replay['turns']),30)
            self.assertFalse((folder/'bots').exists());self.assertFalse((folder/'arena').exists())

    def test_offline_viewer_loads_a_log_and_steps_without_network(self):
        from runner.game import simulate
        with ZipFile(self.path) as archive:
            payload={'common':archive.read('viewer/assets/common.js').decode(),
                     'viewer':archive.read('viewer/assets/viewer.js').decode(),
                     'log':simulate(42,[lambda *_:0]*2)}
        script="""const vm=require('node:vm'),assert=require('node:assert/strict'),fs=require('node:fs');
const input=JSON.parse(fs.readFileSync(0,'utf8')),elements={};
const document={getElementById:id=>elements[id]||=( {} ),addEventListener(){}};
const box={window:{},document,Intl,console,setTimeout:()=>0,clearTimeout(){},fetch(){throw Error('Network is forbidden')}};
vm.createContext(box);vm.runInContext(input.common,box);box.Arena=box.window.Arena;vm.runInContext(input.viewer,box);
(async()=>{const file={size:1000,text:async()=>JSON.stringify(input.log)};
await elements['log-file'].onchange({target:{files:[file]}});
assert.ok(elements.viewer.innerHTML.includes('viewer-layout'));
elements['playback-mode'].value='manual';elements['playback-mode'].onchange();
elements['analyze-next'].onclick();assert.match(elements.viewer.innerHTML,/id="timeline"[^>]*value="1"/);
})().catch(e=>{console.error(e);process.exitCode=1});"""
        result=subprocess.run(['node','-e',script],input=json.dumps(payload),text=True,capture_output=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
