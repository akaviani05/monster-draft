"""Linux sandbox launcher. Python stdlib only; requires kernel Landlock + libseccomp.

No host home, secrets, shell, network, child processes or writable files are exposed
to players. Compilation uses a separate bounded filesystem sandbox. Fails closed.
This is a defense against ordinary hostile code, not a kernel-escape guarantee.
"""
import ctypes
import ctypes.util
import errno
import os
from pathlib import Path
import resource
import sys


def restrict_filesystem(read_paths, write_paths=(), execute_paths=()):
    libc = ctypes.CDLL(None, use_errno=True)
    abi = libc.syscall(444, 0, 0, 1)
    if abi < 3:
        raise RuntimeError("Linux Landlock ABI >= 3 is required")
    # Handle all filesystem rights supported by this kernel (ABI4 adds network
    # rights in a separate field; networking is denied by seccomp instead).
    handled = (1 << 15) - 1
    class Ruleset(ctypes.Structure):
        _fields_ = [("handled_access_fs", ctypes.c_uint64)]
    class PathRule(ctypes.Structure):
        _pack_ = 1
        _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]
    ruleset = Ruleset(handled)
    fd = libc.syscall(444, ctypes.byref(ruleset), ctypes.sizeof(ruleset), 0)
    if fd < 0:
        raise OSError(ctypes.get_errno(), "landlock_create_ruleset")
    try:
        permissions = {}
        for paths, mask in ((read_paths, (1 << 2) | (1 << 3)),
                            (write_paths, handled & ~(1 << 0)),
                            (execute_paths, (1 << 0) | (1 << 2))):
            for path in paths:
                path = str(Path(path).resolve())
                if not os.path.exists(path):
                    continue
                allowed = mask if os.path.isdir(path) else mask & ((1 << 0) | (1 << 1) | (1 << 2) | (1 << 14))
                permissions[path] = permissions.get(path, 0) | allowed
        for path, allowed in permissions.items():
            pfd = os.open(path, os.O_PATH | os.O_CLOEXEC)
            try:
                rule = PathRule(allowed, pfd)
                if libc.syscall(445, fd, 1, ctypes.byref(rule), 0):
                    raise OSError(ctypes.get_errno(), "landlock_add_rule")
            finally:
                os.close(pfd)
        if libc.prctl(38, 1, 0, 0, 0) or libc.syscall(446, fd, 0):
            raise OSError(ctypes.get_errno(), "landlock_restrict_self")
    finally:
        os.close(fd)


def restrict_syscalls(compiler=False):
    lib = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    ctx = lib.seccomp_init(0x7fff0000)  # SCMP_ACT_ALLOW
    if not ctx:
        raise RuntimeError("seccomp_init failed")
    denied = "socket socketpair connect bind listen accept accept4 ptrace process_vm_readv process_vm_writev mount umount2 pivot_root chroot unshare setns bpf perf_event_open keyctl add_key request_key userfaultfd io_uring_setup open_by_handle_at reboot kexec_load init_module finit_module delete_module swapon swapoff kill tkill tgkill setsid setpgid prlimit64 prctl".split()
    if not compiler:
        denied += "fork vfork clone clone3".split()
    try:
        for name in denied:
            nr = lib.seccomp_syscall_resolve_name(name.encode())
            if nr >= 0 and lib.seccomp_rule_add(ctx, 0x50000 | errno.EPERM, nr, 0):
                raise RuntimeError("seccomp rule failed: " + name)
        if lib.seccomp_load(ctx):
            raise RuntimeError("seccomp_load failed")
    finally:
        lib.seccomp_release(ctx)


def launch():
    mode, target, ready = sys.argv[1:4]
    # Parent-death is inherited across exec; deny subsequent prctl calls so a
    # submitted bot cannot disable it and survive a supervisor crash.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, 9, 0, 0, 0) or os.getppid() != int(sys.argv[4]):
        raise RuntimeError("Supervisor exited before sandbox initialization")
    compiler = mode == "compile"
    target = str(Path(target).resolve())
    # Resolve seccomp before restricting paths: find_library can inspect ldconfig.
    ctypes.CDLL(ctypes.util.find_library("seccomp") or "libseccomp.so.2")
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, ((768 if compiler else 256) * 1024**2,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (12, 12) if compiler else (3, 3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024**2,) * 2 if compiler else (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    # On Linux this limit counts every thread belonging to the real UID, not
    # just descendants of this sandbox. A fixed compiler cap can therefore stop
    # GCC spawning cc1plus when unrelated desktop/server processes are running.
    # Compilers inherit the operator's OS limit (and deployment TasksMax);
    # contestant runtimes still cannot create processes or threads at all.
    if not compiler:
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    runtime = ["/lib", "/lib64", "/usr/lib/x86_64-linux-gnu", "/usr/lib/aarch64-linux-gnu",
               "/usr/lib/python3.12", "/usr/local/lib/python3.11", "/usr/local/lib/python3.12",
               "/usr/local/lib/python3.13", "/usr/local/lib/python3.14", "/dev/null",
               "/etc/ld.so.cache", "/etc/localtime", "/dev/urandom"]
    python_lib = str(Path(os.__file__).resolve().parent)
    runtime.append(python_lib)
    if compiler:
        work = str(Path(target).parent)
        reads, writes, executables = ["/usr", "/lib", "/lib64", "/etc/ld.so.cache", "/dev/null", work], [work], ["/usr"]
        command = ["/usr/bin/g++", "-std=c++17", "-O2", "-pipe", target, "-o", work + "/bot"]
        os.chdir(work)
    else:
        reads, writes = runtime + [target], []
        executable = str(Path(sys.executable).resolve()) if mode == "python" else target
        executables = [executable, "/lib64/ld-linux-x86-64.so.2", "/lib/ld-linux-aarch64.so.1"]
        reads.append(executable)
        command = [executable, "-I", "-B", "-u", target] if mode == "python" else [target]
        os.chdir("/")
    # Load library before Landlock hides the loader's configuration paths.
    restrict_filesystem(reads, writes, executables)
    restrict_syscalls(compiler)
    os.write(int(ready), b"R")
    os.close(int(ready))
    os.execve(command[0], command, {"PATH": "/usr/bin", "LANG": "C.UTF-8", "PYTHONHASHSEED": "0", "TMPDIR": str(Path(target).parent) if compiler else "/nonexistent"})


if __name__ == "__main__":
    try:
        launch()
    except BaseException as exc:
        print("Sandbox unavailable: " + str(exc), file=sys.stderr)
        sys.exit(125)
