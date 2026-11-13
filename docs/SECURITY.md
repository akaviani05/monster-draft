# Isolation and limits

The judge is intended to resist ordinary hostile contestant programs. It is not
a replacement for kernel patching or a VM boundary against kernel exploits. Use
a dedicated unprivileged Linux service account on a contest host; never run it
as root or on a machine containing unrelated sensitive workloads.

## Runtime boundary

`runner/isolate.py` loads a trusted launcher, installs hard resource limits,
Landlock filesystem rules and a libseccomp syscall filter, then execs the bot.
The bot gets its own source/executable and read-only runtime/library paths.
Home directories, the site's database, other submissions, `/proc`, `/etc/passwd`,
and writable directories are absent from its permitted filesystem view. The
filesystem restrictions also apply to direct syscalls and symbolic-link targets.
The interpreter, submitted binary and ELF loader are the only executable files
allowed in the runtime profile. Network sockets, fork/clone (including threads),
process signaling, ptrace, process memory access, namespace/mount operations,
io_uring and other high-risk interfaces are blocked by seccomp. `/bin/sh` is not
executable. Calling `os.system` or `subprocess` cannot start a shell.

`PR_SET_PDEATHSIG=SIGKILL` ties every child to its supervisor, including across exec.
Later `prctl` is blocked so contestant code cannot disable this protection.
Referee termination uses **SIGKILL on the entire process group**, followed by reap.
There is no optional unsafe execution fallback. Missing isolation is an
infrastructure error; `python3 -m arena doctor` probes actual denied operations
and runs Python/C++ protocol smoke tests before normal worker startup.

The implementation uses only standard Python modules (`ctypes`, `resource`,
`subprocess`, `selectors`, etc.). `libseccomp` is an OS library, not a pip dependency.
System-call numbers 444–446 target Linux x86-64/aarch64; other architectures are
not supported. Filesystem ABI 3 is the minimum. Reference documentation:
[Linux Landlock](https://docs.kernel.org/userspace-api/landlock.html) and
[seccomp(2)](https://man7.org/linux/man-pages/man2/seccomp.2.html).

## Limits actually enforced

| Resource | Policy |
| --- | --- |
| Active turn response | 0.300 s wall clock, including first-turn runtime startup |
| Player total | 2.000 s sum of active response wall time **and** 2.000 s lifetime CPU |
| CPU watchdog | `/proc/PID/stat` checked while draining pipes; hard RLIMIT_CPU 3 s backstop |
| Inactive work | Lifetime CPU still counts; inactive stdout forfeits |
| Runtime memory | 256 MiB virtual address space (not resident-set size) |
| Standard output | Exact index grammar; 64-byte pending-output ceiling |
| Standard error | 64 KiB lifetime, drained continuously; at most 2 KiB retained by standalone runner |
| End of game | EOF only; 150 ms to exit without extra output |
| Player file writes | Denied; RLIMIT_FSIZE 0, core dumps disabled |
| Compilation | Separate Landlock+seccomp sandbox, 768 MiB, 12 s CPU, 20 s wall |
| Compiler children | Process-group cleanup, inherited OS process limit, service TasksMax=256; 64 KiB diagnostics |
| Submitted source | 64 KiB UTF-8, Python or C++17 |
| Website executable | At most 4 MiB; retained submissions at most about 128 MiB/team |

Compilation intentionally permits compiler subprocesses and read/execute access
to `/usr`, but only its isolated temporary build directory is writable. It gets
no network or access to contest data. `g++` is invoked with fixed argument arrays,
never a shell or user-specified flags. Include/assembler file references remain
subject to Landlock. C++ is compiled once on upload and reused in all matches.

Compilation does not lower `RLIMIT_NPROC`: Linux applies that limit to all threads
of the real UID, including unrelated desktop applications and server requests.
A fixed small value prevents GCC from starting `cc1plus` on busy user accounts.
The compiler retains the operator's inherited process limit and the sample
systemd service's aggregate `TasksMax=256`, plus the existing time, memory,
filesystem and network limits. Contestant runtimes retain `RLIMIT_NPROC=0` and
seccomp denies fork/vfork/clone/clone3.

Time is measured with a monotonic clock. CPU samples have the kernel's tick
resolution and may overshoot slightly before the next sample. Wall-time checks
remain strict; run on otherwise idle hardware with slots no greater than the
dedicated CPU capacity. Constant busy work between turns is not free CPU time.
Inactive/output boundaries are checked from the byte stream; a response arriving
on a boundary may be classified as extra, inactive or malformed output, all of
which forfeit the emitting bot. No timing metadata, seed or future card is ever
sent to bots. Seed is stored as a decimal string in completed replay JSON so
browser download does not round 64-bit integers.

## Application boundary

Passwords use salted scrypt; random session tokens are stored only as SHA-256
hashes with eight-hour expiry. Cookies are HttpOnly and SameSite=Strict; enable
Secure and HTTPS in production. All authenticated mutations require a per-session
CSRF token. Origin/Host checks reject cross-site requests. Team/admin authorization
is server-side, including replay/source access. Friends see only their game and
public result, never another team's source or debug stderr. Tournament replays
are visible to authenticated teams. Logs and the student guide are public files
only when deliberately downloaded/shared by their authorized owners.

SQL is parameterized. Upload paths use random server-generated directories, never
filenames. Text rendering escapes team names, filenames and server messages. CSP
disallows inline/external scripts and framing. Body sizes, connection counts,
socket timeouts, login attempts, compilation concurrency and game/submission rates
are bounded. Team limits: 5 game requests/minute, 1000/day, 4 pending friendlies,
10 invitations/hour, 10 submissions/minute, 100 source files/day. All game quota
checks and invite acceptance are transactional. Reverse-proxy limits provide the
outer HTTP boundary. The in-process HTTP server is for a trusted reverse proxy;
do not expose it directly to the public Internet.


## Desktop practice boundary

`play.py`/`runner/local.py` is a separate, explicitly trusted-file desktop tool
for students who do not use Linux or a terminal. It uses portable pipes/threads,
response timeouts and process cleanup, but cannot promise Linux filesystem,
network, CPU or memory isolation. It is never used by the web service or worker.
C++ compilation there uses the student's installed compiler. Windows and macOS
behavior still requires platform verification; automated local tests ran on Linux.

Final submission selection is owner-only, requires CSRF, and accepts only stored
official submissions belonging to that user. Selection and upload updates are
transactional; already queued jobs and frozen tournament entries retain their IDs.
