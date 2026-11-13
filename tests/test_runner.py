import json
from pathlib import Path
import subprocess
import os
import sys
import tempfile
import threading
import time
import unittest
from arena.storage import ROOT
from runner.referee import prepare_bot, run_match, sandbox_process

LOOP='''import sys
r = int(sys.stdin.readline())
for h in sys.stdin:
    m=[sys.stdin.readline().strip() for _ in range(6)]
    if h.strip()=="YOURTURN":
        ACTION
    else:
        sys.stdin.readline()
'''


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.directory=Path(self.temp.name)
        self.good=('python',ROOT/'bots/greedy.py')

    def tearDown(self):self.temp.cleanup()

    def bot(self, source, name='bot.py'):
        path=self.directory/name;path.write_text(source)
        return ('python',path)

    def test_python_persistent_and_determinism(self):
        a=run_match(self.good,self.good,seed=42)
        b=run_match(self.good,self.good,seed=42)
        self.assertEqual(a['result']['reason'],'completed')
        self.assertEqual(len(a['turns']),30)
        self.assertEqual(a['result'],b['result'])
        self.assertEqual([t['market'] for t in a['turns']],[t['market'] for t in b['turns']])

    def test_cpp_python(self):
        with prepare_bot(ROOT/'bots/starter.cpp') as bot:
            log=run_match(bot,self.good,seed=1)
        self.assertEqual(log['result']['reason'],'completed')

    def test_cpp_compiles_with_many_unrelated_user_threads(self):
        # RLIMIT_NPROC counts the real UID's threads, not just the compiler's
        # children. Desktop apps or a busy HTTP server must not consume an
        # artificial 128-task compiler quota before GCC starts cc1plus.
        release = threading.Event()
        threads = []
        try:
            for _ in range(140):
                thread = threading.Thread(target=release.wait, daemon=True)
                thread.start()
                threads.append(thread)
            with prepare_bot(ROOT/'bots/starter.cpp') as (_, executable):
                self.assertTrue(executable.is_file())
        finally:
            release.set()
            for thread in threads:
                thread.join(timeout=2)

    def test_bot_gets_exact_protocol_and_eof(self):
        source='''import sys,json
r=sys.stdin.readline(); assert r.strip() in '12345' and len(r.strip())==1
my=opp=0
for h in sys.stdin:
    assert h in ('YOURTURN\\n','OPPTURN\\n')
    m=[sys.stdin.readline().strip() for _ in range(6)]
    assert all(len(c)==2 and c[0] in 'ABCDE' and c[1] in '12345' for c in m)
    if h=='YOURTURN\\n':
        my+=1; print(0,flush=True)
    else:
        opp+=1; assert sys.stdin.readline().strip() in '012345'
assert my==opp==15
sys.stderr.write('EOF_OK')
'''
        log=run_match(self.bot(source),self.good)
        self.assertEqual(log['result']['reason'],'completed')
        self.assertIn('EOF_OK',log['stderr'][0])

    def test_invalid_and_extra_responses(self):
        for output in ('6','-1','hello','0 1','۰','0\\n1',' 0'):
            with self.subTest(output=output):
                log=run_match(self.bot(LOOP.replace('ACTION',f'print("{output}",flush=True)')),self.good)
                self.assertEqual(log['result']['winner'],1)
                self.assertIn(log['result']['reason'],('invalid_output','extra_output'))

    def test_crlf_accepted(self):
        log=run_match(self.bot(LOOP.replace('ACTION','sys.stdout.write("0\\r\\n"); sys.stdout.flush()')),self.good)
        self.assertEqual(log['result']['reason'],'completed')

    def test_hang_is_killed_at_real_turn_limit(self):
        start=time.monotonic()
        log=run_match(self.bot(LOOP.replace('ACTION','while True: pass')),self.good)
        self.assertEqual(log['result']['reason'],'turn_timeout')
        self.assertLess(time.monotonic()-start,1.5)

    def test_total_response_budget(self):
        log=run_match(self.bot(LOOP.replace('ACTION','__import__("time").sleep(.025); print(0,flush=True)')),self.good,turn_limit=.1,total_limit=.18)
        self.assertIn(log['result']['reason'],('total_timeout','turn_timeout'))
        self.assertEqual(log['result']['winner'],1)
        self.assertLess(len(log['turns']),30)

    def test_premature_exit(self):
        log=run_match(self.bot('import sys; sys.stdin.readline(); sys.exit(0)'),self.good)
        self.assertEqual(log['result']['winner'],1)
        self.assertEqual(log['result']['reason'],'premature_exit')

    def test_inactive_output(self):
        log=run_match(self.good,self.bot(LOOP.replace('ACTION','print(0,flush=True)').replace('sys.stdin.readline()\n','sys.stdin.readline()\n',1).replace('        sys.stdin.readline()','        print(0,flush=True);sys.stdin.readline()')))
        self.assertEqual(log['result']['winner'],0)
        self.assertIn(log['result']['reason'],('inactive_output','extra_output','invalid_output'))

    def test_output_floods_bounded(self):
        for channel in ('stdout','stderr'):
            log=run_match(self.bot(f'import sys\nsys.{channel}.write("x"*1000000);sys.{channel}.flush()\nwhile True:pass'),self.good)
            self.assertEqual(log['result']['winner'],1)
            self.assertIn(log['result']['reason'],('stdout_limit','stderr_limit'))

    def test_exit_after_eof_cannot_hang_or_print(self):
        for tail,reason in [('\nwhile True: pass','exit_timeout'),('\nprint("bye",flush=True)','extra_output')]:
            log=run_match(self.bot(LOOP.replace('ACTION','print(0,flush=True)')+tail),self.good)
            self.assertEqual(log['result']['reason'],reason)

    def test_closed_output_before_waitpid_is_not_a_false_forfeit(self):
        source=LOOP.replace('ACTION','print(0,flush=True)')+'\nimport os,time\nos.close(1);os.close(2);time.sleep(.06);os._exit(0)'
        log=run_match(self.bot(source),self.good)
        self.assertEqual(log['result']['reason'],'completed')

    def test_inactive_cpu_counts_toward_lifetime_budget(self):
        source=LOOP.replace('ACTION','print(0,flush=True)').replace('        sys.stdin.readline()',
            '        import time\n        start=time.process_time()\n        while time.process_time()-start<.15: pass\n        sys.stdin.readline()')
        slow=LOOP.replace('ACTION','__import__("time").sleep(.09);print(0,flush=True)')
        log=run_match(self.bot(source,'cpu.py'),self.bot(slow,'slow.py'))
        self.assertEqual(log['result']['reason'],'total_cpu_timeout')
        self.assertEqual(log['result']['winner'],1)

    def test_memory_exhaustion_forfeits(self):
        log=run_match(self.bot('x=bytearray(400*1024*1024)'),self.good)
        self.assertEqual(log['result']['winner'],1)
        self.assertLess(len(log['turns']),30)

    def test_shell_network_hostfiles_and_fork_denied(self):
        secret=self.directory/'secret';secret.write_text('DO_NOT_READ')
        source=f'''import os,socket,subprocess
actions=[lambda:open({str(secret)!r}).read(),lambda:open('/etc/passwd').read(),lambda:open('/tmp/escape','w'),lambda:socket.socket(),lambda:os.fork(),lambda:os.execv('/bin/sh',['sh','-c','id']),lambda:subprocess.run(['/bin/sh','-c','id'])]
for action in actions:
    try: action()
    except OSError: pass
    else: raise AssertionError('escape')
print('DENIED_ALL')
'''
        mode,path=self.bot(source)
        p=sandbox_process(mode,path)
        out,err=p.communicate(timeout=3)
        self.assertEqual(p.returncode,0,err)
        self.assertEqual(out.strip(),b'DENIED_ALL')

    def test_cpp_compile_error_is_bounded(self):
        path=self.directory/'bad.cpp';path.write_text('not a program')
        with self.assertRaises(ValueError):
            with prepare_bot(path):pass

    def test_cpp_include_cannot_read_host_secret(self):
        secret=self.directory/'passwords.h';secret.write_text('#define SECRET 42')
        path=self.directory/'bad.cpp';path.write_text(f'#include "{secret}"\nint main(){{return SECRET;}}')
        with self.assertRaises(ValueError):
            with prepare_bot(path):pass

    def test_cpu_hog_on_opponent_turn_is_bounded(self):
        source=LOOP.replace('ACTION','print(0,flush=True)').replace('        sys.stdin.readline()','        while True: pass')
        start=time.monotonic();log=run_match(self.good,self.bot(source))
        self.assertEqual(log['result']['winner'],0)
        self.assertLess(time.monotonic()-start,1.5)

    def test_bot_dies_with_supervisor(self):
        _,path=self.bot('import time; time.sleep(3600)')
        script='from runner.referee import sandbox_process;import os,sys;p=sandbox_process("python",sys.argv[1]);print(p.pid,flush=True);os._exit(0)'
        supervisor=subprocess.run([sys.executable,'-c',script,str(path)],stdout=subprocess.PIPE,timeout=5)
        pid=int(supervisor.stdout.strip());deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            stat=Path(f'/proc/{pid}/stat')
            if not stat.exists() or stat.read_text().rsplit(')',1)[1].split()[0]=='Z':break
            time.sleep(.02)
        else:self.fail('Bot survived supervisor death')

    def test_bot_cannot_disable_parent_death(self):
        source='import ctypes; c=ctypes.CDLL(None,use_errno=True); assert c.prctl(1,0,0,0,0)==-1; print("blocked")'
        mode,path=self.bot(source);p=sandbox_process(mode,path);out,err=p.communicate(timeout=3)
        self.assertEqual(p.returncode,0,err);self.assertEqual(out.strip(),b'blocked')
