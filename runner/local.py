"""Desktop practice for a student's own trusted files, never the web judge.

Works on Windows/macOS/Linux using the standard library. Python bots need Python;
C++ bots also need g++. The production service never imports this module.
"""
from contextlib import ExitStack, contextmanager
import os
from pathlib import Path
import queue
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from .game import VERSION, active_seat, result, score, setup


def terminate(process):
    if process.poll() is None:
        if os.name == 'nt':
            try:subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
            except (OSError,subprocess.TimeoutExpired):process.kill()
        else:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        try:process.wait(timeout=2)
        except subprocess.TimeoutExpired:process.kill()


def start(command, **kwargs):
    options={'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP} if os.name=='nt' else {'start_new_session':True}
    return subprocess.Popen(command,**options,**kwargs)


def cpp_compiler():
    compiler=shutil.which('g++')
    if compiler:return compiler
    for candidate in ('C:/msys64/ucrt64/bin/g++.exe','C:/msys64/mingw64/bin/g++.exe','C:/Program Files/CodeBlocks/MinGW/bin/g++.exe'):
        if Path(candidate).is_file():return candidate
    raise RuntimeError('کامپایلر C++ پیدا نشد. برای فایل .cpp باید g++ نصب باشد؛ فایل‌های .py فقط به پایتون نیاز دارند.')


@contextmanager
def local_command(path):
    path=Path(path).resolve()
    if not path.is_file():raise FileNotFoundError('فایل پیدا نشد: '+str(path))
    if path.suffix.lower()=='.py':
        yield [sys.executable,'-u',str(path)];return
    if path.suffix.lower()!='.cpp':raise ValueError('فقط فایل .py یا .cpp انتخاب کنید.')
    with tempfile.TemporaryDirectory(prefix='duel-local-') as directory:
        executable=Path(directory)/('bot.exe' if os.name=='nt' else 'bot');compiler=cpp_compiler()
        env=dict(os.environ);env['PATH']=str(Path(compiler).parent)+os.pathsep+env.get('PATH','')
        with tempfile.TemporaryFile() as diagnostics:
            flags=['-static'] if os.name=='nt' else []
            process=start([compiler,'-std=c++17','-O2',*flags,str(path),'-o',str(executable)],stdout=diagnostics,stderr=subprocess.STDOUT,env=env)
            try:
                process.wait(timeout=30);diagnostics.seek(0)
                if process.returncode:raise RuntimeError('خطای کامپایل:\n'+diagnostics.read(12000).decode('utf-8','replace'))
            finally:terminate(process)
        yield [str(executable)]


class LocalFault(Exception):
    def __init__(self,seat,reason):self.seat,self.reason=seat,reason


def play(bot0,bot1,seed=None,turn_limit=.3,total_limit=2):
    """Persistent processes, bounded output and per-player response wall limits."""
    seed=seed if seed is not None else int.from_bytes(os.urandom(8),'big')
    banner,cards=setup(seed);market=cards[:6];hidden=iter(cards[6:]);hands=[[],[]];turns=[]
    events=queue.Queue(maxsize=128);processes=[];threads=[];elapsed=[0.,0.];stderr=[bytearray(),bytearray()]
    closed=set();output=[[],[]];flood=[False,False];stop=threading.Event()
    def emit(event):
        try:events.put_nowait(event)
        except queue.Full:flood[event[0]]=True
    def read_stream(seat,stream,kind):
        total=0
        try:
            while not stop.is_set():
                chunk=stream.readline(65) if kind=='out' else stream.read(4096)
                if not chunk:emit((seat,kind,b''));return
                total+=len(chunk)
                if total>(4096 if kind=='out' else 65536):emit((seat,'fault','stdout_limit' if kind=='out' else 'stderr_limit'));return
                emit((seat,kind,chunk))
        except (ValueError,OSError):return
    def collect(timeout=0):
        for seat in (0,1):
            if flood[seat]:raise LocalFault(seat,'stdout_limit')
        try:seat,kind,chunk=events.get(timeout=timeout)
        except queue.Empty:return
        if kind=='fault':raise LocalFault(seat,chunk)
        if kind=='err':stderr[seat].extend(chunk[:max(0,2048-len(stderr[seat]))])
        elif not chunk:closed.add(seat)
        else:output[seat].append(chunk)
    def drain():
        while not events.empty():collect()
    def send(seat,text):
        try:processes[seat].stdin.write(text.encode('ascii'));processes[seat].stdin.flush()
        except (BrokenPipeError,OSError):raise LocalFault(seat,'premature_exit')
    with ExitStack() as stack:
        commands=[stack.enter_context(local_command(p)) for p in (bot0,bot1)]
        try:
            for seat,command in enumerate(commands):
                process=start(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0);processes.append(process)
                for kind,stream in [('out',process.stdout),('err',process.stderr)]:
                    thread=threading.Thread(target=read_stream,args=(seat,stream,kind),daemon=True);thread.start();threads.append(thread)
            for seat in (0,1):send(seat,str(banner)+'\n')
            for t in range(30):
                active=active_seat(t);drain()
                for seat in (0,1):
                    if output[seat]:raise LocalFault(seat,'extra_output')
                    if seat in closed:raise LocalFault(seat,'premature_exit')
                begin=time.monotonic();budget=min(turn_limit,total_limit-elapsed[active]);deadline=begin+budget
                for seat in (0,1):send(seat,('YOURTURN\n' if seat==active else 'OPPTURN\n')+'\n'.join(market)+'\n')
                while not output[active]:
                    remaining=deadline-time.monotonic()
                    if remaining<=0:raise LocalFault(active,'total_timeout' if budget<turn_limit else 'turn_timeout')
                    collect(min(.005,remaining))
                    if output[1-active]:raise LocalFault(1-active,'inactive_output')
                    if active in closed and not output[active]:raise LocalFault(active,'premature_exit')
                duration=time.monotonic()-begin
                if duration>budget:raise LocalFault(active,'turn_timeout' if budget==turn_limit else 'total_timeout')
                elapsed[active]+=duration;drain()
                if len(output[active])!=1:raise LocalFault(active,'extra_output')
                response=output[active].pop()
                if response not in [str(i).encode()+end for i in range(6) for end in (b'\n',b'\r\n')]:raise LocalFault(active,'invalid_output')
                choice=int(response);send(1-active,str(choice)+'\n');picked=market[choice];refill=next(hidden)
                turns.append({'turn':t,'seat':active,'market':market[:],'choice':choice,'card':picked,'refill':refill,'elapsed_ms':round(duration*1000,3)})
                hands[active].append(picked);market[choice]=refill
            for process in processes:process.stdin.close()
            deadline=time.monotonic()+.3
            while time.monotonic()<deadline and (len(closed)<2 or any(p.poll() is None for p in processes)):collect(.005)
            drain()
            for seat,p in enumerate(processes):
                if output[seat]:raise LocalFault(seat,'extra_output')
                if p.poll() is None:raise LocalFault(seat,'exit_timeout')
                if p.returncode:raise LocalFault(seat,'runtime_error')
            outcome=result(hands,banner)
        except LocalFault as fault:
            outcome={'winner':1-fault.seat,'loser':fault.seat,'reason':fault.reason,'scores':[score(hands[p],hands[1-p],banner) for p in (0,1)]}
        finally:
            stop.set()
            for p in processes:terminate(p)
            for p in processes:
                for stream in (p.stdin,p.stdout,p.stderr):
                    if stream:stream.close()
            for thread in threads:thread.join(timeout=.2)
    return {'version':VERSION,'seed':str(seed),'banner':banner,'players':[Path(bot0).name,Path(bot1).name],
            'initial_market':cards[:6],'turns':turns,'hands':hands,'result':outcome,
            'timing':[{'wall_ms':round(t*1000,3),'cpu_ms':0} for t in elapsed],
            'runner':'local-trusted','stderr':[bytes(s).decode('utf-8','replace') for s in stderr]}
