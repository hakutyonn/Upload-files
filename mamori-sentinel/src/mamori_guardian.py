#!/usr/bin/env python3
"""守りの道具箱 Sentinel MVP: local-only, read-only defensive monitor."""
import argparse, hashlib, json, os, platform, subprocess, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BASELINE = DATA / "baseline.json"
EVENTS = DATA / "events.jsonl"
STATE = DATA / "state.json"
HEALTH = DATA / "health.json"
CONFIG_DEFAULT = ROOT / "config" / "config.json"

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def read_json(path, default=None):
    try: return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return default

def write_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)

def emit(rule, severity, title, evidence=None, action="管理者が確認してください。"):
    DATA.mkdir(parents=True, exist_ok=True)
    e = {"timestamp": now(), "rule_id": rule, "severity": severity, "title": title,
         "evidence": evidence or {}, "recommendation": action,
         "requires_human_approval": True, "automated_system_change": False}
    with EVENTS.open("a", encoding="utf-8") as f: f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"[{severity}] {rule}: {title}")
    return e

def load_config(path):
    c = read_json(path)
    if not isinstance(c, dict): raise ValueError("設定ファイルを読めません")
    interval = c.get("interval_seconds", 60)
    if not isinstance(interval, int) or not 15 <= interval <= 3600:
        raise ValueError("interval_seconds は15〜3600秒にしてください")
    if c.get("auto_remediation") is not False:
        raise ValueError("このMVPでは自動修復を有効にできません")
    paths = c.get("watch_paths", ["sample-watch"])
    if not isinstance(paths, list) or not all(isinstance(x, str) and x.strip() for x in paths):
        raise ValueError("watch_paths はパス文字列の配列にしてください")
    c["watch_paths"] = paths
    c["max_files"] = max(1, min(int(c.get("max_files", 5000)), 50000))
    c["max_file_size_mb"] = max(1, min(int(c.get("max_file_size_mb", 20)), 512))
    return c

def watch_paths(cfg):
    out = []
    for item in cfg["watch_paths"]:
        p = Path(item).expanduser()
        out.append((p if p.is_absolute() else ROOT / p).resolve())
    return out

def digest_file(path, limit):
    h = hashlib.sha256(); size = 0
    with open(path, "rb") as f:
        while True:
            block = f.read(1024 * 1024)
            if not block: break
            size += len(block)
            if size > limit: return None, size
            h.update(block)
    return h.hexdigest(), size

def scan(paths, max_files=5000, max_mb=20):
    found, skipped, errors, count = {}, [], [], 0
    for root in paths:
        if not root.exists():
            errors.append({"path": str(root), "reason": "監視対象がありません"}); continue
        candidates = [root] if root.is_file() else root.rglob("*")
        for p in candidates:
            if count >= max_files:
                skipped.append({"reason": "max_files上限"}); return found, skipped, errors
            try:
                if p.is_symlink() or not p.is_file(): continue
                count += 1
                sha, size = digest_file(p, max_mb * 1024 * 1024)
                if sha is None:
                    skipped.append({"path": str(p), "reason": "サイズ上限", "size": size}); continue
                found[str(p.resolve())] = {"sha256": sha, "size": size}
            except OSError as ex:
                errors.append({"path": str(p), "reason": type(ex).__name__})
    return found, skipped, errors

def compare(baseline, current, active):
    events, updated = [], {}
    for path in sorted(set(baseline) | set(current)):
        old, new = baseline.get(path), current.get(path)
        if old == new:
            if path in active: events.append(("FILE_CHANGE_REVERTED", "info", "ファイルが基準状態に戻りました", {"path": path}))
            continue
        fp = "missing" if new is None else new["sha256"]
        updated[path] = fp
        if active.get(path) == fp: continue
        if old is None: events.append(("FILE_NEW", "medium", "新しいファイルを検知", {"path": path}))
        elif new is None: events.append(("FILE_MISSING", "high", "基準にあったファイルが見つかりません", {"path": path}))
        else: events.append(("FILE_CHANGED", "high", "監視対象ファイルの変更を検知", {"path": path, "baseline_sha256": old["sha256"], "current_sha256": fp}))
    return events, updated

def ps_json(command):
    if platform.system() != "Windows": return None, "not_windows"
    try:
        p = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "AllSigned", "-Command", command],
                           capture_output=True, text=True, timeout=12, check=False)
        if p.returncode or not p.stdout.strip(): return None, "取得不可または権限不足"
        return json.loads(p.stdout), None
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None, "照会失敗"

SECURITY_PS = r"""Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4625,1102; StartTime=(Get-Date).AddMinutes(-2)} -MaxEvents 50 -ErrorAction SilentlyContinue | Select-Object RecordId,TimeCreated,Id | ConvertTo-Json -Depth 2"""
DEFENDER_PS = r"""Get-MpComputerStatus | Select-Object AntivirusEnabled,RealTimeProtectionEnabled | ConvertTo-Json -Depth 2"""

