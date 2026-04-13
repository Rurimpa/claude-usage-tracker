# usage-tracker - Claude Code作業指示書

## プロジェクト概要
Claude Code のトークン消費量・使用率を可視化する汎用ツール。
Claude Code の JSONL ログを解析し、プロジェクト別・モデル別・時系列でトークン消費を表示。
Anthropic OAuth API でセッション残量・追加使用量をリアルタイム監視する。

## バージョン: v3.5.5

## 作業ルール
- コードはファイル全体を提示（部分修正禁止）
- 実装済み機能を失わないこと
- 変更時はCHANGELOG.mdを更新すること
- 設計・仕様変更時はDESIGN.mdを更新すること
- 設計変更が必要な場合は実装を止めてユーザーに確認すること
- 仕様変更・機能追加・設計変更を行った場合は、CHANGELOG.mdだけでなくCLAUDE.mdとDESIGN.mdも該当箇所を更新すること
- ログは必ずlogsフォルダに保存

## ★ v3.0.0 最大の変更: OAuth認証への全面移行

### 旧方式（v2.x — 廃止）
- ブラウザCookieを手動コピーしてsettings.jsonに保存
- curl_cffi でCloudflare回避
- エンドポイント: `https://claude.ai/api/organizations/{org_id}/usage`
- 問題: 手動Cookie取得が煩雑、ブラウザのAppBound Encryptionで自動取得不可

### 新方式（v3.0.0）
- `~/.claude/.credentials.json` のOAuthトークンを自動読み取り
- 標準のHTTPリクエスト（curl_cffi不要）
- エンドポイント: `https://api.anthropic.com/api/oauth/usage`
- ヘッダー: `Authorization: Bearer {token}` + `anthropic-beta: oauth-2025-04-20`
- **セットアップ手順ゼロ**（Claude Codeユーザーなら起動するだけ）

### v3.0.0 で廃止するもの
- `curl_cffi` 依存（requirements.txtから削除）
- `browser_cookie3` 依存（requirements.txtから削除）
- Cookie手動入力UI（設定タブから削除）
- `config.SESSION_KEY`（config.pyから削除）
- settings.json の `session_key` フィールド（削除）
- keyring によるCookie保存（削除）
- 自動セットアップボタン（browser_cookie3ベース、削除）
- usage_api.py の `set_cookies_from_string()` メソッド
- usage_api.py の Cookie関連ロジック全体

### v3.0.0 で追加・変更するもの
- usage_api.py を全面書き換え: OAuthトークン読み取り + 新エンドポイント
- Organization ID の自動取得（OAuthトークンでAPIを叩いて取得。手動入力不要にする）
- トークン期限切れ時の自動リフレッシュ（refreshTokenを使用）
- settings.json からorg_id手動入力も廃止（自動取得に一本化。取得できない場合のみフォールバック）

## セキュリティルール（★必須）

- `.credentials.json` のトークンをログに出力しない（先頭20文字までのマスク表示のみ）
- `.credentials.json` のパスをハードコードしない（`Path.home() / ".claude" / ".credentials.json"`）
- usage_snapshot テーブルの raw_json カラムは廃止（API生レスポンスを保存しない）
- GitHub公開前に .gitignore を作成: `data/`, `logs/`, `__pycache__/`, `.claude/`, `*.pyc`

## 汎用性ルール（★必須）

このツールは特定のユーザーに依存せず、Claude Codeユーザー誰でも使えること。

- パスのハードコード禁止。すべて動的取得
  - 認証: `Path.home() / ".claude" / ".credentials.json"`
  - JSONLログ: `Path.home() / ".claude" / "projects"`
  - DB・ログ: ツールフォルダ内の相対パス
- org_id: OAuth APIから自動取得（手動入力フォールバックあり）
- Cookie手動入力: 廃止

## OAuth認証の実装仕様

### 認証ファイル
場所: `Path.home() / ".claude" / ".credentials.json"`

構造:
```json
{
  "claudeAiOauth": {
    "accessToken": "sk-ant-oat01-...",
    "refreshToken": "sk-ant-ort01-...",
    "expiresAt": 1775827029620,
    "scopes": ["user:inference", "user:profile", ...],
    "subscriptionType": "max"
  }
}
```

### Usage APIエンドポイント
- URL: `https://api.anthropic.com/api/oauth/usage`
- メソッド: GET
- ヘッダー:
  - `Authorization: Bearer {accessToken}`
  - `anthropic-beta: oauth-2025-04-20`
- curl_cffi不要（標準のurllib.requestまたはrequestsで動作）
- ※未公開APIのため予告なく変更される可能性あり

### レスポンス構造（2026-04-10確認）
```json
{
  "five_hour": {"utilization": 100.0, "resets_at": "2026-04-10T14:00:00+00:00"},
  "seven_day": {"utilization": 87.0, "resets_at": "2026-04-10T23:00:00+00:00"},
  "seven_day_sonnet": {"utilization": 42.0, "resets_at": "..."},
  "extra_usage": {"is_enabled": true, "monthly_limit": 10000, "used_credits": 4353.0, "utilization": 43.53}
}
```

