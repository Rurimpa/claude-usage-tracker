"""Usage Tracker - 国際化（i18n）モジュール"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_strings: dict = {}
_current_lang: str = "en"
LOCALE_DIR = Path(__file__).parent / "locale"


def load(lang: str = "en") -> None:
    """指定言語のロケールファイルを読み込む。"""
    global _strings, _current_lang
    _current_lang = lang
    locale_file = LOCALE_DIR / f"{lang}.json"
    if not locale_file.exists():
        logger.warning("ロケールファイルが見つかりません: %s (enにフォールバック)", locale_file)
        locale_file = LOCALE_DIR / "en.json"
    try:
        with open(locale_file, "r", encoding="utf-8") as f:
            _strings = json.load(f)
        logger.info("ロケール読み込み完了: %s (%d キー)", lang, len(_strings))
    except Exception as e:
        logger.error("ロケール読み込みエラー: %s", e)
        _strings = {}


def t(key: str, **kwargs) -> str:
    """翻訳文字列を取得する。{key}形式のプレースホルダーをkwargsで置換。"""
    text = _strings.get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def current_lang() -> str:
    return _current_lang
