"""Build preview 0.1.2 only from the checksum-verified public 0.1.1 package."""
from pathlib import Path
import base64, hashlib, io, re, zipfile
VERSION='0.1.2-preview'
BASE_SHA='a615b528897afcbe6fe25da7aa4b87d2f8d63b097eec8cf0879c6d03d76cebee'
PUBLIC='https://github.com/hakutyonn/Upload-files/blob/main/mamori-toolbox/README.md'
def once(s,a,b):
    if s.count(a)!=1: raise ValueError('Patch context must occur exactly once: '+a[:90])
    return s.replace(a,b,1)
def build(base, output):
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    pkg=output/'MamoriToolbox'; pkg.mkdir(exist_ok=True)
    raw=Path(base).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=BASE_SHA: raise ValueError('Unexpected base archive')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for i in z.infolist():
            p=Path(i.filename)
            if not i.filename.startswith('MamoriToolbox/') or p.is_absolute() or '..' in p.parts or i.file_size>300000: raise ValueError('Invalid archive entry')
        z.extractall(output)
    s=(pkg/'START.html').read_text()
    scripts=re.findall(r'<script[^>]*>([\s\S]*?)</script>',s)
    assert len(scripts)==3
    core,bundle,ui=scripts
    core=core.replace('0.1.0-preview',VERSION)
    old=next(line for line in core.splitlines() if "'認証情報候補'" in line and 'scan(' in line)
    new=r'''    scan(/(?:password|passwd|api[_ -]?key|client[_ -]?secret|access[_ -]?token|パスワード|秘密鍵)["']?\s*[=:：]\s*(?:"(?:\\.|[^"\r\n])*"|'(?:\\.|[^'\r\n])*'|[^\s\r\n"'<>;,}]+)/gi,'認証情報候補');
    scan(/\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9_]{16,}\b/g,'決済APIキー候補');
    scan(/\bBearer[ \t]+[A-Za-z0-9._~+\/-]{12,}=*/gi,'認証情報候補');'''
    core=once(core,old,new)
    core=once(core,"if(!plain(o)||o.schema!=='mamori.windows/1'||!Array.isArray(o.checks)||o.checks.length>50)","if(!plain(o)||o.schema!=='mamori.windows/1'||typeof o.demo!=='boolean'||!Array.isArray(o.checks)||o.checks.length>50)")
    ui=once(ui,"$('windows-script').addEventListener('click',()=>{", "$('windows-reviewed').addEventListener('change',()=>{$('windows-script').disabled=!$('windows-reviewed').checked;});\n$('windows-script').addEventListener('click',()=>{if(!$('windows-reviewed').checked){note('管理者による確認と検証環境の準備を先に行ってください。',true);return;}")
    for a,b in zip(scripts,[core,bundle,ui]): s=once(s,'<script>'+a+'</script>','<script>'+b+'</script>')
    s=s.replace('v0.1.0-preview','v'+VERSION).replace('公開前の検証用です。','公開検証版です。安定版ではありません。')
    s=once(s,'href="USER_GUIDE.html"','href="USER_GUIDE.html" target="_blank" rel="noopener noreferrer"')
    s=once(s,'<span class="pill">個人・法人とも無料</span>',f'<a class="pill" href="{PUBLIC}" target="_blank" rel="noopener noreferrer" style="color:white">最新版・更新情報</a><span class="pill">個人・法人とも無料</span>')
    s=once(s,'<body>','<body><noscript><p style="padding:20px;border:3px solid #a12a33;background:white">JavaScriptを利用できないため点検は動作していません。組織の制限を解除せず、管理者へ確認してください。手順書だけを開くことはできます。</p></noscript>')
    s=once(s,'承認済みPCで読み取り専用スクリプトを実行し、12項目の結果を表示。取得できない設定は未確認。','まず架空例で12項目の見方を確認。実端末の収集は管理者向け・未検証です。取得できない項目は未確認。')
    s=once(s,'<button class="btn" id="windows-script">点検スクリプトを保存</button>','<label class="checkline"><input type="checkbox" id="windows-reviewed">管理者としてソースを確認し、承認済み検証環境でのみ試用します（実機未検証・未署名）</label><button class="btn" type="button" id="windows-script" disabled>管理者向けスクリプトを保存</button>')
    s=once(s,'</style>','#url-form,#redact-form{align-self:start}\n</style>')
    hashes=' '.join("'sha256-"+base64.b64encode(hashlib.sha256(x.encode()).digest()).decode()+"'" for x in [core,bundle,ui])
    s=re.sub(r"script-src [^;]+;",'script-src '+hashes+';',s,count=1)
    (pkg/'START.html').write_text(s)
    (output/'core-review.cjs').write_text(core)
    (pkg/'VERSION.txt').write_text(VERSION+'\n公開検証版。企業向け認証・安定版ではありません。\n')
    (pkg/'CHANGELOG.txt').write_text('2026-10-09 / '+VERSION+'\n・長い認証情報の末尾が残る問題と、JSON形式の認証情報の取りこぼしを修正。\n・決済APIキーとBearer形式の検出を追加。検出の完全性は保証しません。\n・Windows結果の架空データ区分を必須化。\n・Windowsスクリプトの取得前に管理者確認欄を追加。\n・赤枠付き実画面手順書を全5機能へ追加。\n・手順書を別タブに変更し、点検中の入力画面を維持。\n・手動更新の案内を追加。課金、登録、解析、自動外部送信は追加していません。\n')
    (pkg/'UPDATE_GUIDE.txt').write_text('''守りの道具箱 / 手動更新の手順

1. 入力は自動保存されません。入口台帳はJSON、その他の結果は各画面から必要に応じて保存します。
2. 「最新版・更新情報」から配布ページを開き、版と変更内容を確認します。この操作だけはGitHubへ通信します。
3. 新版ZIPを別フォルダーへ展開します。旧版の上書きはしません。
4. 新しいSTART.htmlを開き、VERSION.txtと画面の版を確認し、まず架空例で試します。
5. 入口台帳はmamori.assets/1形式のJSONのみ再読込できます。TXTから入力を復元する機能はありません。
6. 新版で使えることを確認してから、不要な旧版を組織の手順で削除します。必要な保存結果は消しません。

自動更新・常時通信・個別の更新通知はありません。利用者への通知到達や更新完了は確認できません。
公開する本体・修正・手順書の取得は無料です。無期限更新、個別サポート、一定時間内の修正は約束しません。
認証情報を外部送信済みなら、伏せ字の作成だけで済ませず、管理者の手順で失効・再発行を検討してください。
''')
    (pkg/'00_README.txt').write_text('守りの道具箱 '+VERSION+'\nAI業務改善ラボ / 白鳥 裕児\n\n1. ZIPをフォルダーごと展開。\n2. START.htmlを許可されたPCブラウザーで開く。\n3. 初回は架空例で試す。画像手順書はUSER_GUIDE.html、印刷用はUSER_GUIDE.pdf。\n\n個人・法人とも無料。登録・カード情報・外部AI接続は不要。個別相談・個別サポート・導入代行は含まれません。\n自動防御・常時監視・感染診断ではありません。入力は自動保存されません。\nWindowsスクリプトは実機未検証・未署名。管理者のソース確認と検証が必要です。\nCHECKS_AND_LIMITS.txt、UPDATE_GUIDE.txtも確認してください。\n')
    return pkg
