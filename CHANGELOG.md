# CHANGELOG

## v3.5.4 (2026-04-13)

### UI改善
- **ポップアップのフォントサイズ+2pt**: ラベル9→11pt、値10→12pt、リセット時間8→10pt、フッター8→10pt。ウィンドウサイズ340x520→360x560
- **ミニウィジェットのフォントサイズ+2pt**: `max(8, sz//18)` → `max(10, sz//16)`。デフォルト200pxで12pt、最小120pxで10pt
- **ミニウィジェットのテキスト左右分離レイアウト**: ラベル（Session:等）を左寄せ、数値（27%等）をbold右寄せに変更（ポップアップと同じrow形式、リセット時間は省略）

### 内部改善
- config.py: `VERSION`を3.5.4に更新
- main.py: `_create_tray_popup()`のフォントサイズ+2pt。`_create_mini_widget()`のテキスト部を左右分離レイアウト（ラベルLabel+値Label in row Frame）に全面書き換え。`_resize_mini_widget()`のフォントリサイズをラベル+値の2要素構成に更新。`_update_widget_text()`を左右分離ラベル構造に全面書き換え

## v3.5.3 (2026-04-13)

### UI改善
- **ミニウィジェットのレイアウト改善**: キャラアイコン→時計盤→テキスト情報の縦配置に変更。外側パディング追加（ウィンドウ端から最低6px余白）
- **ミニウィジェットのフォントサイズ拡大**: `max(7, sz//22)` → `max(8, sz//18)`。デフォルト200pxで11pt、最小120pxでも8pt確保
- **ミニウィジェットのラベルi18n対応**: 160px以上で「Session:」「週間:」等のフルラベル表示、160px未満で「S:」「W:」「E:」に自動フォールバック

### 内部改善
- config.py: `VERSION`を3.5.3に更新
- main.py: `_create_mini_widget()`を縦配置（キャラ→時計→テキスト）+余白付きに全面書き換え。`_resize_mini_widget()`で外側パディング・キャラ・フォント・ウィンドウサイズ連動更新。`_update_widget_text()`にサイズ連動ラベル切替ロジック追加
- locale/en.json, locale/ja.json: `widget_session`, `widget_weekly`, `widget_extra` キー追加

## v3.5.2 (2026-04-13)

### UI改善
- **ミニウィジェットにテキスト情報追加**: 時計盤の下にセッション残量%(S)・週間残量%(W)・追加使用量%(E)をコンパクト表示。色はget_remaining_colorで残量に応じて自動変化
- **ミニウィジェットにキャラアイコン追加**: icons/tss.pngのキャラクター画像をテキスト左側に配置
- **ミニウィジェットのホイール拡縮にテキスト・キャラ追従**: フォントサイズ・キャラ画像サイズがウィジェットサイズに比例して変化
- **ミニウィジェットのデフォルトサイズ変更**: 150→200。最小サイズ100→120に変更（テキスト可読性確保）

### 内部改善
- config.py: `VERSION`を3.5.2に更新。`MINI_WIDGET_SIZE`デフォルト200、最小クランプ120
- main.py: `_create_mini_widget()`にテキスト情報・キャラアイコン追加。`_resize_mini_widget()`新規追加（ホイール拡縮でキャラ・フォント・フレーム連動リサイズ）。`_update_widget_text()`新規追加。`_update_mini_widget()`にテキスト更新追加

## v3.5.1 (2026-04-13)

### バグ修正
- **時計盤の弧描画ロジック修正**: 弧が「短針の現在位置→リセット時刻位置」の誤ったロジックだったのを修正。正しくは弧の角度 = 残量% × 150°（5時間 = 12h時計上で150°）、弧の終端 = リセット時刻位置、弧の始端 = リセット時刻から残量時間分だけ反時計回りに戻った位置

### UI改善
- **ポップアップを縦長レイアウトに変更**: トレイ左クリックポップアップを420x300横長→340x520縦長に変更
- **ポップアップにテキスト情報を集約**: 時計盤の下にセッション残量%・リセット時刻、週間残量%・リセット時刻、Sonnet残量%、追加使用量（有効時のみ）を表示
- **ポップアップにキャラアイコン追加**: icons/tss.pngのキャラクター画像を時計盤の右隣に100x100で配置

