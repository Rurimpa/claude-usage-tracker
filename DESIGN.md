# Usage Tracker - 設計ドキュメント

## ツールの目的
Claude Code の JSONL ログを解析し、プロジェクト別・モデル別・時系列でトークン消費を可視化する。
Anthropic OAuth API でセッション残量・追加使用量をリアルタイム監視する。
システムトレイに常駐し、バックグラウンドで継続的にログ・APIを監視する。

## バージョン: v3.5.5

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
| `gui.py` | tkinter 5タブウィンドウ（残量/ダッシュボード/分析/アクティビティ/設定） |
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

## 残量タブ（v3.4.0）

- デフォルト表示タブ（最初に開かれる）
- 右上に更新ボタン（Usage API即座ポーリング、3秒連打防止）
- 左側: 300x300 Canvas アナログ時計盤（12時間制）
  - 現在時刻の短針・長針（白/グレー）
  - セッション残量の弧（扇形）を塗りつぶし
  - 弧の角度 = 残量% × 150°（5時間 = 12h時計上で150°）
  - 弧の終端 = リセット時刻の位置（時計上）
  - 弧の始端 = リセット時刻から「残量%×5時間」分だけ反時計回りに戻った位置
  - 弧の色はペース比率で決定（get_session_pace_color: 余裕→青、注意→黄、速すぎ→赤）
  - セッション使い切り時はグレーアウト+テキスト表示
  - 毎分更新（APIポーリングとは独立）
- 左側下: icons/tss.png キャラクター画像（存在する場合のみ）
- 右側: セッション/週間/Sonnet/追加使用量の残量%・リセット情報テキスト
- 下部: 週間消費ペースミニグラフ（400x80 Canvas）
  - 基準ライン: 100%→0%均等消費の直線（グレー）
  - 実消費ライン: usage_snapshotの日別seven_day_utilをプロット（色は基準比較で青/黄/赤）
  - 色判定: actual >= baseline*1.10→青、>= baseline*0.95→黄、< baseline*0.95→赤
  - 現在位置に縦点線、最新ポイントにマーカー＋残量%テキスト
  - 警告テキスト: ペース状態に応じた1行メッセージ

## DBローテーション（v3.4.0）

- 起動時に `cleanup_old_records()` を自動実行
- usage_snapshot: 30日保持、token_log: 90日保持、tool_log: 孤児削除
- ログファイル: 30日保持
- 削除後にVACUUM実行

## アクティビティ更新抑制（v3.4.0）

- アクティビティタブ操作中（Treeviewフォーカス or スクロール中）はUsage API更新を保留
- タブ切替時に保留データを反映

## ポップアップ（v3.5.1）

- トレイ左クリックで表示（340x520 縦長レイアウト）
- 上部: 時計盤(180x180) + キャラクター画像(100x100、icons/tss.png)を横並び
- 中部: テキスト情報（セッション残量%・リセット時刻、週間残量%・リセット時刻、Sonnet残量%、追加使用量）
- 下部: 「ダッシュボードを開く」リンク
- 8秒自動閉じ + クリックで閉じ + フォーカス喪失で閉じ

## ミニウィジェット（v3.5.4）

- トレイメニュー「ミニウィジェット」で表示/非表示切替
- 縦配置レイアウト（上から下）:
  1. キャラクター: icons/tss.png（中央揃え、サイズ比例 max(30, sz//4)）
  2. アナログ時計盤Canvas（draw_clock_on_canvas共通関数）
  3. テキスト情報: 左右分離レイアウト（ラベル左寄せ・値bold右寄せ）
     - Session: / 27% のように左ラベル＋右数値（ポップアップと同形式、リセット時間省略）
     - 160px以上でフルラベル（i18n: Session/セッション等）、未満で略称（S/W/E）
- 外側パディング: max(6, sz//25) で余白確保
- テキスト色: ラベルはCLaudeオレンジ(#E07B39)、値はget_remaining_color()で残量連動
- フォント: max(10, sz//16) — デフォルト200pxで12pt、最小120pxで10pt
- デフォルトサイズ: 200px、最小120px、最大400px
- ホイール拡縮: 20px刻み。キャラ画像・時計盤・フォント・パディングすべて追従
- 左クリック: Usage API即座ポーリング（3秒連打防止）、ドラッグ移動
- 右クリック: 閉じる

## 自動起動設定（v3.5.5）

- 設定タブにチェックボックス「PC起動時に自動起動」
- ON: Windowsスタートアップフォルダ（shell:startup）に ClaudeUsageTracker.lnk を作成
- OFF: ショートカットを削除
- ショートカット作成: PowerShell（WScript.Shell COM）で .lnk を生成
- ターゲット判定: PyInstaller frozen → sys.executable、開発環境 → pythonw.exe + main.py
- 状態判定: アプリ起動時にショートカットの実在をチェック（settings.json の autostart フラグも併用）
- レジストリ不使用（スタートアップフォルダ方式のみ）

## 既知の制限
- `api.anthropic.com/api/oauth/usage` は未公開API（予告なく変更の可能性）
- Phase 1はClaude Codeのみ対象
- cache_creation_5mとcache_creation_1hの分離は未実装
