#!/usr/bin/env python3
"""Loopback-only local dashboard. Never binds to a public interface."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/"data"
CFG=json.loads((ROOT/"config/config.json").read_text(encoding="utf-8"))
HOST="127.0.0.1"; PORT=int(CFG.get("dashboard_port",8765))
PAGE=r"""<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>守りの道具箱 Sentinel</title><style>
*{box-sizing:border-box}body{margin:0;background:#f1f5f9;color:#173047;font:16px/1.6 system-ui,"Meiryo",sans-serif}header{background:#152d40;color:white;padding:22px 5vw}.wrap{max-width:1050px;margin:24px auto;padding:0 18px}.notice{background:#fff1dc;border-left:5px solid #bc781a;padding:14px 18px;margin:16px 0}.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.card{background:white;border:1px solid #d9e3ec;border-radius:14px;padding:18px}.num{font-size:27px;font-weight:750}.tablewrap{overflow:auto;background:white;border-radius:12px;margin-top:20px}table{width:100%;border-collapse:collapse;min-width:680px}th,td{text-align:left;padding:12px;border-bottom:1px solid #e2e9ef}th{background:#eaf1f7}.high{color:#a51e2c;font-weight:bold}.medium{color:#95520a;font-weight:bold}.info{color:#266c4c}.foot{font-size:13px;color:#546a7a}@media(max-width:680px){.cards{grid-template-columns:1fr}header{padding:18px}}
</style></head><body><header><h1>守りの道具箱 Sentinel</h1><div>ローカル監視ダッシュボード / MVP・検証版</div><small>データはこのPC内のログを読み込みます。外部送信しません。</small></header><main class="wrap"><div class="notice"><b>検証版：</b>完全な侵入検知や自動修復ではありません。未検出は安全の証明ではありません。</div><div class="cards"><section class="card">エージェント状態<div class="num" id="health">確認中</div><small id="beat">時刻を確認中</small></section><section class="card">表示イベント<div class="num" id="count">0</div><small>最新100件</small></section><section class="card">重大・高優先度<div class="num" id="critical">0</div><small>人が確認してください</small></section></div><h2>最近のイベント</h2><div class="tablewrap"><table><thead><tr><th>時刻</th><th>重要度</th><th>検知内容</th><th>推奨対応</th></tr></thead><tbody id="rows"><tr><td colspan="4">読み込み中...</td></tr></tbody></table></div><p class="foot">PCが停止している間は監視できません。24時間運用にはサービス化、停止監視、通知、集中管理、復旧試験が別途必要です。</p></main><script>
async function refresh(){try{const r=await fetch('/api/status',{cache:'no-store'}),d=await r.json();document.getElementById('health').textContent=d.health.status||'未確認';document.getElementById('beat').textContent=d.health.timestamp||'ハートビートなし';document.getElementById('count').textContent=d.events.length;document.getElementById('critical').textContent=d.events.filter(e=>['high','critical'].includes(e.severity)).length;const rows=document.getElementById('rows');rows.replaceChildren();for(const e of d.events){const tr=document.createElement('tr');for(const v of [e.timestamp||'',e.severity||'',e.title||'',e.recommendation||'']){const td=document.createElement('td');td.textContent=v;if(v===e.severity)td.className=v;tr.appendChild(td)}rows.appendChild(tr)}if(!d.events.length)rows.innerHTML='<tr><td colspan="4">イベントなし。監視エージェントを実行してください。</td></tr>'}catch(e){document.getElementById('health').textContent='取得不可';document.getElementById('rows').innerHTML='<tr><td colspan="4">エージェントを実行して再読み込みしてください。</td></tr>'}}refresh();setInterval(refresh,30000);
</script></body></html>"""
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path=="/":
            b=PAGE.encode();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(b);return
        if self.path=="/api/status":
            ev=[];p=DATA/"events.jsonl"
            if p.exists():
                for line in p.read_text(encoding="utf-8",errors="replace").splitlines()[-100:]:
                    try:ev.append(json.loads(line))
                    except json.JSONDecodeError:pass
            try:health=json.loads((DATA/"health.json").read_text(encoding="utf-8"))
            except (OSError,json.JSONDecodeError):health={"status":"未確認"}
            b=json.dumps({"events":list(reversed(ev)),"health":health},ensure_ascii=False).encode()
            self.send_response(200);self.send_header("Content-Type","application/json; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(b);return
        self.send_error(404)
    def log_message(self,*args):pass
if __name__=="__main__":
    print(f"ローカル画面 http://{HOST}:{PORT}");ThreadingHTTPServer((HOST,PORT),H).serve_forever()
