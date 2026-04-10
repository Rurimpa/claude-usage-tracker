# CHANGELOG

## v3.0.0 (2026-04-10)

### OAuth認証への全面移行（認証方式の完全刷新）
- **認証方式を完全刷新**: ブラウザCookie手動入力 → `~/.claude/.credentials.json` のOAuthトークン自動読み取り
- **セットアップ手順ゼロ**: Claude Codeユーザーなら起動するだけで動作
- **エンドポイント変更**: `claude.ai/api/organizations/{org_id}/usage` → `api.anthropic.com/api/oauth/usage`
- **curl_cffi不要**: 標準のurllib.requestで動作（Cloudflare回避不要）
- **トークン自動更新**: 期限切れ時に `.credentials.json` を再読み込み（Claude Codeが自動リフレッシュ）

### 廃止した依存ライブラリ
- curl_cffi（Cloudflare TLS偽装 → 不要に）
- browser_cookie3（ブラウザCookie自動取得 → 不要に）
- keyring（Cookie暗号化保存 → OAuthトークンはClaude Code管理のため不要）

### 設定タブUI変更
- Cookie手動入力欄を削除
- 自動セットアップボタンを削除
- OAuth認証ステータス表示を追加（トークンマスク表示、サブスクリプション種別）
- Organization ID 入力欄は自動取得フォールバックとして残存

### ビルド・配布
- PyInstaller でワンフォルダビルド対応（build.bat 作成）
- Inno Setup でインストーラー作成（installer.iss 作成、日本語UI）
- インストール先: `%LOCALAPPDATA%\ClaudeUsageTracker`（管理者権限不要）
- デスクトップショートカット + スタートメニュー登録 + アンインストーラー付き

### セキュリティ
- settings.json から session_key フィールドを削除（Cookie平文保存の廃止）

### 表示の全面変更
- ポップアップ・ツールチップ・設定タブの全数値を「残量表示」に統一（「残り ○○%」形式）
- 金額表示（$表記）をすべて廃止。utilization %のみ
- ゲージ色閾値変更: >50%青/黄緑 → >20%黄色 → ≤20%赤。点滅: ≤10%ゆっくり、≤5%早い
- トレイアイコン3パターン表示切り替え（F-14）: セッション残あり→青、セッション使い切り+追加ON→黄緑、+追加OFF→赤バツ
- ウィンドウタイトルにバージョン表示（「Claude Usage Tracker v3.0.0」）
- config.py に VERSION 定数追加

### セキュリティ改善
- usage_snapshot テーブルから raw_json カラム廃止
- .gitignore 作成（data/, logs/, __pycache__/, .claude/, *.pyc）

### 内部改善
- usage_api.py: 全面書き換え。`load_credentials()`, `UsageAPIClient` をOAuthベースに
- config.py: `SESSION_KEY`, `KEYRING_*`, `load_cookie()`, `save_cookie()` 削除。`VERSION` 追加
- main.py: Cookie関連ロジック削除、`UsageAPIClient()` を引数なしで初期化
- gui.py: Cookie/セットアップウィザードUI削除、OAuth認証情報表示追加、マウスホイールスクロール対応
- icons/gauge.py: 色閾値変更（COLOR_ORANGE→COLOR_YELLOW）
- database.py: `insert_usage_snapshot` から `raw_json` パラメータ削除
- test_oauth_api.py 削除

## v2.2.0 (2026-04-10)

### 新機能
- **セットアップウィザード**: 設定タブに「自動セットアップ」ボタン追加
  - browser_cookie3 で Edge → Chrome → Firefox の順にCookie自動取得
  - organizations API で org_id を自動取得
  - Cookie を keyring、org_id を settings.json に自動保存
  - 完了後に Usage API テストを自動実行
- **Cookie期限切れの自動リカバリ**: Usage API が 401/403 を返した際に browser_cookie3 でCookie再取得を自動試行
- **初回起動検出**: org_id未設定＋Cookie未保存の場合、設定タブを自動表示し「自動セットアップ」ボタンを赤色で強調

