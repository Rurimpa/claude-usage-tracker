"""Usage Tracker - JSONLスキャナー（差分読み取り・tool_use解析）"""
import json
import glob
import logging
import os
from pathlib import Path
from typing import Callable, Optional
import config
import database

logger = logging.getLogger(__name__)

# ツール名 → 人間可読アクション変換
def _tool_target(name: str, inp: dict) -> str:
    try:
        if name == "Read":
            fname = Path(inp.get("file_path", "")).name
            return f"{fname} を読み込み"
        elif name == "Write":
            fname = Path(inp.get("file_path", "")).name
            return f"{fname} を書き出し"
        elif name == "Edit":
            fname = Path(inp.get("file_path", "")).name
            return f"{fname} を編集"
        elif name == "Glob":
            return f"ファイル検索: {inp.get('pattern', '')}"
        elif name == "Grep":
            pat = str(inp.get("pattern", ""))[:30]
            return f"コード検索: {pat}"
        elif name == "Bash":
            cmd = str(inp.get("command", ""))[:40]
            return f"コマンド実行: {cmd}"
        elif name == "WebSearch":
            q = str(inp.get("query", ""))[:30]
            return f"Web検索: {q}" if q else "Web検索"
        elif name == "WebFetch":
            url = str(inp.get("url", ""))[:40]
            return f"Webフェッチ: {url}"
        elif name == "Agent":
            desc = str(inp.get("description", ""))[:30]
            return f"サブエージェント: {desc}"
        elif name == "TodoWrite":
            return "タスクリスト更新"
        elif name == "Skill":
            skill_name = str(inp.get("skill", ""))[:30]
            return f"スキル実行: {skill_name}"
        else:
            # 汎用フォールバック
            first_val = next(iter(inp.values()), "") if inp else ""
            return f"{name}: {str(first_val)[:40]}"
    except Exception:
        return name


def get_all_jsonl_files() -> list:
    pattern = str(config.PROJECTS_DIR / "**" / "*.jsonl")
    return glob.glob(pattern, recursive=True)


def scan_all(
    progress_cb: Optional[Callable[[int, int], None]] = None,
    incremental: bool = True
) -> int:
    """
    全JSONLファイルをスキャンしてDBに保存。
    incremental=True: scan_stateで差分のみ読む。
    progress_cb(done, total): 進捗コールバック。
    返り値: 新規挿入レコード数。
    """
    files = get_all_jsonl_files()
    total = len(files)
    inserted = 0

    logger.info("スキャン開始: %d ファイル", total)

    for i, fpath in enumerate(files):
        if progress_cb:
            progress_cb(i, total)
        try:
            inserted += _scan_file(fpath, incremental)
        except Exception as e:
            logger.error("ファイルスキャンエラー %s: %s", fpath, e)

    if progress_cb:
        progress_cb(total, total)
    logger.info("スキャン完了: %d件挿入, %d/%dファイル処理", inserted, total, total)
    return inserted


def _scan_file(fpath: str, incremental: bool) -> int:
    """1ファイルをスキャン。返り値: 挿入件数。

    B-2修正: バイナリモードで読み込み、手動デコードする。
    テキストモードでのseekはバイト位置とズレる可能性があったため。
    """
    try:
        current_size = os.path.getsize(fpath)
    except OSError:
        return 0

    prev_size = database.get_scan_state(fpath) if incremental else None
    if prev_size is not None and current_size <= prev_size:
        return 0  # 変化なし

    inserted = 0
    seek_pos = prev_size if (prev_size and incremental and prev_size > 0) else 0

    # B-2修正: バイナリモードで読み込み → 手動デコード
    # os.path.getsize()のバイト数とseek位置を正確に一致させる
    raw_data = b""
    try:
        with open(fpath, "rb") as fp:
            if seek_pos > 0:
                fp.seek(seek_pos)
            raw_data = fp.read()
    except OSError as e:
        logger.error("ファイル読み込みエラー %s: %s", fpath, e)
        return 0

    if not raw_data:
        database.update_scan_state(fpath, current_size)
        return 0

    # デコード（UTF-8 → Shift-JIS → Latin-1 の順で試行）
    text = None
    for encoding in ("utf-8", "shift-jis", "latin-1"):
        try:
            text = raw_data.decode(encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue

    if text is None:
        # すべてのエンコーディングで失敗した場合、replaceモードで強制デコード
        text = raw_data.decode("utf-8", errors="replace")

    lines = text.splitlines()

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except (json.JSONDecodeError, Exception) as e:
            logger.debug("JSON解析スキップ: %s", e)
            continue

        if row.get("type") != "assistant":
            continue

        msg = row.get("message")
        if not isinstance(msg, dict):
            continue
        usage = msg.get("usage")
        if not usage or not isinstance(usage, dict):
            continue

        timestamp = row.get("timestamp", "")
        session_id = row.get("sessionId", "") or ""
        cwd = row.get("cwd", "") or ""
        project_path = cwd
        project_name = Path(cwd).name if cwd else "unknown"
        model = msg.get("model", "") or ""
        uuid = row.get("uuid", "") or ""

        input_tokens = int(usage.get("input_tokens", 0) or 0)
        output_tokens = int(usage.get("output_tokens", 0) or 0)
        cache_creation = int(usage.get("cache_creation_input_tokens", 0) or 0)
        cache_read = int(usage.get("cache_read_input_tokens", 0) or 0)
        stu = usage.get("server_tool_use") or {}
        web_search = int(stu.get("web_search_requests", 0) or 0) if isinstance(stu, dict) else 0

        token_log_id = database.insert_token_log(
            timestamp, project_path, project_name, session_id, model,
            input_tokens, output_tokens, cache_creation, cache_read,
            web_search, uuid
        )
        if token_log_id:
            inserted += 1

        # tool_useを取り出してtool_logに保存
        content = msg.get("content", [])
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") != "tool_use":
                    continue
                tname = item.get("name", "") or ""
                tinput = item.get("input") or {}
                if not isinstance(tinput, dict):
                    tinput = {}
                ttarget = _tool_target(tname, tinput)
                database.insert_tool_log(
                    timestamp, session_id, project_path, project_name,
                    tname, ttarget, token_log_id
                )

    database.update_scan_state(fpath, current_size)
    return inserted
