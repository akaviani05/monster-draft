"""Bounded persistent-process referee. Uses only Python's standard library."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import time

from .game import VERSION, active_seat, result, score, setup

ROOT = Path(__file__).resolve().parent


class InfrastructureError(RuntimeError):
    pass


class BotFault(Exception):
    def __init__(self, seat, reason):
        self.seat, self.reason = seat, reason


def kill_group(process):
    if process:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream:
                stream.close()


def sandbox_process(mode, path):
    rfd, wfd = os.pipe()
    process = None
    try:
        process = subprocess.Popen([sys.executable, "-I", "-B", str(ROOT / "isolate.py"), mode,
                                    str(Path(path).resolve()), str(wfd), str(os.getpid())],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   bufsize=0, start_new_session=True, pass_fds=(wfd,),
                                   env={"PATH": "/usr/bin", "LANG": "C.UTF-8"})
        os.close(wfd)
        wfd = None
        with selectors.DefaultSelector() as sel:
            sel.register(rfd, selectors.EVENT_READ)
            if not sel.select(5) or os.read(rfd, 1) != b"R":
                kill_group(process)
                raise InfrastructureError("Sandbox initialization failed; run `python3 -m arena doctor`.")
        return process
    except BaseException:
        kill_group(process)
        raise
    finally:
        os.close(rfd)
        if wfd is not None:
            os.close(wfd)


@contextmanager
def prepare_bot(path, language=None):
    path = Path(path).resolve()
    language = language or ("cpp" if path.suffix == ".cpp" else "python" if path.suffix == ".py" else "binary")
    if language != "cpp":
        yield language, path
        return
    with tempfile.TemporaryDirectory(prefix="duel-compile-") as directory:
        work = Path(directory)
        source = work / "source.cpp"
        source.write_bytes(path.read_bytes())
        process = sandbox_process("compile", source)
        try:
            # communicate is bounded in time and compiler diagnostics are bounded
            # by a spool file rather than an unbounded in-memory PIPE.
            with tempfile.TemporaryFile() as diagnostics:
                with selectors.DefaultSelector() as sel:
                    for stream in (process.stdout, process.stderr):
                        os.set_blocking(stream.fileno(), False)
                        sel.register(stream, selectors.EVENT_READ)
                    deadline, size = time.monotonic() + 20, 0
                    while sel.get_map():
                        if time.monotonic() > deadline:
                            raise ValueError("Compilation exceeded 20 seconds")
                        for key, _ in sel.select(.05):
                            data = os.read(key.fileobj.fileno(), 8192)
                            if not data:
                                sel.unregister(key.fileobj)
                            else:
                                size += len(data)
                                if size > 65536:
                                    raise ValueError("Compiler output exceeds 64 KiB")
                                diagnostics.write(data)
                    process.wait(timeout=1)
                if process.returncode or not (work / "bot").exists():
                    diagnostics.seek(0)
                    raise ValueError(diagnostics.read().decode("utf-8", "replace")[:12000] or "Compilation failed")
        finally:
            kill_group(process)
        yield "binary", work / "bot"


def cpu_time(process):
    try:
        fields = Path(f"/proc/{process.pid}/stat").read_text().rsplit(")", 1)[1].split()
        return (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK")
    except (FileNotFoundError, ProcessLookupError):
        return 0.0


def run_match(bot0, bot1, seed=0, names=None, turn_limit=.3, total_limit=2.0, debug_seat=None):
    """botN=(python|binary, absolute path). Never use shell=True.

    Limits: response wall time per turn; summed active wall time AND lifetime CPU
    per player. Setup is outside response timing; runtime startup is inside it.
    """
    banner, cards = setup(seed)
    market, hidden, hands, turns = cards[:6], iter(cards[6:]), [[], []], []
    processes, elapsed, cpus, stderr_sizes = [], [0., 0.], [0., 0.], [0, 0]
    stderr_preview, buffers, closed = [bytearray(), bytearray()], [bytearray(), bytearray()], set()
    outcome = None
    events, trace_sizes, trace_truncated = [], {'stdin': 0, 'stdout': 0, 'stderr': 0}, False
    current_turn = -1

    def record(seat, stream, raw):
        nonlocal trace_truncated
        if seat != debug_seat:
            return
        remaining = 16384 - trace_sizes[stream]
        if len(raw) > remaining or len(events) >= 512:
            trace_truncated = True
        if remaining > 0 and len(events) < 512:
            data = raw[:remaining]
            trace_sizes[stream] += len(data)
            events.append({'turn': current_turn, 'stream': stream, 'text': data.decode('utf-8', 'replace')})
    sel = selectors.DefaultSelector()
    started = time.monotonic()
    try:
        for seat, bot in enumerate((bot0, bot1)):
            p = sandbox_process(*bot)
            processes.append(p)
            for kind, stream in (("out", p.stdout), ("err", p.stderr)):
                os.set_blocking(stream.fileno(), False)
                sel.register(stream, selectors.EVENT_READ, (seat, kind))
            os.set_blocking(p.stdin.fileno(), False)

        def send(seat, message):
            try:
                os.write(processes[seat].stdin.fileno(), message.encode("ascii"))
                record(seat, 'stdin', message.encode('ascii'))
            except (BrokenPipeError, BlockingIOError):
                raise BotFault(seat, "premature_exit")

        def collect(timeout=0):
            for key, _ in sel.select(timeout):
                seat, kind = key.data
                data = os.read(key.fileobj.fileno(), 8192)
                if not data:
                    sel.unregister(key.fileobj)
                    if kind == "out":
                        closed.add(seat)
                    continue
                record(seat, 'stdout' if kind == 'out' else 'stderr', data)
                if kind == "err":
                    stderr_sizes[seat] += len(data)
                    if stderr_sizes[seat] > 65536:
                        raise BotFault(seat, "stderr_limit")
                    if len(stderr_preview[seat]) < 2048:
                        stderr_preview[seat].extend(data[:2048-len(stderr_preview[seat])])
                else:
                    buffers[seat].extend(data)
                    if len(buffers[seat]) > 64:
                        raise BotFault(seat, "stdout_limit")
            for seat, p in enumerate(processes):
                cpus[seat] = max(cpus[seat], cpu_time(p))
                if cpus[seat] > total_limit:
                    raise BotFault(seat, "total_cpu_timeout")

        for seat in (0, 1):
            send(seat, str(banner) + "\n")
        for t in range(30):
            current_turn = t
            active = active_seat(t)
            collect()
            for seat in (0, 1):
                if buffers[seat]:
                    raise BotFault(seat, "extra_output")
                if seat in closed:
                    raise BotFault(seat, "premature_exit")
            start = time.monotonic()
            deadline = start + min(turn_limit, max(0, total_limit-elapsed[active]))
            for seat in (0, 1):
                send(seat, ("YOURTURN\n" if seat == active else "OPPTURN\n") + "\n".join(market) + "\n")
            while b"\n" not in buffers[active]:
                if time.monotonic() >= deadline:
                    raise BotFault(active, "total_timeout" if elapsed[active] + turn_limit >= total_limit else "turn_timeout")
                collect(min(.005, max(0, deadline-time.monotonic())))
                if buffers[1-active]:
                    raise BotFault(1-active, "inactive_output")
                if active in closed and b"\n" not in buffers[active]:
                    raise BotFault(active, "premature_exit")
            duration = time.monotonic() - start
            if start + duration > deadline:
                raise BotFault(active, "turn_timeout" if duration > turn_limit else "total_timeout")
            elapsed[active] += duration
            response = bytes(buffers[active])
            buffers[active].clear()
            if response not in [str(i).encode() + end for i in range(6) for end in (b"\n", b"\r\n")]:
                raise BotFault(active, "invalid_output")
            choice = int(response.strip())
            send(1-active, str(choice) + "\n")
            picked, refill = market[choice], next(hidden)
            turns.append({"turn": t, "seat": active, "market": market[:], "choice": choice,
                          "card": picked, "refill": refill, "elapsed_ms": round(duration*1000, 3)})
            hands[active].append(picked)
            market[choice] = refill
        # EOF only. Allow bounded graceful shutdown; catch final-turn extra output.
        for p in processes:
            p.stdin.close()
        end = time.monotonic() + .15
        # A pipe can reach EOF just before waitpid reports process exit. Keep the
        # grace window open until BOTH conditions hold; otherwise normal Python
        # shutdown is occasionally misclassified under CPU contention.
        while time.monotonic() < end and (len(closed) < 2 or any(p.poll() is None for p in processes)):
            collect(.005)
            for seat in (0, 1):
                if buffers[seat]:
                    raise BotFault(seat, "extra_output")
        for seat, p in enumerate(processes):
            if p.poll() is None:
                raise BotFault(seat, "exit_timeout")
            if p.returncode != 0:
                raise BotFault(seat, "runtime_error")
        outcome = result(hands, banner)
    except BotFault as fault:
        outcome = {"winner": 1-fault.seat, "loser": fault.seat, "reason": fault.reason,
                   "scores": [score(hands[p], hands[1-p], banner) for p in (0, 1)]}
    finally:
        sel.close()
        for p in processes:
            kill_group(p)
    replay = {"version": VERSION, "seed": str(seed), "banner": banner,
            "players": names or ["P0", "P1"], "initial_market": cards[:6],
            "turns": turns, "hands": hands, "result": outcome,
            "timing": [{"wall_ms": round(elapsed[p]*1000, 3), "cpu_ms": round(cpus[p]*1000, 3)} for p in (0, 1)],
            "stderr": [bytes(s).decode("utf-8", "replace") for s in stderr_preview],
            "duration_ms": round((time.monotonic()-started)*1000, 3)}
    if debug_seat in (0, 1):
        replay['_diagnostics'] = {'seat': debug_seat, 'events': events,
                                  'truncated': trace_truncated,
                                  'exit_code': processes[debug_seat].returncode,
                                  'result': outcome, 'timing': replay['timing'][debug_seat]}
    return replay