### 内部改善
- config.py: `VERSION`を3.5.1に更新
- gui.py: `draw_clock_on_canvas()`の弧描画ロジックを「残量%×150°、リセット時刻終端」方式に修正
- main.py: `_create_tray_popup()`を縦長レイアウト・テキスト情報・キャラアイコン追加で全面書き換え

## v3.5.0 (2026-04-13)

### UI改善
- **ターミナル(py.exe)ウィンドウ非表示強化**: ShowWindow(SW_HIDE)に加え`FreeConsole()`を呼び出し、py.exeのコンソールが残らないよう確実に非表示化
- **ミニウィジェット・ポップアップの時計盤表示**: 縦メーター(gauge)表示を廃止し、残量タブと同じアナログ時計盤に変更。ミニウィジェットはCanvasで描画、ポップアップも左側に時計盤を配置
- **分針の太さを短針と統一**: 時計盤の長針(分針)の太さを短針(時針)と同じwidthに変更（サイズ比例で自動調整）
- **ミニウィジェットのホイール拡縮**: マウスホイール上=拡大、下=縮小。100x100〜400x400の範囲で20px刻み。サイズはsettings.jsonに保存・復元
- **ミニウィジェットのクリック動作変更**: 左クリック=Usage APIを即座にポーリング（3秒連打防止）、右クリック=閉じる。ドラッグ移動も維持
- **時計盤の弧の色をペース比率で決定**: セッション残量の弧の色を、経過時間に対する消費ペース比率で青/黄/赤に自動判定。`config.get_session_pace_color()`で統一。週間ミニグラフの色判定ロジックと一貫性を保つ
- **時計盤描画の共通関数化**: `gui.draw_clock_on_canvas()`として共通関数化し、残量タブ・ミニウィジェット・ポップアップすべてで同一ロジックを使用。サイズに応じてフォント・目盛り・針の太さが自動スケール

### バグ修正
- **DeprecationWarning修正**: `datetime.utcnow()`を`datetime.now(timezone.utc).replace(tzinfo=None)`に全ファイルで置換（main.py, gui.py, database.py, usage_api.py, period_selector.py）

### 内部改善
- config.py: `VERSION`を3.5.0に更新。`get_session_pace_color()`関数追加。`MINI_WIDGET_SIZE`設定追加（settings.jsonに永続化）
- gui.py: `draw_clock_on_canvas()`モジュールレベル共通関数追加。`_draw_clock_face()`を共通関数のラッパーに簡素化
- main.py: ミニウィジェットを時計盤Canvas方式に全面書き換え。ポップアップも時計盤Canvas方式に変更。`FreeConsole()`追加

## v3.4.0 (2026-04-11)

### UI改善（追加）
- **残量タブ2カラムレイアウト**: gridベースの2×2構成に全面変更。上段左=時計盤+セッション情報、上段右=ミニグラフ(高さ200px)+週間情報+ペース警告、下段左=追加使用量、下段右=週間Sonnet。上下段を区切り線で分離。ウィンドウリサイズ時に右カラムが追従(`columnconfigure weight=1`)
- **セッション枯渇時の表示切替**: five_hour_util>=100時にセッションテキストを「セッション使い切り」(赤)に変更し、追加使用量のフォントを20ptに拡大して目立たせる。追加使用量が無効の場合は「未使用」と表示
- **最終更新時刻表示**: 残量タブ上部バー左側にUsage API最終更新時刻(HH:MM:SS)を表示
- **ミニグラフ拡大・改善**: Canvas高さ200px、幅は右カラム追従。フォント10pt化。Y軸・X軸・ラベルすべて見やすく拡大。基準ラインを#AAA太線(width=2)に強化。「今」の縦点線に上部ラベル追加
- **ツールチップ罫線フォーマット**: 罫線(━)で上下を囲み、各項目間に空行を挿入して読みやすく改善。128文字超過時は段階的に省略
- **ツールチップWeekly日本語化**: ハードコード`"Weekly:"`を`tray_tooltip_weekly`キーに変更。日本語: `"週間: 残りXX%"`

