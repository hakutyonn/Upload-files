# 守りの道具箱 Sentinel（MVP / Preview）

**無料の企業向けセキュリティ監視エージェント試作版**です。個人・中小企業・大企業での検証を想定しますが、本番運用向けの完成品ではありません。

## この版でできること
- 指定したフォルダーの追加・変更・削除をSHA-256で検知
- Windows Securityログの一部イベント（4625、1102）を取得（Windows・権限に依存）
- Microsoft Defenderの一部状態を読み取り専用で確認
- ローカルJSONL記録と、PC内だけで動くダッシュボード
- 監視ループの例外を記録して再試行
- 手動実行のローカルAI説明サンプル（初期設定では無効）

## 重要な制限
このMVPはマルウェアを完全検出せず、攻撃を完全防止せず、ファイル削除・隔離やWindows設定変更を自動実行しません。AI出力をコマンドとして実行しません。24時間運用には、サービス化、停止時の監視、通知、集中管理、署名付き更新、権限設計、実機・負荷・復旧試験が必要です。

## Windowsでの試用
1. Python 3.11以降を組織のルールに従って用意し、ZIPを展開。
2. `config/config.json` の `watch_paths` がテスト用フォルダーのみか確認。
3. PowerShellで展開先へ移動し実行：

```powershell
python .\\src\\mamori_guardian.py --self-test
python .\\src\\mamori_guardian.py --init-baseline
python .\\src\\mamori_guardian.py --once
python .\\src\\dashboard.py
```

4. `http://127.0.0.1:8765` を同じPCのブラウザーで開く。
5. 継続監視は `python .\\src\\mamori_guardian.py`。停止は Ctrl+C。PCやプロセスが停止中は監視できません。

## AI説明（任意）
`src/local_ai_summary.py` は、手動実行時に限り `127.0.0.1` のOllamaへイベントID・重要度・一般化したタイトルを渡します。パスや生ログは渡しません。Ollamaとローカルモデルが必要です。クラウド接続に変更しないでください。AI出力は助言であり、実行命令ではありません。

## 無料方針
試作版の取得・基本機能・手順書は個人・中小企業・大企業とも無料。個別相談・個別サポート・導入代行は含まれません。更新頻度、SLA、無期限サポートは保証しません。

## 参考
- IPA 情報セキュリティ10大脅威 2026: https://www.ipa.go.jp/security/10threats/10threats2026.html
- IPA 中小企業の情報セキュリティ対策ガイドライン: https://www.ipa.go.jp/security/guide/sme/about.html
- IPA ランサムウェア対策: https://www.ipa.go.jp/security/anshin/measures/ransom_tokusetsu.html
