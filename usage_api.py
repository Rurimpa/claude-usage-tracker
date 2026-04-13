"""Usage Tracker - OAuth Usage API クライアント（v3.0.0）

~/.claude/.credentials.json の OAuth トークンで Anthropic Usage API を叩く。
curl_cffi / browser_cookie3 / Cookie 手動入力は不要。

エンドポイント:
    GET https://api.anthropic.com/api/oauth/usage
ヘッダー:
    Authorization: Bearer {accessToken}
    anthropic-beta: oauth-2025-04-20
"""
import json
import logging
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"
USAGE_API_URL = "https://api.anthropic.com/api/oauth/usage"
ORGANIZATIONS_URL = "https://api.anthropic.com/api/oauth/organizations"


def load_credentials() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """~/.claude/.credentials.json を読み込む。

    Returns:
        (credentials_dict, error_message)
        成功: ({"accessToken": ..., "subscriptionType": ..., ...}, None)
        失敗: (None, "エラーメッセージ")
    """
    if not CREDENTIALS_PATH.exists():
        return None, ("認証ファイルが見つかりません\n"
                      f"パス: {CREDENTIALS_PATH}\n"
                      "Claude Code をインストールしてログインしてください")

    try:
        with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return None, f"認証ファイル読み込みエラー: {e}"

    oauth = data.get("claudeAiOauth")
    if not oauth or not isinstance(oauth, dict):
        return None, ("claudeAiOauth キーが見つかりません\n"
                      "Claude Code で claude login を実行してください")

    token = oauth.get("accessToken")
    if not token:
        return None, "accessToken が空です。Claude Code で再ログインしてください"

    logger.info("credentials.json 読み込み成功（token=%s..., subscription=%s）",
                token[:20], oauth.get("subscriptionType", "?"))
    return oauth, None


def is_token_expired(credentials: Dict[str, Any]) -> bool:
    """トークンが期限切れかチェックする。"""
    expires_at = credentials.get("expiresAt")
    if not expires_at:
        return False
    now_ms = int(time.time() * 1000)
    return now_ms >= int(expires_at)


def _api_request(url: str, token: str) -> Tuple[Optional[Any], Optional[str], int]:
    """OAuth トークンで API リクエストを送信する。

    Returns:
        (response_data, error_message, status_code)
    """
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("anthropic-beta", "oauth-2025-04-20")
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data, None, resp.status
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")[:200]
        except Exception:
            pass
        return None, f"HTTP {e.code}: {body}", e.code
    except urllib.error.URLError as e:
        return None, f"接続エラー: {e.reason}", 0
    except Exception as e:
        return None, f"通信エラー: {e}", 0


class UsageAPIClient:
    """OAuth Usage API クライアント。"""

    def __init__(self):
        self._credentials: Optional[Dict[str, Any]] = None
        self._last_error: Optional[str] = None
        self._last_fetch_time: Optional[str] = None
        self._last_data: Optional[Dict[str, Any]] = None

    def _load_or_refresh_token(self) -> Optional[str]:
        """トークンを取得する。期限切れなら再読み込み。"""
        if self._credentials and not is_token_expired(self._credentials):
            return self._credentials.get("accessToken")

        # 再読み込み（Claude Code が自動更新するため）
        cred, err = load_credentials()
        if cred is None:
            self._last_error = err
            return None

        self._credentials = cred
        return cred.get("accessToken")

    def get_auth_info(self) -> Dict[str, Any]:
        """認証情報のサマリーを返す（GUI表示用）。"""
        cred, err = load_credentials()
        if cred is None:
            return {"status": "error", "error": err}

        token = cred.get("accessToken", "")
        masked = token[:20] + "..." if len(token) > 20 else token
        return {
            "status": "ok",
            "token_masked": masked,
            "subscription_type": cred.get("subscriptionType", "不明"),
            "rate_limit_tier": cred.get("rateLimitTier", ""),
            "scopes": cred.get("scopes", []),
            "credentials_path": str(CREDENTIALS_PATH),
            "expires_at": cred.get("expiresAt"),
        }

    def fetch_usage(self) -> Optional[Dict[str, Any]]:
        """Usage API からデータを取得しパースして返す。"""
        token = self._load_or_refresh_token()
        if not token:
            return None

        data, err, status = _api_request(USAGE_API_URL, token)

        if status in (401, 403):
            # トークン期限切れの可能性 → 再読み込みしてリトライ
            logger.info("Usage API %d、トークン再読み込みしてリトライ", status)
            self._credentials = None
            token = self._load_or_refresh_token()
            if not token:
                return None
            data, err, status = _api_request(USAGE_API_URL, token)

        self._last_fetch_time = datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"

        if data is None:
            if status in (401, 403):
                self._last_error = "認証エラー: Claude Code で再ログインしてください"
            elif status == 429:
                self._last_error = "レートリミット: しばらく待ってから再試行してください"
            else:
                self._last_error = err
            return None

        logger.info("Usage API レスポンス取得成功（キー: %s）", list(data.keys()))
        self._last_error = None

        parsed = self._parse_usage(data)
        self._last_data = parsed
        return parsed

    def fetch_organizations(self) -> Tuple[Optional[str], Optional[str]]:
        """organizations API から org_id を自動取得する。"""
        token = self._load_or_refresh_token()
        if not token:
            return None, self._last_error

        data, err, status = _api_request(ORGANIZATIONS_URL, token)
        if data is None:
            return None, err

        if isinstance(data, list) and len(data) > 0:
            org = data[0]
            org_id = org.get("uuid") or org.get("id")
            if org_id:
                return str(org_id), None
        elif isinstance(data, dict):
            org_id = data.get("uuid") or data.get("id")
            if org_id:
                return str(org_id), None

        return None, "org_id を自動取得できませんでした"

    def _parse_usage(self, data: dict) -> Dict[str, Any]:
        """API レスポンスをパースする。"""
        result = {
            "five_hour_util": None,
            "seven_day_util": None,
            "seven_day_sonnet_util": None,
            "extra_usage_is_enabled": False,
            "extra_usage_util": None,
            "five_hour_resets_at": None,
            "seven_day_resets_at": None,
        }

        five_hour = data.get("five_hour")
        if isinstance(five_hour, dict):
            result["five_hour_util"] = _safe_float(five_hour.get("utilization"))
            result["five_hour_resets_at"] = five_hour.get("resets_at")

        seven_day = data.get("seven_day")
        if isinstance(seven_day, dict):
            result["seven_day_util"] = _safe_float(seven_day.get("utilization"))
            result["seven_day_resets_at"] = seven_day.get("resets_at")

        seven_day_sonnet = data.get("seven_day_sonnet")
        if isinstance(seven_day_sonnet, dict):
            result["seven_day_sonnet_util"] = _safe_float(seven_day_sonnet.get("utilization"))

        extra_usage = data.get("extra_usage")
        if isinstance(extra_usage, dict):
            result["extra_usage_is_enabled"] = bool(extra_usage.get("is_enabled", False))
            result["extra_usage_util"] = _safe_float(extra_usage.get("utilization"))

        logger.info("Usage API パース: session=%.1f%%, weekly=%.1f%%, sonnet=%.1f%%",
                     result["five_hour_util"] or 0,
                     result["seven_day_util"] or 0,
                     result["seven_day_sonnet_util"] or 0)

        return result

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def last_fetch_time(self) -> Optional[str]:
        return self._last_fetch_time

    @property
    def last_data(self) -> Optional[Dict[str, Any]]:
        return self._last_data


def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
