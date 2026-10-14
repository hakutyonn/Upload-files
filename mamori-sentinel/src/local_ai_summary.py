"""Optional explanation via local Ollama only; AI output is never executed."""
import json, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; log=ROOT/"data/events.jsonl"
if not log.exists(): raise SystemExit("イベントログがありません")
events=[]
for line in log.read_text(encoding="utf-8").splitlines()[-10:]:
    try:
        e=json.loads(line)
        # Do not send paths, usernames, raw messages, hostnames or file contents.
        events.append({k:e.get(k) for k in ("rule_id","severity","title")})
    except json.JSONDecodeError: pass
if not events: raise SystemExit("説明対象イベントがありません")
prompt=("防御側の解説者として以下のイベントだけを説明してください。不確実性を明示し、確認手順を提案。"
        "コマンド、コード、設定変更、自動実行の指示は出さない。人間の管理者が判断します。\n"
        +json.dumps(events,ensure_ascii=False))
payload=json.dumps({"model":"llama3.2","prompt":prompt,"stream":False}).encode()
req=urllib.request.Request("http://127.0.0.1:11434/api/generate",data=payload,headers={"Content-Type":"application/json"},method="POST")
try:
    with urllib.request.urlopen(req,timeout=45) as r: print(json.loads(r.read().decode()).get("response","応答なし"))
except Exception as e: raise SystemExit("ローカルOllamaに接続できません: "+type(e).__name__)