### 内部改善
- usage_api.py: `auto_get_cookies()`, `fetch_organizations()`, `cookies_to_string()` 関数追加。`set_cookies_from_dict()`, `clear_cookies()` メソッド追加
- main.py: `_auto_setup()` セットアップウィザードコールバック追加。`_fetch_and_update_usage()` にCookie自動リカバリロジック追加
- gui.py: `_run_auto_setup()`, `update_setup_status()`, `on_setup_complete()`, `show_setup_needed()` メソッド追加。手動Cookie入力に「通常は自動セットアップをお使いください」ラベル追加
- requirements.txt: `browser_cookie3>=0.20.0`, `keyring>=25.0.0` 追加

## v2.1.0 (2026-04-10)

### セキュリティ改善
- Cookie保存をsettings.json平文からkeyring（Windows Credential Manager）暗号化保存に変更。サービス名 "ClaudeUsageTracker"、キー名 "session_cookie"
- usage_snapshotテーブルからraw_jsonカラムを廃止（APIレスポンス生データの保存を中止）
- .gitignore作成（data/, logs/, __pycache__/, .claude/, *.pyc 除外）

### 表示修正
- B-5: ポップアップ・ツールチップ・設定タブから金額表示（$表記）をすべて廃止。追加使用量はutilization %表示に統一。is_enabled=falseのときは追加使用量の行自体を非表示
- F-14: トレイアイコン3パターン表示切り替え実装。(1)セッション残あり→青系ゲージ、(2)セッション使い切り+追加ON→黄緑系ゲージ、(3)セッション使い切り+追加OFF→赤バツ。色閾値変更: >50%/20%。点滅閾値変更: ≤10%/5%
- F-15: 設定タブのマウスホイールスクロール対応（Canvas上でMouseWheelイベントバインド）

### GUI改善
- ウィンドウ起動サイズを1100x750に拡大（config.py MIN_WIDTH/MIN_HEIGHT）

### 内部改善
- config.py: SESSION_KEY廃止、load_cookie()/save_cookie()追加（keyring経由）、KEYRING_SERVICE/KEYRING_KEY定数追加
- database.py: insert_usage_snapshotからraw_jsonパラメータ削除、マイグレーションからraw_json除外
- usage_api.py: extra_usage_is_enabled, extra_usage_utilをパース結果に追加
- icons/gauge.py: 色閾値変更（≥55%/25%→>50%/>20%）、COLOR_YELLOW→COLOR_ORANGEに変更
- main.py: _update_tray_from_data()で3パターン分岐、_ensure_usage_client()をkeyring経由に変更、DB保存からraw_json削除
- gui.py: Cookie保存/読み込みをkeyring経由に変更

## v2.0.0 (2026-04-10)

### Phase 2: Usage API 連携

#### 新機能
- Usage API クライアント実装（usage_api.py 新規作成）
  - browser_cookie3 で Edge/Chrome の sessionKey Cookie を自動取得
  - `https://claude.ai/api/organizations/{org_id}/usage` へ定期ポーリング
  - レスポンスの柔軟なパース（フィールド名自動検出、0-1→0-100%正規化）
  - Cookie有効期限切れ時の自動再取得
- usage_snapshot テーブルへのデータ保存（five_hour_resets_at, seven_day_resets_at, raw_json カラム追加）
- Usage API ポーリングスレッド（デフォルト2分間隔、設定タブから変更可能）
- F-5: トレイアイコン左クリックでポップアップ表示
  - ダークテーマのボーダーレスウィンドウ（画面右下に出現）
  - セッション(5h)使用率、週間使用率、Sonnet使用率、追加使用量を表示
  - 使用率に応じた色分け（緑/黄/赤）
  - リセットまでの残り時間表示
  - 8秒自動閉じ + フォーカス喪失で閉じ
  - 「ダッシュボードを開く」リンク付き
