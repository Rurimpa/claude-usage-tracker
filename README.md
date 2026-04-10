# Claude Usage Tracker

Claude Code のトークン消費量・セッション残量をリアルタイムで可視化する Windows デスクトップアプリ。

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6)
![License](https://img.shields.io/badge/License-MIT-green)

## 特徴

- **セットアップ不要** — Claude Code にログイン済みなら起動するだけで動作
- **リアルタイム監視** — セッション残量・週間使用率をシステムトレイに常時表示
- **トークン消費分析** — プロジェクト別・アクション別にコストを可視化
- **10段ゲージ** — タスクマネージャー風のトレイアイコンで残量がひと目でわかる

## 動作イメージ

| ダッシュボード | トレイアイコン | ポップアップ |
|:---:|:---:|:---:|
| 時系列グラフ・円グラフ・メッセージ一覧 | 10段縦バーゲージ | 左クリックで使用量表示 |

## 必要環境

- **Windows 10/11**
- **Claude Code** がインストール済みで `claude login` 完了していること
- Python 3.10 以上（ソースから実行する場合）

## インストール

### インストーラー（推奨）

[Releases](../../releases) から `ClaudeUsageTracker_Setup_vX.X.X.exe` をダウンロードして実行。
管理者権限は不要です（`%LOCALAPPDATA%\ClaudeUsageTracker` にインストール）。

### ソースから実行

```bash
git clone https://github.com/Rurimpa/claude-usage-tracker.git
cd claude-usage-tracker
pip install -r requirements.txt
python main.py
```

## 仕組み

### データソース

| ソース | 取得方法 | 内容 |
|--------|---------|------|
| Claude Code ローカルログ | `~/.claude/projects/**/*.jsonl` を自動スキャン | プロジェクト別トークン消費・アクション履歴 |
| Anthropic Usage API | `~/.claude/.credentials.json` の OAuth トークンで自動認証 | セッション残量・週間使用率・追加使用量 |

### 認証

ブラウザでのCookie取得やAPI キーの入力は一切不要です。
Claude Code のログイン時に生成される OAuth トークン（`~/.claude/.credentials.json`）を自動で読み取ります。

## 機能一覧

### ダッシュボード
- 期間別サマリー（入力/出力トークン・コスト）
- 時系列トークン消費グラフ（時間別・日別）
- モデル別円グラフ
- 直近50件メッセージ一覧
- 期間選択: プリセット（今日/1週間/1ヶ月/全期間）+ カレンダー入力

### 分析タブ
- プロジェクト別コスト横棒グラフ（プロジェクト外を分離表示）
- アクション別コスト横棒グラフ（Read/Write/Bash等）
- 仕訳軸をドロップダウンで切り替え

### アクティビティログ
- Claude Code の全アクションを展開・折りたたみ表示
- ツール名・対象ファイル・トークン数・コストを一覧
- ヘッダークリックでソート

### トレイアイコン
- タスクマネージャー風 10段縦バーゲージ
- セッション残量に応じて色が変化（青→オレンジ→赤→点滅）
- セッション使い切り時は追加使用量に自動切替（黄緑系）
- 左クリックでポップアップ、ホバーでツールチップ

### 設定
- スキャン間隔変更（10秒〜5分）
- Usage API ポーリング間隔変更
- OAuth 認証ステータス表示
- CSV エクスポート

## コスト概算

ダッシュボードに表示されるコストは以下の料金テーブルに基づく概算値です。

| モデル | 入力 ($/MTok) | 出力 ($/MTok) |
|--------|:---:|:---:|
| Opus 4.6 | $5 | $25 |
| Sonnet 4.6 | $3 | $15 |
| Haiku 4.5 | $1 | $5 |

## 注意事項

- このツールが使用する Usage API エンドポイント（`api.anthropic.com/api/oauth/usage`）は Anthropic の未公開 API です。予告なく変更・廃止される可能性があります
- Claude Code のローカルログ解析機能は API に依存せず、常に動作します
- 表示されるコストは概算値であり、実際の請求額とは異なる場合があります

## ビルド

```bash
# PyInstaller でビルド
build.bat

# Inno Setup でインストーラー作成（Inno Setup 必要）
# installer.iss を Inno Setup で開いてコンパイル
```

## ライセンス

MIT License
