#!/usr/bin/env python3
"""Restart the monitoring process after an unexpected exit; does not repair the OS."""
import json, os, signal, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "config.json"
LOG = ROOT / "data" / "supervisor.jsonl"
STOP = False

def write_log(kind, detail=None):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    row = {"timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "event": kind, "detail": detail or {}}
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

def stop_handler(signum, frame):
    global STOP
    STOP = True

def main():
    signal.signal(signal.SIGINT, stop_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop_handler)
    agent = ROOT / "src" / "mamori_guardian.py"
    delay = 2
    while not STOP:
        write_log("AGENT_STARTING")
        try:
            child = subprocess.Popen([sys.executable, str(agent), "--config", str(CFG)], cwd=str(ROOT))
            while child.poll() is None and not STOP:
                time.sleep(1)
            if STOP and child.poll() is None:
                child.terminate()
                try: child.wait(timeout=10)
                except subprocess.TimeoutExpired: child.kill()
                write_log("SUPERVISOR_STOPPED")
                return 0
            code = child.returncode
            if code == 0:
                write_log("AGENT_EXITED_NORMALLY", {"exit_code": code})
                return 0
            write_log("AGENT_CRASH_RESTART", {"exit_code": code, "delay_seconds": delay})
        except Exception as exc:
            write_log("SUPERVISOR_ERROR", {"exception_type": type(exc).__name__, "delay_seconds": delay})
        end = time.monotonic() + delay
        while not STOP and time.monotonic() < end:
            time.sleep(0.5)
        delay = min(delay * 2, 60)
    write_log("SUPERVISOR_STOPPED")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