- F-6: トレイアイコンのツールチップにリアルデータ表示
  - Usage APIデータ取得後「セッション: ○○% | 週間: ○○% | $○○」形式で表示
- 設定タブに Usage API セクション追加
  - Organization ID 入力・保存
  - API ポーリング間隔選択（1分/2分/3分/5分）
  - 「Usage API テスト」ボタン（Cookie取得→API呼び出し→結果表示）
  - 接続状態・最新データの表示

#### バグ修正
- B-2: scanner.py の差分スキャンで tool_use が解析されないことがある問題を修正
  - 根本原因: テキストモード(`open("r")`)での `fp.seek(byte_position)` が Windows の `\r\n` 変換でバイト位置とずれる可能性
  - 修正: バイナリモード(`open("rb")`)で読み込み→手動デコードに変更

#### 内部改善
- config.py: `USAGE_API_INTERVAL_SECONDS`, `USAGE_API_ENABLED`, `FONT_SMALL` 追加。settings.jsonに永続化
- database.py: `insert_usage_snapshot()`, `query_latest_usage_snapshot()`, `query_usage_snapshots()` 追加。usage_snapshotテーブルに `five_hour_resets_at`, `seven_day_resets_at`, `raw_json` カラム追加
- main.py: `_usage_api_loop()` ポーリングスレッド追加。`_show_usage_popup()` / `_create_tray_popup()` F-5ポップアップ実装。`_update_tray_tooltip()` F-6ツールチップ実装。`_test_usage_api()` テストコールバック追加。トレイメニューに「使用量を表示」項目追加
- gui.py: 設定タブにUsage APIセクション追加。`set_usage_api_test_callback()`, `update_usage_status()` メソッド追加。設定タブにスクロール対応追加
- usage_api.py: 新規作成（UsageAPIClient クラス）
- requirements.txt: `browser_cookie3>=0.20.0`, `requests>=2.28.0` 追加

## v1.2.2 (2026-04-10)

### 改善
- config.py: `PROJECTS_DIR` のハードコードパス(`C:\Users\PCowner\.claude\projects`)を `Path.home() / ".claude" / "projects"` に変更。誰のPCでも動作するようになった
- config.py: Phase 2用 `ORG_ID` 設定を追加。settings.jsonに永続化。設定タブから入力・保存可能
- gui.py: 設定タブに Organization ID 入力欄を追加

## v1.2.1 (2026-04-10)

### 新機能
- F-4/F-7/F-13: トレイアイコンをタスクマネージャーCPU使用率風の縦バー10段ブロックゲージに刷新。段数マッピング（100-95→10段〜1-15未満→1段）、0%=赤バツ印
- F-4/F-7: トレイアイコン点滅機能実装。15%未満→1.5秒間隔ゆっくり点滅、5%未満→0.5秒間隔早い点滅。専用スレッド(_tray_blink_loop)で動作
- F-12: 起動時のCMDウィンドウを非表示化（ctypes.ShowWindow SW_HIDE）
- アイコン生成コードを`icons/gauge.py`に分離、参照画像を`icons/`フォルダに格納
- `icons/test_tray.py`: トレイアイコン動作確認ツール（スライダー+数値入力+点滅テスト）

### 内部改善
- icons/gauge.py: ゲージ生成モジュール新規作成（_get_lit_count段数マッピング、_draw_cross赤バツ印、make_gauge_icon関数）
- main.py: 旧アイコン生成コード削除、icons.gauge.make_gauge_iconを使用。ctypesをファイル先頭でimportに統一
- main.py: update_tray_icon()メソッド追加（Phase 2でUsage APIから残量%を受け取りアイコン・ツールチップを更新）

## v1.2.0 (2026-04-10)

