"""停掉本项目的所有进程（调度器 + 它 spawn 出来的 tester/getter/server 子进程）。

子进程的命令行是 `python -c from multiprocessing.spawn...`，不含 run.py，
所以必须按父子关系递归杀，不能只匹配命令行。

    python tools/stop.py
"""
import os
import signal
import subprocess
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5555

PS = (
    "Get-CimInstance Win32_Process | "
    "ForEach-Object { $_.ProcessId.ToString() + '|' + $_.ParentProcessId.ToString() "
    "+ '|' + $_.Name + '|' + $_.CommandLine }"
)
NET = ("Get-NetTCPConnection -LocalPort " + str(PORT) +
       " -State Listen -ErrorAction SilentlyContinue | ForEach-Object { $_.OwningProcess }")


def sh(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                          capture_output=True, text=True, errors="ignore").stdout


def snapshot():
    out = subprocess.run(["powershell", "-NoProfile", "-Command", PS],
                         capture_output=True, text=True, errors="ignore").stdout
    procs = []
    for line in out.splitlines():
        parts = line.split("|", 3)
        if len(parts) < 4:
            continue
        try:
            pid, ppid = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        procs.append({"pid": pid, "ppid": ppid, "name": parts[2], "cmd": parts[3]})
    return procs


def main():
    procs = snapshot()
    by_pid = {p["pid"]: p for p in procs}
    marked = set()

    def is_python(p):
        return "python" in p["name"].lower()

    # 1. 命令行含项目路径的 python 进程（调度器）
    for p in procs:
        if is_python(p) and "Proxy_Pool" in (p["cmd"] or ""):
            marked.add(p["pid"])

    # 2. 监听 API 端口的进程 —— spawn 子进程靠这条认领（命令行里没有项目路径）。
    #    只认领 python：Docker Desktop 的端口转发进程（com.docker.backend.exe）也监听 5555，
    #    不筛类型会把整个 Docker 后端当成本项目进程杀掉。
    #    孤儿场景（调度器已死、子进程还占着端口）用 multiprocessing 签名兜底。
    def ancestor_is_project(pid):
        seen = set()
        cur = pid
        while cur in by_pid and cur not in seen:
            seen.add(cur)
            if cur in marked:
                return True
            cur = by_pid[cur]["ppid"]
        return False

    for line in sh(NET).splitlines():
        if not line.strip().isdigit():
            continue
        pid = int(line.strip())
        p = by_pid.get(pid)
        if not p or not is_python(p):
            continue
        if ancestor_is_project(pid) or "multiprocessing" in (p["cmd"] or ""):
            marked.add(pid)

    changed = True
    while changed:                      # 3. 递归收集子孙
        changed = False
        for p in procs:
            if p["ppid"] in marked and p["pid"] not in marked:
                marked.add(p["pid"])
                changed = True

    marked.discard(os.getpid())
    killed = 0
    for pid in sorted(marked):
        try:
            os.kill(pid, signal.SIGTERM)
            killed += 1
        except Exception:
            pass
    print(f"killed {killed} process(es): {sorted(marked)}")


if __name__ == "__main__":
    main()