### バグ修正（追加）
- **時間表示バグ修正**: `_format_reset_digital()` で hours=0 のとき「あと0時間XX分」と表示されるバグを修正。「XX分後リセット」のみ表示するように変更。ポップアップ側 `_format_reset_time()` は既にh>0で正しく分岐済みだが、古い `__pycache__` が残っていると旧コードが実行されるため、キャッシュクリアで解消
- **色体系の統一**: 残量タブ・ポップアップの色がトレイアイコン（gauge.py）と不一致だった問題を修正。session>50%=青(#2980b9)、extra>50%=緑(#2ecc71)、>20%=黄(#f0c800)、≤20%=赤(#e74c3c)に統一。`config.get_remaining_color()` 共通関数を追加
- **分針の太さ修正**: 時計盤の分針が細すぎて秒針に見えた問題を修正（width=2→3、時針はwidth=4→5）
- **残量タブのレイアウト最適化**: 時計盤を300x300に拡大、キャラクター画像を120x120に拡大して右側上部に配置、全体を中央配置に変更
- **ポップアップのリセット時間テキスト切れ修正**: `row("", rs)` の左ラベル`width=18`が幅を食い、リセット時間テキストの先頭が切れるバグを修正。`sub_row()` ヘルパーで左ラベルなし全幅右寄せ表示に変更

### 新機能
- **残量タブ新設**: デフォルト表示タブとして追加。アナログ時計盤（12時間制Canvas描画）でセッション5hリセットまでの弧を色分け表示。キャラクター画像配置。セッション/週間/Sonnet/追加使用量の残量%・リセット時刻をテキスト表示
- **週間消費ペースミニグラフ**: 残量タブ下部に400x80 Canvasで基準ライン（均等消費）と実消費ラインを描画。色は基準との比較で青/黄/赤に自動判定。usage_snapshotの履歴データをプロット。ペース警告テキスト付き
- **残量タブ更新ボタン**: 残量タブ右上に更新ボタン追加。クリックでUsage APIを即座にポーリング（3秒連打防止付き）
- **ツールチップ改善**: 各項目を改行で分離し読みやすく。週間残量も表示
- **DBローテーション**: 起動時に古いレコードを自動削除（usage_snapshot: 30日、token_log: 90日、tool_log: 孤児レコード、ログファイル: 30日）。削除後にVACUUM実行
- **設定タブにDB容量表示**: データベースサイズ（MB）表示と「データベースを最適化」ボタン（手動VACUUM）追加

### バグ修正・改善
- **時間表示バグ修正**: `_format_reset_time()` で h=0 のとき「0時間XX分後リセット」と表示されないことを確認・保証
- **トレイ右クリックメニュー文言変更**: 「使用量を表示」→「残量を表示」(ja) / "Show Usage" → "Show remaining" (en)
- **ポップアップをクリックで閉じる**: トレイポップアップ内の任意の場所をクリックで閉じる。auto_closeタイマーもキャンセル
- **アクティビティ閲覧中のUI更新抑制**: アクティビティタブでTreeviewフォーカスまたはスクロール中はUsage APIデータ更新をバックグラウンド保持し、タブ切替時に反映

### 内部改善
- config.py: `RETENTION_DAYS_SNAPSHOT`, `RETENTION_DAYS_TOKEN_LOG`, `RETENTION_DAYS_LOG_FILES` 定数追加
- database.py: `cleanup_old_records()`, `vacuum_db()`, `get_db_size_mb()` 関数追加
- gui.py: `_build_remaining_tab()`, `_draw_clock_face()`, `update_remaining_tab()`, `_is_user_browsing_activity()`, `_optimize_db()` メソッド追加
- main.py: `database.cleanup_old_records()` を起動時に呼び出し。Usage API結果を残量タブにも反映
- locale/en.json, locale/ja.json: 残量タブ・DB最適化・時計関連のi18nキー追加

## v3.1.0 (2026-04-10)

### 新機能: 多言語対応（i18n）
- English / 日本語を設定タブのドロップダウンで切替可能
- i18n.py モジュール新規作成（キーベースの翻訳文字列管理）
- locale/en.json, locale/ja.json に全UI文字列を外出し
- gui.py, main.py, period_selector.py の全ハードコード文字列を i18n.t() に置換
- ポップアップ・ツールチップ・トレイメニューも完全i18n対応
- 言語変更時は再起動促すダイアログ表示
- config.py に LANGUAGE 設定追加（settings.jsonに永続化）
- README.md を英語メインに変更、README_ja.md を日本語版として新規作成

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