### 新機能
- F-8: 期間選択UIを刷新。PeriodSelector共通コンポーネント（period_selector.py新規作成）。プリセットボタン（今日/1週間/1ヶ月/全期間/カスタム）＋カレンダー入力（tkcalendar DateEntry＋スピンボックス時分）。ダッシュボード上部サマリー・グラフ・円グラフ・直近メッセージすべて期間連動
- F-9: 「プロジェクト別」タブを「分析」タブに拡張。ttk.Comboboxで仕訳軸切替（プロジェクト別/アクション別）。プロジェクト外をグレーバー＋axhline破線セパレータで最下部に分離表示。アクション別はtool_name単位でコスト降順＋バーラベルに「$12.34 (142回)」形式
- F-10: 設定タブからスキャン間隔を変更可能に（10秒/30秒/1分/2分/5分）。デフォルト30秒。data/settings.jsonに永続化。1秒刻みループで間隔変更即反映
- F-11: トレイメニューから「今すぐスキャン」を削除し「ダッシュボードを開く」「終了」の2項目に簡素化

### 内部改善
- period_selector.py: PeriodSelector共通コンポーネント新規作成（ダッシュボード・分析・アクティビティで共通利用）
- database.py: 全クエリをsince/until範囲指定方式に統一。_build_range_clause()ヘルパー追加。query_tool_stats()新規追加（アクション別集計）。旧_period_since()廃止
- charts.py: make_tool_bar_chart()新規追加。make_project_bar_chart()にプロジェクト外分離表示追加。make_model_pie_chart()にtitleパラメータ追加
- config.py: load_settings()/save_settings()追加。SETTINGS_PATH追加。デフォルトスキャン間隔を300→30秒に変更
- main.py: バックグラウンドスキャンループを1秒刻みに変更（間隔変更即反映）
- requirements.txt: tkcalendar>=1.6.1 追加

## v1.1.0 (2026-04-10)

### バグ修正
- B-1: ダッシュボードの入力トークン数にcache_creation_tokens + cache_read_tokensを合算するよう修正
- B-3: アクティビティログの子要素にメッセージ別トークン数（入力/出力）・コストを表示するよう修正
- B-4: 全画面の時刻表示をUTCからJST（UTC+9）に変換。「今日」フィルターもJST基準に修正

### 新機能
- F-1: アクティビティログのヘッダークリックで昇順・降順ソート切替（コスト列でソートして重いアクション特定が可能）
- F-2: ダッシュボードの時系列グラフに期間フィルター追加（直近24時間/1週間/1ヶ月/全期間）。1週間以上は日別グラフに自動切替
- F-3: 直近メッセージの表示件数を6件→50件に拡大、スクロール対応（Treeview height=10）

### 内部改善
- database.py: `utc_to_jst_str()` ヘルパー追加、`_period_since()` にJST基準の時刻計算を実装
- database.py: `query_activity_log()` がメッセージ別トークン・コスト・ツール情報を返すよう構造変更
- database.py: `query_hourly_tokens()` が期間文字列を受け付け、JST時間でグループ化するよう変更
- charts.py: `make_hourly_bar_chart()` にtitleパラメータ追加、X軸ラベルを時間/日単位で自動フォーマット

## v1.0.0 (2026-04-10)

### 新機能
- Phase 1 初回リリース
- Claude Code JSONL ログの差分スキャン・SQLite保存
- ダッシュボードタブ（時系列棒グラフ・モデル別円グラフ・直近メッセージ一覧）
- プロジェクト別タブ（横棒グラフ・期間フィルター）
- アクティビティログタブ（Treeview・展開可能・ツール詳細）
- 設定タブ（スキャンパス情報・CSVエクスポート・ログフォルダを開く）
- システムトレイ常駐（pystray）：GUIを閉じてもトレイに残る
- バックグラウンド差分スキャン（5分間隔）
- 起動時バックグラウンドスキャン（GUIは即座に表示）
- ステータスバーにスキャン進捗表示

### 設計・データ
- scanner.py: tool_useはassistant行のcontent[]から取得（独立行ではない）
- 料金テーブル更新: Opus 4.6 $5/$25、Sonnet 4.6 $3/$15、Haiku 4.5 $1/$5
- feasibility_report.md に追加検証結果を追記（tool_use構造・料金確認）
