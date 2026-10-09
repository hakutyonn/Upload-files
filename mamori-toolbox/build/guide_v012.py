"""Capture actual controls with red annotations. No synthetic UI or private user data."""
from pathlib import Path
import base64, html, io, json, os
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright
V='0.1.2-preview'
STEPS=[
('home','はじめに：機能と手順書を選ぶ',['[role=tablist]','header a[href="USER_GUIDE.html"]','header a:has-text("最新版")'],None,['左メニューで点検する場所を選びます。','「手順書を開く」は別タブで開き、入力画面は残ります。','「最新版・更新情報」は公開配布ページを開きます。更新確認は手動です。']),
('entry','入口・認証 1：対象と認証を入力',['#asset-alias','#asset-type','#asset-exposure','#asset-mfa'],['label:has(#asset-alias)','label:has(#asset-type)','label:has(#asset-exposure)','label:has(#asset-mfa)'],['管理用の別名を入力。IP・パスワードは不要です。','対象の種類を選びます。初回は「架空例を入力」でも試せます。','管理者が確認した公開範囲を選びます。','多要素認証は登録だけでなく、実際の適用状況を選びます。']),
('entry','入口・認証 2：設定を確認して追加',['#asset-patch','#asset-logging','#asset-checkedOn','#asset-form button[type=submit]'],['label:has(#asset-patch)','label:has(#asset-owner)','label:has(#asset-logging)','label:has(#asset-separateAdmin)','label:has(#asset-checkedOn)','#asset-form .buttons'],['更新の適用状況と管理責任者を選びます。','ログの担当と、日常用・管理用アカウントの分離を選びます。','設定を確認した日を入力。不明な日は空欄にします。','「優先事項を確認して台帳へ追加」を押します。追加だけではファイル保存されません。']),
('entry-saved','入口・認証 3：保存・再読込',['#asset-export','#asset-report','#asset-import'],['#asset-table','#asset-export','#asset-report','#asset-clear','label:has(#asset-import)'],['後日続ける場合は「台帳JSONを保存」。','人が読む資料には「改善メモを保存」。','再開時は保存した台帳JSONを選びます。現在の台帳を置き換える前に確認します。']),
('windows','Windows：架空の結果から見方を確認',['#windows-demo','#windows-import','#windows-report'],['label:has(#windows-import)','#windows-demo','#windows-report'],['「架空の結果で表示を試す」を押します。実端末の診断ではありません。','管理者が承認・取得したJSONがある場合だけ読み込みます。','結果を読み、「点検結果を保存」。未確認を安全とは判断しません。']),
('url','不審URL：リンクを開かず点検',['#url-input','#url-domain','#url-form button[type=submit]'],['#url-form'],['URLを貼り付けます。この機能は接続先を開きません。','正規ドメインは別の信頼できる経路で確認した場合だけ入力。','「リンクを開かず点検する」を押し、下のホスト名・注意点を読みます。「確認メモを保存」で記録できます。未検出でも安全性は未確認です。']),
('redact','AI送信前 1：文章と伏せたい語句',['#redact-input','#redact-terms','#redact-form button[type=submit]'],['#redact-form'],['文章を入力。外部AIへの送信はしません。','社名・氏名・案件名などは1行ずつ指定します。','「候補を点検して伏せ字案を作る」を押します。匿名化の保証ではありません。']),
('redact-output','AI送信前 2：全文確認後に保存',['#redact-output','#redact-reviewed','#redact-copy','#redact-save'],['#redact-summary','#redact-output','label:has(#redact-reviewed)','#redact-copy','#redact-save'],['伏せ字案を最後まで読み、機密情報や特定につながる文脈が残っていないか確認。','全文を見直した後だけチェック。外部送信の許可を意味しません。','「伏せ字案をコピー」を押すとコピーできます。','「伏せ字案をTXTで保存」を押し、保存先も確認します。']),
('recovery','復旧 1：備えと試験日を入力',['#recovery-backup','#recovery-isolated','#recovery-businessTest','#recovery-testDate'],['#recovery-selects','label:has(#recovery-testDate)'],['重要データをバックアップしているか選択。','本番からの切り離し・削除耐性を確認したか選択。','残りの4項目も選びます。未実施・未確認はそのまま残します。','直近の復元試験日を入力。入力だけで復元や感染検査は行われません。']),
('recovery-metrics','復旧 2：目標と実測値を比較',['#recovery-rpoTarget','#recovery-rtoTarget','#recovery-form button[type=submit]','#recovery-report'],['label:has(#recovery-rpoTarget)','label:has(#recovery-lossObserved)','label:has(#recovery-rtoTarget)','label:has(#recovery-restoreObserved)','#recovery-form .buttons','#recovery-report'],['許容データ損失（RPO）と、試験時に失った時間分を入力。','目標復旧時間（RTO）と、実際に戻すまでの時間を入力。','「不足と目標との差を確認」を押します。単位はすべて時間です。','「点検メモを保存」で結果を保存。入力値だけで復旧を証明できません。']),
('hash','ファイル照合：元と復元後を選ぶ',['#hash-a','#hash-b','#hash-run','#hash-report'],['label:has(#hash-a)','label:has(#hash-b)','#hash-run','#hash-report','#hash-result'],['元ファイルを選びます。1ファイル32 MiBまで。','実際に復元して別に取得したファイルを選びます。同じ元ファイルを2回選ばないでください。','「2ファイルのSHA-256を比較」を押します。暗号機能が使えなければ比較しません。','結果を保存。一致しても非感染や業務再開は保証されません。'])]
def run(pkg,out):
    pkg=Path(pkg);out=Path(out);out.mkdir(parents=True,exist_ok=True);imgdir=pkg/'guide-images';imgdir.mkdir(exist_ok=True)
    tests=[];errors=[];requests=[]
    def ok(name,v):
        tests.append({'name':name,'pass':bool(v)})
        if not v:raise AssertionError(name)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',22)
    with sync_playwright() as p:
        opts={'headless':True,'args':['--no-sandbox']}
        if os.environ.get('CHROMIUM_PATH'):opts['executable_path']=os.environ['CHROMIUM_PATH']
        browser=p.chromium.launch(**opts);c=browser.new_context(viewport={'width':1280,'height':1000},accept_downloads=True);page=c.new_page();page.set_default_timeout(10000)
        page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append(r.url) if r.url.startswith(('https://','http://')) else None);page.on('dialog',lambda d:d.accept())
        page.set_content((pkg/'START.html').read_text(),wait_until='load')
        ok('CSP allows only the reviewed scripts',not errors and len(page.locator('#ps-hash').inner_text())==64)
        ok('Manual opens separately',page.locator('header a[href="USER_GUIDE.html"]').get_attribute('target')=='_blank')
        page.locator('#tab-windows').click();ok('Script disabled before administrator confirmation',page.locator('#windows-script').is_disabled());page.locator('#windows-reviewed').check();ok('Script enabled after confirmation',page.locator('#windows-script').is_enabled());page.locator('#windows-reviewed').uncheck()
        page.locator('#tab-redact').click()
        for name,secret in [('long','password='+'a'*400),('json','{"api_key":"'+'b'*80+'"}'),('stripe','sk_live_'+'c'*40),('bearer','Bearer '+'d'*400)]:
            page.locator('#redact-input').fill(secret);page.locator('#redact-form button[type=submit]').click();value=page.locator('#redact-output').inner_text();ok('Redaction regression '+name,'[伏せ字' in value and secret[-20:-2] not in value);ok('Manual review gate '+name,page.locator('#redact-save').is_disabled())
        pages=[]
        for ix,(mode,title,marks,regions,steps) in enumerate(STEPS):
            tab=mode.split('-')[0];tab='recovery' if tab=='hash' else tab
            page.locator('#tab-'+tab).click();page.evaluate('() => window.scrollTo(0,0)')
            if mode.startswith('entry'):
                page.locator('#asset-example').click()
                if mode=='entry-saved':page.locator('#asset-form button[type=submit]').click()
            if mode=='windows':page.locator('#windows-demo').click()
            if mode=='url':page.locator('#url-example').click();page.locator('#url-form button[type=submit]').click()
            if mode.startswith('redact'):
                page.locator('#redact-example').click()
                if mode=='redact-output':page.locator('#redact-form button[type=submit]').click()
            if mode.startswith('recovery'):
                page.locator('#recovery-example').click()
                if mode=='recovery-metrics':page.locator('#recovery-form button[type=submit]').click()
            if mode=='hash':
                page.locator('#hash-a').set_input_files(str(pkg/'samples/original-example.txt'));page.locator('#hash-b').set_input_files(str(pkg/'samples/restored-same-example.txt'))
            page.evaluate('() => {document.getElementById("status").textContent=""; window.scrollTo(0,0);}')
            boxes=[]
            for sel in regions or marks:
                for loc in page.locator(sel).all():
                    if loc.is_visible():boxes.append(loc.bounding_box())
            if regions is None:clip={'x':0,'y':0,'width':1280,'height':760}
            else:
                x=max(0,min(b['x'] for b in boxes)-20);y=max(0,min(b['y'] for b in boxes)-34);x2=min(1280,max(b['x']+b['width'] for b in boxes)+20);y2=max(b['y']+b['height'] for b in boxes)+22;clip={'x':x,'y':y,'width':x2-x,'height':y2-y}
            im=Image.open(io.BytesIO(page.screenshot(clip=clip,full_page=True))).convert('RGB');draw=ImageDraw.Draw(im)
            for num,sel in enumerate(marks,1):
                b=page.locator(sel).bounding_box();x=b['x']-clip['x'];y=b['y']-clip['y'];w=b['width'];h=b['height'];draw.rectangle((x-3,y-3,x+w+3,y+h+3),outline='#d8212b',width=4);cx=max(18,x-3);cy=max(18,y-4);draw.ellipse((cx-17,cy-17,cx+17,cy+17),fill='#d8212b',outline='white',width=2);draw.text((cx,cy),str(num),anchor='mm',font=font,fill='white')
            name=f'{ix+1:02d}-{mode}.png';im.save(imgdir/name,optimize=True);pages.append((title,name,steps));ok('Real annotated screenshot '+mode,True)
        page.locator('#tab-entry').click()
        with page.expect_download() as dl:page.locator('#asset-export').click()
        saved=out/'saved-assets.json';dl.value.save_as(saved);obj=json.loads(saved.read_text());ok('Actual JSON download',obj['schema']=='mamori.assets/1' and len(obj['assets'])==1)
        page.locator('#asset-clear').click();page.locator('#asset-import').set_input_files(str(saved));page.wait_for_function('() => document.querySelectorAll("#asset-table tbody tr").length===1');ok('Saved inventory reload',True)
        page.locator('#tab-redact').click();page.locator('#redact-example').click();page.locator('#redact-form button[type=submit]').click();page.locator('#redact-reviewed').check()
        with page.expect_download() as dl:page.locator('#redact-save').click()
        saved=out/'redacted.txt';dl.value.save_as(saved);ok('Actual TXT download','[伏せ字' in saved.read_text() and 'demo@example.com' not in saved.read_text());page.locator('#redact-input').fill('changed');ok('Input change revokes export',page.locator('#redact-save').is_disabled())
        for width in [1366,390,360]:
            page.set_viewport_size({'width':width,'height':920})
            for tab in ['home','entry','windows','url','redact','recovery']:
                page.locator('#tab-'+tab).click();ok(f'No horizontal overflow {width} {tab}',page.evaluate('() => document.documentElement.scrollWidth<=innerWidth+1'))
        ok('No automatic external HTTP',not requests);ok('No JavaScript errors',not errors)
        css='''@page{size:A4 landscape;margin:12mm}*{box-sizing:border-box}body{font:15px/1.6 "Noto Sans CJK JP","Meiryo",sans-serif;color:#173044;margin:0}h1{font-size:35px;margin:5px 0}h2{font-size:24px;margin:5px 0 12px}.page{page-break-after:always;padding:0 8px}.page:last-child{page-break-after:auto}.top{font-size:11px;color:#386170;border-bottom:2px solid #173044;padding:4px 0 8px}.visual{display:block;max-width:100%;max-height:380px;margin:12px auto;object-fit:contain;border:1px solid #d9e1e7}.steps{display:grid;grid-template-columns:1fr 1fr;gap:7px 20px}.step{padding:7px 10px;border-left:3px solid #d8212b;background:#f3f7fa;font-size:14px}.num{color:#b31b28;font-weight:bold}.note{background:#fff3e0;border-left:4px solid #bd761a;padding:10px 15px;font-size:13px}.flow{display:flex;gap:12px;margin:25px 0}.card{flex:1;padding:20px;background:#ecf3f7;border-top:5px solid #1c6678}.card strong{font-size:23px;display:block}.foot{font-size:10px;color:#536779;margin-top:10px;padding-top:7px}table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:8px;border-bottom:1px solid #dbe3e8;text-align:left}th{background:#eaf2f6}@media screen{body{background:#eaf0f3}.page{max-width:1120px;background:white;margin:20px auto;padding:25px}.visual{max-height:520px}}@media screen and (max-width:650px){.steps,.flow{display:block}.step,.card{margin:8px 0}.page{padding:15px}h1{font-size:28px}h2{font-size:21px}.visual{max-height:none;width:100%}}'''
        cover='<section class="page"><div class="top">AI業務改善ラボ / 白鳥 裕児　個人・法人とも無料</div><h1>守りの道具箱<br>赤枠でわかる操作手順書</h1><p>5つの点検を、入力・確認・保存まで。'+V+'</p><div class="flow"><div class="card"><strong>1　展開</strong>ZIPを右クリックし「すべて展開」。ZIP内から直接起動しません。</div><div class="card"><strong>2　開く</strong>START.htmlを許可されたPCブラウザーで開きます。</div><div class="card"><strong>3　試す・保存</strong>最初は架空例で試し、必要な結果を各画面から保存します。</div></div><div class="note">ウイルス対策・常時監視・攻撃の自動遮断ではありません。「未検出」「一致」は安全証明ではありません。会社端末は社内承認が必要です。個別相談・個別サポート・導入代行は含まれません。</div><p>登録・支払い・外部AIは不要。入力は自動保存されません。提供者の毎回の同席は不要ですが、利用者の確認・管理者の判断は必要です。</p><p class="foot">画像は配布HTMLを実際に動かして撮影し、操作箇所に赤枠を追加したものです。生成AIで画面を描き直していません。画面内の値はすべて架空です。</p></section>'
        sections=[cover];texts=['守りの道具箱 '+V+' / 赤枠付き操作手順書']
        for i,(title,name,steps) in enumerate(pages,2):
            b64=base64.b64encode((imgdir/name).read_bytes()).decode();alt=html.escape('。'.join(steps),quote=True)
            sections.append('<section class="page"><div class="top">守りの道具箱 / '+V+'</div><h2>'+html.escape(title)+'</h2><img class="visual" alt="'+alt+'" src="data:image/png;base64,'+b64+'"><div class="steps">'+''.join('<div class="step"><span class="num">'+str(n)+'　</span>'+html.escape(t)+'</div>' for n,t in enumerate(steps,1))+'</div><p class="foot">赤枠の番号と説明を対応させて操作します。実画面・架空入力の説明画像です。 / '+str(i)+'</p></section>');texts += ['\n'+title]+[str(n)+'. '+t for n,t in enumerate(steps,1)]
        sections.append('''<section class="page"><div class="top">更新と困ったとき / 無料・登録不要</div><h2>更新は、自分で確認して入れ替える。</h2><div class="flow"><div class="card"><strong>保存する</strong>台帳・メモを保存。入力中の内容は自動保存されません。</div><div class="card"><strong>別に展開する</strong>公開ページで更新内容を確認し、新版を別フォルダーへ展開。</div><div class="card"><strong>試す</strong>新版を架空例で確認。入口台帳のJSONは再読込できます。</div></div><table><tr><th>困ったこと</th><th>対応</th></tr><tr><td>起動しない／保護警告</td><td>展開済みか確認。組織の制限や警告は解除・回避せず、管理者へ確認。</td></tr><tr><td>保存が見つからない</td><td>ブラウザーのダウンロード履歴と保存先を確認し、実際に開く。</td></tr><tr><td>入力が消えた</td><td>自動復元はありません。入口台帳のJSONのみ再読込可能。TXTは読むための控え。</td></tr><tr><td>JSONが読めない</td><td>形式と版を確認。Windowsのdemo区分が不明な場合は手でfalseに変えず管理者に確認。</td></tr><tr><td>暗号機能が使えない</td><td>照合は停止します。承認済みの対応環境で確認してください。</td></tr></table><div class="note">更新リンクを開くとGitHubへ通信します。自動更新・個別の更新通知はありません。修正と手順書の取得は無料ですが、無期限更新や24時間対応の約束ではありません。</div><p class="foot">実機・第三者診断・電子署名は別途確認が必要です。</p></section>''')
        manual='<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\';"><title>守りの道具箱 | 赤枠付き操作手順書</title><style>'+css+'</style></head><body>'+''.join(sections)+'</body></html>'
        (pkg/'USER_GUIDE.html').write_text(manual);(pkg/'USER_GUIDE.txt').write_text('\n'.join(texts)+'\n\n'+(pkg/'UPDATE_GUIDE.txt').read_text())
        mp=c.new_page();mp.set_content(manual,wait_until='load');mp.emulate_media(media='print');mp.pdf(path=str(pkg/'USER_GUIDE.pdf'),prefer_css_page_size=True,print_background=True);ok('All 11 annotated screenshots included',mp.locator('img').count()==11)
        result={'passed':len(tests),'failed':0,'tests':tests,'automaticHTTP':requests,'jsErrors':errors,'scope':'Chromium DOM-loaded real HTML, synthetic example data','WindowsExecution':'not tested','WindowsMacIPhone':'not tested','thirdPartyReviewAndSigning':'not performed'};(out/'visual-tests.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));browser.close()
    return result
