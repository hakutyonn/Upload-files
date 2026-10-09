"""Build and publish only free Mamori files. No paid materials or credentials are packaged."""
from pathlib import Path
import base64, hashlib, io, json, os, subprocess, sys, time, urllib.error, urllib.request, zipfile
from patch_v012 import build, BASE_SHA
from guide_v012 import run
REPO='hakutyonn/Upload-files';V='0.1.2-preview'
BASE='https://raw.githubusercontent.com/'+REPO+'/main/mamori-toolbox/v0.1.1-preview/mamori-toolbox-0.1.1-preview.zip'
OUT=Path('mamori-output');PKG=OUT/'MamoriToolbox'
def digest(b):return hashlib.sha256(b).hexdigest()
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mamori-release-check/0.1.2'}),timeout=45) as r:
        if r.status!=200:raise RuntimeError('Unexpected download status')
        return r.read(20_000_000)
def build_all():
    OUT.mkdir(exist_ok=True);raw=get(BASE)
    if digest(raw)!=BASE_SHA:raise RuntimeError('Base checksum mismatch')
    (OUT/'base.zip').write_bytes(raw);build(OUT/'base.zip',OUT)
    # Regression tests use public artificial strings only.
    js=r'''const C=require('./core-review.cjs'),a=require('node:assert/strict'),fs=require('fs');
const samples=['password='+'a'.repeat(400),'{"api_key":"'+'b'.repeat(400)+'"}','Bearer '+'c'.repeat(400),'sk_live_'+'d'.repeat(200)];
for(const s of samples){const r=C.redact(s);a.match(r.redacted,/伏せ字/);a(!r.redacted.includes(s.slice(-20,-2)));}
const d=JSON.parse(fs.readFileSync('MamoriToolbox/samples/windows-demo.json','utf8'));a.equal(C.validateWindowsDocument(d,'2026-10-09').demo,true);const n={...d};delete n.demo;a.throws(()=>C.validateWindowsDocument(n,'2026-10-09'));a.throws(()=>C.validateWindowsDocument({...d,demo:'false'},'2026-10-09'));console.log('7 regression assertions groups passed');'''
    (OUT/'regression.cjs').write_text(js);subprocess.run(['node','regression.cjs'],cwd=OUT,check=True)
    report=run(PKG,OUT/'qa')
    # Test direct file startup on this Linux runner separately from Windows real devices.
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True);page=browser.new_page();page.goto((PKG/'START.html').resolve().as_uri(),wait_until='load');assert page.locator('#tab-home').is_visible();report['linuxRunnerDirectFileStartup']='passed'
        page.locator('#tab-recovery').click();page.locator('#hash-a').set_input_files(str(PKG/'samples/original-example.txt'));page.locator('#hash-b').set_input_files(str(PKG/'samples/restored-same-example.txt'));page.locator('#hash-run').click();page.wait_for_timeout(800);result=page.locator('#hash-result').inner_text()
        if not page.evaluate('() => !!(globalThis.crypto && crypto.subtle)'):raise RuntimeError('Real browser WebCrypto unavailable on runner')
        assert '一致' in result and page.locator('#hash-report').is_enabled(),result
        report['linuxRunnerActualWebCrypto']='equal sample files compared; this is not a restoration or infection test';browser.close()
    from pypdf import PdfReader
    report['manualPages']=len(PdfReader(PKG/'USER_GUIDE.pdf').pages);assert report['manualPages']==13
    report['regressionGroups']=7;report['version']=V;report['publication']='preview, not stable release or third-party certification'
    (PKG/'CHECKS_AND_LIMITS.txt').write_text('守りの道具箱 '+V+' / 検証範囲\n\n'+str(report['passed'])+'件の画面・入力・保存・赤枠画像の検査に成功。認証情報と架空データ区分の回帰テスト7群に成功。\nGitHub ActionsのLinux上のChromiumでHTMLの直接起動と実Web Cryptoによる同じ内容の2ファイル照合を確認しました。Windows設定収集・Windows/Mac/iPhoneの実端末・実企業環境の試験ではありません。\n\nWindowsスクリプトは実機未検証・未署名です。一般利用者は実行せず、管理者のレビューと承認済み検証環境の試験を先に行ってください。\n第三者脆弱性診断・ウイルススキャン・電子署名は未実施。攻撃の自動遮断、感染の判定、完全匿名化、企業向け認証は提供しません。\n検証の詳細はREVIEW.json。過去の異なる試験件数と合算して侵入テストと表現しないでください。\n')
    (PKG/'REVIEW.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    (PKG/'SHA256SUMS.txt').unlink(missing_ok=True)
    (PKG/'SHA256SUMS.txt').write_text(''.join(digest(f.read_bytes())+'  '+str(f.relative_to(PKG)).replace('\\','/')+'\n' for f in sorted(PKG.rglob('*')) if f.is_file()))
    target=OUT/('mamori-toolbox-'+V+'.zip')
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for f in sorted(PKG.rglob('*')):
            if f.is_file():z.write(f,'MamoriToolbox/'+str(f.relative_to(PKG)))
        assert z.testzip() is None
    report['zipSHA256']=digest(target.read_bytes());report['zipBytes']=target.stat().st_size
    (OUT/'published-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='tests'},ensure_ascii=False))
def publish():
    if os.environ.get('GITHUB_REPOSITORY')!=REPO:raise RuntimeError('Wrong repository')
    token=os.environ['GH_TOKEN'];api='https://api.github.com/repos/'+REPO
    def request(path,body=None):
        req=urllib.request.Request(api+path,data=None if body is None else json.dumps(body).encode(),method='GET' if body is None else 'PUT',headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=60) as r:return json.load(r)
    name='mamori-toolbox-'+V+'.zip';z=(OUT/name).read_bytes()
    outputs={name:z,'USER_GUIDE.pdf':(PKG/'USER_GUIDE.pdf').read_bytes(),'USER_GUIDE.html':(PKG/'USER_GUIDE.html').read_bytes(),'UPDATE_GUIDE.txt':(PKG/'UPDATE_GUIDE.txt').read_bytes(),'CHANGELOG.txt':(PKG/'CHANGELOG.txt').read_bytes(),'REVIEW.json':(OUT/'published-review.json').read_bytes(),'preview.png':(PKG/'guide-images/06-url.png').read_bytes(),name+'.sha256':(digest(z)+'  '+name+'\n').encode()}
    prefix='mamori-toolbox/v'+V+'/'
    for name,data in outputs.items():
        endpoint='/contents/'+prefix+name
        try:existing=request(endpoint)
        except urllib.error.HTTPError as e:
            if e.code!=404:raise
            existing=None
        wanted=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        if existing:
            if existing['sha']!=wanted:raise RuntimeError('Refusing to overwrite existing release file: '+name)
        else:request(endpoint,{'message':'Publish reviewed free '+V+': '+name,'content':base64.b64encode(data).decode(),'branch':'main'})
    # Verify anonymous customer retrieval, independent from authenticated API writes.
    for name,data in outputs.items():
        url='https://raw.githubusercontent.com/'+REPO+'/main/'+prefix+name
        for attempt in range(6):
            try:
                got=get(url)
                if digest(got)!=digest(data):raise RuntimeError('Anonymous checksum differs')
                break
            except (urllib.error.URLError,RuntimeError):
                if attempt==5:raise
                time.sleep(4)
    print('Anonymous downloads verified; ZIP SHA-256:',digest(z),'bytes:',len(z))
if __name__=='__main__':
    if sys.argv[1]=='build':build_all()
    elif sys.argv[1]=='publish':publish()
    else:raise RuntimeError('Unknown command')
