"""Usage Tracker - Settings and Constants"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# === Version ===
VERSION = "3.5.4"

# === Language ===
LANGUAGE = "en"  # "en" or "ja"

# === Path settings (user-independent) ===
PROJECTS_DIR = Path.home() / ".claude" / "projects"
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "usage.db"
LOG_DIR = BASE_DIR / "logs"
SETTINGS_PATH = BASE_DIR / "data" / "settings.json"

# === Scan settings ===
SCAN_INTERVAL_SECONDS = 30

# === Phase 2 settings ===
ORG_ID = ""
USAGE_API_INTERVAL_SECONDS = 120
USAGE_API_ENABLED = True

# === GUI settings ===
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

# === DB Retention settings ===
RETENTION_DAYS_SNAPSHOT = 30
RETENTION_DAYS_TOKEN_LOG = 90
RETENTION_DAYS_LOG_FILES = 30

# === Pricing table (USD/1M tokens) ===
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

# === Model display names ===
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
        return "Unknown"
    if model in MODEL_DISPLAY:
        return MODEL_DISPLAY[model]
    for key, display in MODEL_DISPLAY.items():
        if model.startswith(key):
            return display
    return model


# === Remaining color (gauge.py 準拠) ===
# session >50%: 青, extra >50%: 緑, >20%: 黄, ≤20%: 赤
REMAINING_COLOR_BLUE = "#2980b9"
REMAINING_COLOR_GREEN = "#2ecc71"
REMAINING_COLOR_YELLOW = "#f0c800"
REMAINING_COLOR_RED = "#e74c3c"


def get_remaining_color(remaining_pct: float, mode: str = "session") -> str:
    """残量%とモード（session/extra）に応じた色を返す（gauge.py 準拠）。"""
    if remaining_pct > 50:
        return REMAINING_COLOR_BLUE if mode == "session" else REMAINING_COLOR_GREEN
    elif remaining_pct > 20:
        return REMAINING_COLOR_YELLOW
    else:
        return REMAINING_COLOR_RED


def get_session_pace_color(remaining_pct: float, elapsed_pct: float) -> str:
    """セッション消費ペースに基づく色を返す（時計盤の弧用）。

    Args:
        remaining_pct: 実際の残量% (100 - five_hour_util)
        elapsed_pct: 経過% (経過時間 / 5時間 * 100)

    Returns:
        色コード (#2980b9=青, #f0c800=黄, #e74c3c=赤)
    """
    expected_remaining = 100.0 - elapsed_pct
    if expected_remaining <= 0:
        # セッション終了間際: 残量があれば青、なければ赤
        return REMAINING_COLOR_BLUE if remaining_pct > 0 else REMAINING_COLOR_RED
    pace_ratio = remaining_pct / expected_remaining
    if pace_ratio >= 1.10:
        return REMAINING_COLOR_BLUE   # 余裕あり
    elif pace_ratio >= 0.95:
        return REMAINING_COLOR_YELLOW  # 注意
    else:
        return REMAINING_COLOR_RED     # 消費ペースが速すぎる


# === Chart colors ===
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


# === Settings persistence (non-sensitive data only) ===

# === Mini widget settings ===
MINI_WIDGET_SIZE = 200


def load_settings() -> None:
    global SCAN_INTERVAL_SECONDS, ORG_ID, USAGE_API_INTERVAL_SECONDS, USAGE_API_ENABLED, LANGUAGE, MINI_WIDGET_SIZE
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
            LANGUAGE = str(data.get("language", "en"))
            MINI_WIDGET_SIZE = int(data.get("mini_widget_size", 200))
            MINI_WIDGET_SIZE = max(120, min(400, MINI_WIDGET_SIZE))
            logger.info("Settings loaded: scan=%ds, ORG_ID=%s, API=%ds",
                        SCAN_INTERVAL_SECONDS,
                        ORG_ID[:8] + "..." if ORG_ID else "(auto)",
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
            "language": LANGUAGE,
            "mini_widget_size": MINI_WIDGET_SIZE,
        }
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Settings saved: %s", SETTINGS_PATH)
    except Exception as e:
        logger.error("Settings save error: %s", e)