def once(cfg):
    DATA.mkdir(parents=True, exist_ok=True)
    baseline = read_json(BASELINE)
    if not isinstance(baseline, dict):
        emit("BASELINE_MISSING", "high", "基準ファイルがありません",
             action="監視対象を確認し、--init-baseline で基準を作成してください。")
        write_json(HEALTH, {"status": "degraded", "timestamp": now()}); return
    current, skipped, errors = scan(watch_paths(cfg), cfg["max_files"], cfg["max_file_size_mb"])
    state = read_json(STATE, {}) or {}
    events, active = compare(baseline, current, state.get("active", {}))
    for rid, sev, title, ev in events:
        emit(rid, sev, title, ev, "変更が承認済みか確認。不明なら既存のEDR・インシデント対応手順を優先し、ファイルを自動削除しないでください。")
    for ev in skipped: emit("SCAN_LIMIT", "low", "監視上限により一部を確認できません", ev)
    for ev in errors: emit("WATCH_PATH_ERROR", "medium", "監視対象にアクセスできません", ev)
    state["active"] = active
    seen = set(state.get("seen_record_ids", []))
    if cfg.get("check_windows_security_events", True):
        rows, err = ps_json(SECURITY_PS)
        if err is None:
            if isinstance(rows, dict): rows = [rows]
            for row in rows or []:
                rid = str(row.get("RecordId", ""))
                if not rid or rid in seen: continue
                seen.add(rid); eid = str(row.get("Id", ""))
                if eid == "4625":
                    emit("WINDOWS_FAILED_LOGON", "medium", "Windowsのログオン失敗イベントを検知",
                         {"event_id": eid, "record_id": rid, "time": str(row.get("TimeCreated", ""))},
                         "単独のイベントだけで侵入と断定せず、連続性や利用者の心当たりを管理者が確認してください。")
                elif eid == "1102":
                    emit("WINDOWS_AUDIT_LOG_CLEARED", "high", "Windows監査ログ消去イベントを検知",
                         {"event_id": eid, "record_id": rid, "time": str(row.get("TimeCreated", ""))},
                         "計画保守か確認。不明なら組織のインシデント対応手順に従ってください。")
            state["seen_record_ids"] = list(seen)[-1000:]
        elif err != "not_windows":
            emit("WINDOWS_LOG_UNAVAILABLE", "low", "Windowsログを取得できません", {"reason": err})
    if cfg.get("check_defender_status", True):
        d, err = ps_json(DEFENDER_PS)
        if err is None and isinstance(d, dict):
            if d.get("AntivirusEnabled") is False or d.get("RealTimeProtectionEnabled") is False:
                emit("DEFENDER_PROTECTION_OFF", "high", "Defender保護が無効の可能性",
                     {"antivirus": d.get("AntivirusEnabled"), "real_time": d.get("RealTimeProtectionEnabled")},
                     "管理者が状態と組織ポリシーを確認してください。本ツールは設定を勝手に変更しません。")
        elif err != "not_windows":
            emit("DEFENDER_STATUS_UNAVAILABLE", "low", "Defender状態を取得できません", {"reason": err})
    write_json(STATE, state)
    write_json(HEALTH, {"status": "ok", "timestamp": now(), "scanned_files": len(current),
                        "skipped": len(skipped), "errors": len(errors), "version": "0.1.0-preview"})
    print(f"1回の確認完了: files={len(current)} skipped={len(skipped)} errors={len(errors)}")

def init_baseline(cfg):
    DATA.mkdir(parents=True, exist_ok=True)
    if BASELINE.exists(): raise SystemExit("基準ファイルが既にあります。手動で退避・確認するまで上書きしません。")
    current, skipped, errors = scan(watch_paths(cfg), cfg["max_files"], cfg["max_file_size_mb"])
    if not current: raise SystemExit("基準ファイルが0件です。監視先を確認してください。")
    write_json(BASELINE, current)
    emit("BASELINE_CREATED", "info", "監視対象の基準状態を作成", {"files": len(current), "skipped": len(skipped), "errors": len(errors)})
    print(f"基準作成: {len(current)}ファイル")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(CONFIG_DEFAULT))
    ap.add_argument("--init-baseline", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(); cfg = load_config(a.config)
    if a.self_test:
        assert cfg["auto_remediation"] is False
        print("Self-test OK: 設定正常、自動修復は無効です"); return 0
    if a.init_baseline: init_baseline(cfg); return 0
    if a.once: once(cfg); return 0
    print("監視開始。終了はCtrl+C。OS設定変更やファイル削除は行いません。")
    while True:
        start = time.monotonic()
        try: once(cfg)
        except KeyboardInterrupt: print("停止しました"); return 0
        except Exception as ex:
            emit("AGENT_LOOP_ERROR", "high", "監視処理の例外", {"type": type(ex).__name__})
        time.sleep(max(1, cfg["interval_seconds"] - (time.monotonic()-start)))

if __name__ == "__main__": raise SystemExit(main())