### トークン期限切れの処理
- `expiresAt` を確認し、期限切れなら `.credentials.json` を再読み込み
  （Claude Codeが自動でトークンをリフレッシュしてファイルを更新するため）
- 再読み込み後もAPIが401/403を返す場合 → トレイ通知「Claude Codeで再ログインしてください」

### エラーハンドリング
- `.credentials.json` が存在しない → 「Claude Codeをインストールしてログインしてください」
- `claudeAiOauth` キーがない → 「Claude Codeで claude login を実行してください」
- API 429 → レートリミット。リトライ間隔を延長
- API 401/403 → トークン期限切れ。再読み込み → 失敗なら通知

## 表示の大原則：すべてパーセント（%）表示

ドル金額（used_credits）はゲージ・ポップアップ・ツールチップのどこにも表示しない。
追加使用量も含めてすべて utilization（使用率%）ベースで表示すること。

## トレイアイコン表示ロジック（3パターン）

### パターン1: セッションが残っている場合
- 条件: five_hour.utilization < 100
- ゲージ: セッション残量（100 - five_hour.utilization）
- 色: 青スタート（>50%青 → >20%オレンジ → ≤20%赤 → ≤10%赤ゆっくり点滅 → ≤5%赤早い点滅）

### パターン2: セッション使い切り＋追加使用量ON
- 条件: five_hour.utilization >= 100 かつ extra_usage.is_enabled == true
- ゲージ: utilization null → 満タン(100%)、数値 → 100 - utilization
- 色: 黄緑スタート（以下同）

### パターン3: セッション使い切り＋追加使用量OFF
- 条件: five_hour.utilization >= 100 かつ extra_usage.is_enabled == false
- ゲージ: 0%（赤バツ表示）

### トレイアイコン仕様
- 64x64 RGBA、縦バー1本、10段ブロック、セグメント間ギャップ1px
- 背景ダークグレー角丸、目盛り線なし、文字なし

### ポップアップ（左クリック）
- セッション・週間: %表示。追加使用量: is_enabled=false→非表示、null→「無制限」、数値→%

### ツールチップ（ホバー）
- is_enabled=false: 「セッション: 72% 使用」
- is_enabled=true: 「セッション: 80% 使用 | 追加使用量: 無制限」

## コスト概算用料金テーブル（config.pyに定数として保持）

| モデル | input/1Mトークン | output/1Mトークン |
|--------|-----------------|------------------|
| Opus 4.6 | $5 | $25 |
| Sonnet 4.6 | $3 | $15 |
| Haiku 4.5 | $1 | $5 |

## ファイル構成

```
usage-tracker/
├── main.py              # エントリーポイント
├── config.py            # 設定・料金定数・パス
├── scanner.py           # JSONLスキャナー
├── database.py          # SQLite操作
├── gui.py               # tkinter GUI（4タブ）
├── charts.py            # matplotlib グラフ生成
├── usage_api.py         # ★ OAuth認証 Usage APIクライアント（v3.0.0で全面書き換え）
├── period_selector.py   # 期間選択共通コンポーネント
├── icons/
│   ├── gauge.py         # トレイアイコンゲージ生成
│   └── *.png            # 参照画像
├── CLAUDE.md / DESIGN.md / CHANGELOG.md
├── requirements.txt     # ★ curl_cffi, browser_cookie3 を削除
├── .gitignore           # ★ 新規作成
├── data/                # SQLite + settings.json（.gitignore対象）
└── logs/                # ログ（.gitignore対象）
```

## 設定タブUI変更（v3.0.0）

### 廃止する要素
- Cookie手動入力欄
- Cookie保存ボタン
- 自動セットアップボタン（browser_cookie3ベース）
- Organization ID 手動入力欄（自動取得に一本化。フォールバックとしてのみ残す）

### 追加・変更する要素
- 認証ステータス表示: 「OAuth認証: 有効（sk-ant-oat01-xxx...）」
- 認証ファイルパス表示: `C:\Users\{ユーザー名}\.claude\.credentials.json`
- サブスクリプション種別表示: 「Max (5x)」等
- エラー時: 「認証ファイルが見つかりません。Claude Codeをインストールしてログインしてください」
- Usage APIテストボタンは残す

## 必須セット実行（★これを必ず守ること）

main.py を修正したら、必ずその直後に以下を実行すること:
  python main.py
明示的に指示されなくても実行すること。

## 注意事項

- このツールが使用する `https://api.anthropic.com/api/oauth/usage` は未公開APIである
- Anthropic公式のclaude-codeリポジトリで議論されており、コミュニティツールで利用実績がある
- 予告なく変更・廃止される可能性があるため、エラーハンドリングを堅牢にすること
- APIが廃止された場合に備え、将来的にCookie手動入力フォールバックを復活できるようコードをクリーンに保つ
- **__pycache__ 問題**: .pyファイルを修正した後、`__pycache__/` 内の古い .pyc が使われて修正が反映されないことがある。修正後に動作がおかしい場合は `__pycache__/` と `icons/__pycache__/` を削除してから再実行すること
