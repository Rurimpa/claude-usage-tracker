"""Usage Tracker - 險ｭ螳壹・螳壽焚"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# === 繝舌・繧ｸ繝ｧ繝ｳ ===
VERSION = "3.2.0"

# === 險隱櫁ｨｭ螳・===
LANGUAGE = "en"  # "en" or "ja"

# === 繝代せ險ｭ螳夲ｼ医Θ繝ｼ繧ｶ繝ｼ髱樔ｾ晏ｭ假ｼ・===
PROJECTS_DIR = Path.home() / ".claude" / "projects"
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "usage.db"
LOG_DIR = BASE_DIR / "logs"
SETTINGS_PATH = BASE_DIR / "data" / "settings.json"

# === 繧ｹ繧ｭ繝｣繝ｳ險ｭ螳・===
SCAN_INTERVAL_SECONDS = 30  # 繝・ヵ繧ｩ繝ｫ繝・0遘・
# === Phase 2逕ｨ險ｭ螳・===
ORG_ID = ""  # OAuth API縺九ｉ閾ｪ蜍募叙蠕励ょ叙蠕励〒縺阪↑縺・ｴ蜷医・繝輔か繝ｼ繝ｫ繝舌ャ繧ｯ
USAGE_API_INTERVAL_SECONDS = 120  # Usage API繝昴・繝ｪ繝ｳ繧ｰ髢馴囈・医ョ繝輔か繝ｫ繝・蛻・ｼ・USAGE_API_ENABLED = True  # Usage API繝昴・繝ｪ繝ｳ繧ｰ繧呈怏蜉ｹ縺ｫ縺吶ｋ縺・
# === GUI險ｭ螳夲ｼ・LAUDE.md ﾂｧ18貅匁侠・・===
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

# === 譁咎≡繝・・繝悶Ν・・SD/1M繝医・繧ｯ繝ｳ縲・026-04-10遒ｺ隱搾ｼ・===
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

# === 繝｢繝・Ν陦ｨ遉ｺ蜷・===
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
        return "荳肴・"
    if model in MODEL_DISPLAY:
        return MODEL_DISPLAY[model]
    for key, display in MODEL_DISPLAY.items():
        if model.startswith(key):
            return display
    return model


# === 繧ｰ繝ｩ繝戊牡 ===
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


# === 險ｭ螳壹・豌ｸ邯壼喧・磯撼讖溷ｯ・ュ蝣ｱ縺ｮ縺ｿ・・===

def load_settings() -> None:
    global SCAN_INTERVAL_SECONDS, ORG_ID, USAGE_API_INTERVAL_SECONDS, USAGE_API_ENABLED, LANGUAGE
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
            logger.info("險ｭ螳夊ｪｭ縺ｿ霎ｼ縺ｿ螳御ｺ・ 繧ｹ繧ｭ繝｣繝ｳ髢馴囈=%d遘・ ORG_ID=%s, API髢馴囈=%d遘・,
                        SCAN_INTERVAL_SECONDS,
                        ORG_ID[:8] + "..." if ORG_ID else "(閾ｪ蜍募叙蠕・",
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
        }
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("險ｭ螳壻ｿ晏ｭ伜ｮ御ｺ・ %s", SETTINGS_PATH)
    except Exception as e:
        logger.error("險ｭ螳壻ｿ晏ｭ倥お繝ｩ繝ｼ: %s", e)
