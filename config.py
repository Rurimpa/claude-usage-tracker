"""Usage Tracker - 設定・定数"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# === バージョン ===
VERSION = "3.0.0"

# === パス設定（ユーザー非依存） ===
PROJECTS_DIR = Path.home() / ".claude" / "projects"
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "usage.db"
LOG_DIR = BASE_DIR / "logs"
SETTINGS_PATH = BASE_DIR / "data" / "settings.json"

# === スキャン設定 ===
SCAN_INTERVAL_SECONDS = 30  # デフォルト30秒

# === Phase 2用設定 ===
ORG_ID = ""  # OAuth APIから自動取得。取得できない場合のフォールバック
USAGE_API_INTERVAL_SECONDS = 120  # Usage APIポーリング間隔（デフォルト2分）
USAGE_API_ENABLED = True  # Usage APIポーリングを有効にするか

# === GUI設定（CLAUDE.md §18準拠） ===
FONT_FAMILY = "Meiryo"
FONT_SIZE = 10
FONT = (FONT_FAMILY, FONT_SIZE)
FONT_BOLD = (FONT_FAMILY, FONT_SIZE, "bold")
FONT_LARGE = (FONT_FAMILY, 13, "bold")
FONT_SMALL = (FONT_FAMILY, 8)
MIN_WIDTH = 1100
MIN_HEIGHT = 750
BG_COLOR = "#f0f0f0"
ACCENT_COLOR = "#1a6b9a"

# === 料金テーブル（USD/1Mトークン、2026-04-10確認） ===
PRICING = {
    "claude-opus-4-6": {
        "input": 5.00,
        "output": 25.00,
        "cache_write_5m": 6.25,
        "cache_write_1h": 10.00,
        "cache_read": 0.50,
    },
    "claude-sonnet-4-6": {
        "input": 3.00,
        "output": 15.00,
        "cache_write_5m": 3.75,
        "cache_write_1h": 6.00,
        "cache_read": 0.30,
    },
    "claude-haiku-4-5": {
        "input": 1.00,
        "output": 5.00,
        "cache_write_5m": 1.25,
        "cache_write_1h": 2.00,
        "cache_read": 0.10,
    },
    "claude-opus-4-5": {
        "input": 15.00,
        "output": 75.00,
        "cache_write_5m": 18.75,
        "cache_write_1h": 18.75,
        "cache_read": 1.875,
    },
    "claude-sonnet-4-5": {
        "input": 3.00,
        "output": 15.00,
        "cache_write_5m": 3.75,
        "cache_write_1h": 6.00,
        "cache_read": 0.30,
    },
    "default": {
        "input": 3.00,
        "output": 15.00,
        "cache_write_5m": 3.75,
        "cache_write_1h": 6.00,
        "cache_read": 0.30,
    },
}

# === モデル表示名 ===
MODEL_DISPLAY = {
    "claude-opus-4-6": "Opus 4.6",
    "claude-sonnet-4-6": "Sonnet 4.6",
    "claude-haiku-4-5": "Haiku 4.5",
    "claude-opus-4-5": "Opus 4.5",
    "claude-sonnet-4-5": "Sonnet 4.5",
    "claude-haiku-3-5": "Haiku 3.5",
    "claude-opus-4": "Opus 4",
    "claude-sonnet-4": "Sonnet 4",
}


def get_model_display(model: str) -> str:
    if not model:
        return "不明"
    if model in MODEL_DISPLAY:
        return MODEL_DISPLAY[model]
    for key, display in MODEL_DISPLAY.items():
        if model.startswith(key):
            return display
    return model


# === グラフ色 ===
MODEL_COLORS = {
    "claude-opus-4-6": "#c0392b",
    "claude-sonnet-4-6": "#2980b9",
    "claude-haiku-4-5": "#27ae60",
    "claude-opus-4-5": "#e74c3c",
    "claude-sonnet-4-5": "#3498db",
    "default": "#7f8c8d",
}


def get_model_color(model: str) -> str:
    if not model:
        return MODEL_COLORS["default"]
    if model in MODEL_COLORS:
        return MODEL_COLORS[model]
    for key, color in MODEL_COLORS.items():
        if key != "default" and model.startswith(key):
            return color
    return MODEL_COLORS["default"]


def _get_pricing(model: str) -> dict:
    if not model:
        return PRICING["default"]
    if model in PRICING:
        return PRICING[model]
    for key in PRICING:
        if key != "default" and model.startswith(key):
            return PRICING[key]
    return PRICING["default"]


def calc_cost(model: str, input_tokens: int, output_tokens: int,
              cache_creation_tokens: int = 0, cache_read_tokens: int = 0,
              cache_creation_5m: int = 0) -> float:
    p = _get_pricing(model)
    m = 1_000_000
    cache_1h = max(0, cache_creation_tokens - cache_creation_5m)
    cost = (
        input_tokens * p["input"] / m
        + output_tokens * p["output"] / m
        + cache_read_tokens * p["cache_read"] / m
        + cache_creation_5m * p["cache_write_5m"] / m
        + cache_1h * p["cache_write_1h"] / m
    )
    return max(0.0, cost)


# === 設定の永続化（非機密情報のみ） ===

def load_settings() -> None:
    global SCAN_INTERVAL_SECONDS, ORG_ID, USAGE_API_INTERVAL_SECONDS, USAGE_API_ENABLED
    if not SETTINGS_PATH.exists():
        return
    for enc in ("utf-8", "shift-jis", "latin-1"):
        try:
            with open(SETTINGS_PATH, "r", encoding=enc) as f:
                data = json.load(f)
            SCAN_INTERVAL_SECONDS = int(data.get("scan_interval_seconds", 30))
            ORG_ID = str(data.get("org_id", ""))
            USAGE_API_INTERVAL_SECONDS = int(data.get("usage_api_interval_seconds", 120))
            USAGE_API_ENABLED = bool(data.get("usage_api_enabled", True))
            logger.info("設定読み込み完了: スキャン間隔=%d秒, ORG_ID=%s, API間隔=%d秒",
                        SCAN_INTERVAL_SECONDS,
                        ORG_ID[:8] + "..." if ORG_ID else "(自動取得)",
                        USAGE_API_INTERVAL_SECONDS)
            return
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, OSError):
            continue


def save_settings() -> None:
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "scan_interval_seconds": SCAN_INTERVAL_SECONDS,
            "org_id": ORG_ID,
            "usage_api_interval_seconds": USAGE_API_INTERVAL_SECONDS,
            "usage_api_enabled": USAGE_API_ENABLED,
        }
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("設定保存完了: %s", SETTINGS_PATH)
    except Exception as e:
        logger.error("設定保存エラー: %s", e)
