# Usage Tracker - 設計ドキュメント

## ツールの目的
Claude Code の JSONL ログを解析し、プロジェクト別・モデル別・時系列でトークン消費を可視化する。
Anthropic OAuth API でセッション残量・追加使用量をリアルタイム監視する。
システムトレイに常駐し、バックグラウンドで継続的にログ・APIを監視する。

## バージョン: v3.0.0（OAuth認証）

## 基本設計

```
main.py（エントリーポイント・トレイ・スキャンスレッド・Usage APIポーリング・ポップアップ）
  ├── database.py（SQLite操作）
  ├── scanner.py（JSONLスキャン）
  ├── usage_api.py（OAuth Usage APIクライアント）★v3.0.0で全面書き換え
  ├── gui.py（tkinter GUI 4タブ）
  └── charts.py（matplotlib Figure生成）
config.py（VERSION定数・設定・料金テーブル・コスト計算）
```

## 主なファイルと役割

| ファイル | 役割 |
|---------|------|
| `config.py` | VERSION, 料金テーブル, パス定数, GUIカラー, `calc_cost()`, 設定永続化 |
| `database.py` | SQLite CRUD + クエリ（since/until範囲指定, usage_snapshot） |
| `scanner.py` | JSONL差分スキャン（バイナリモード読み込み）、tool_use解析、DB保存 |
| `usage_api.py` | OAuth Usage APIクライアント（.credentials.json読み取り, urllib.request） |
| `charts.py` | matplotlib Figure生成 |
| `gui.py` | tkinter 4タブウィンドウ（ダッシュボード/分析/アクティビティ/設定） |
| `main.py` | 起動, ロギング, トレイ(pystray), スキャンスレッド, Usage APIポーリング, ポップアップ |
| `period_selector.py` | 期間選択共通コンポーネント |
| `icons/gauge.py` | トレイアイコンゲージ生成（Pillow動的描画） |

## 認証方式（v3.0.0: OAuth）

### 認証ファイル
`Path.home() / ".claude" / ".credentials.json"` のOAuthトークンを自動読み取り。
Claude Code がトークンを自動リフレッシュするため、ユーザー操作不要。

### Usage APIエンドポイント
- URL: `https://api.anthropic.com/api/oauth/usage`
- ヘッダー: `Authorization: Bearer {accessToken}`, `anthropic-beta: oauth-2025-04-20`
- 標準のurllib.requestで動作（curl_cffi不要）

### トークン期限切れ処理
- `expiresAt` を確認し期限切れなら `.credentials.json` を再読み込み
- 再読み込み後もAPI 401/403 → 「Claude Codeで再ログインしてください」

### レスポンス構造（2026-04-10確認）
```json
{
  "five_hour": {"utilization": 100.0, "resets_at": "..."},
  "seven_day": {"utilization": 87.0, "resets_at": "..."},
  "seven_day_sonnet": {"utilization": 42.0, "resets_at": "..."},
  "extra_usage": {"is_enabled": true, "utilization": 55.0, ...}
}
```

## 表示の大原則

- **すべて残量表示**（100 - utilization）
- ドル金額は一切表示しない
- ポップアップ・ツールチップ・設定タブすべて「残り ○○%」形式

## トレイアイコン表示ロジック（3パターン）

| パターン | 条件 | ゲージ | 色系統 |
|---|---|---|---|
| 1 | five_hour < 100 | 100 - five_hour | 青 → 黄 → 赤 |
| 2 | five_hour >= 100 + extra ON | utilization null→100%, 数値→100-util | 黄緑 → 黄 → 赤 |
| 3 | five_hour >= 100 + extra OFF | 0%（赤バツ） | - |

色閾値: 残り>50%=青/黄緑、>20%=黄色、≤20%=赤
点滅: ≤10%ゆっくり(1.5秒)、≤5%早い(0.5秒)

## データベース設計

```sql
token_log       -- メッセージ単位のトークン記録（message_uuid でユニーク）
tool_log        -- ツール使用ログ（token_log.id に紐づく）
scan_state      -- スキャン済みファイルのサイズ記録
usage_snapshot  -- Usage APIスナップショット（raw_json廃止済み）
```

## フェーズ管理

| フェーズ | 内容 | 状態 |
|---------|------|------|
| Phase 1 | Claude Code JSONL ログ集計・可視化 | 完了 |
| Phase 2 | Usage API 定期ポーリング + トレイ連動 | 完了 |
| v3.0.0 | OAuth認証への全面移行 | 完了 |
| Phase 3 | Desktop Agent 会話ログ取り込み | 構想のみ |

## スレッド構成

```
メインスレッド: tkinter mainloop
├── ScanLoop: JSONL差分スキャン
├── TrayIcon: pystray.Icon.run()
├── TrayBlink: 点滅制御
├── InitialScan: 初回フルスキャン
└── UsageAPI: OAuth Usage APIポーリング
```

## ビルド・配布

- `build.bat`: PyInstaller ワンフォルダビルド（--noconsole、icons/ 同梱、tkcalendar collect-data）
- `installer.iss`: Inno Setup インストーラー（日本語UI、管理者権限不要、%LOCALAPPDATA%\ClaudeUsageTracker）
- デスクトップショートカット + スタートメニュー登録 + アンインストーラー

## 既知の制限
- `api.anthropic.com/api/oauth/usage` は未公開API（予告なく変更の可能性）
- Phase 1はClaude Codeのみ対象
- cache_creation_5mとcache_creation_1hの分離は未実装
