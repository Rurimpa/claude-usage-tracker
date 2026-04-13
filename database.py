"""Usage Tracker - SQLite データベース操作"""
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, date, timedelta, timezone
from typing import Optional, Tuple
import config

logger = logging.getLogger(__name__)


def utc_to_jst_str(ts: str) -> str:
    """UTC timestamp文字列をJST表示文字列（YYYY-MM-DD HH:MM）に変換する。"""
    if not ts:
        return ""
    try:
        ts_base = ts[:19]  # "YYYY-MM-DDTHH:MM:SS" の部分のみ取得
        dt_utc = datetime.strptime(ts_base, '%Y-%m-%dT%H:%M:%S')
        dt_jst = dt_utc + timedelta(hours=9)
        return dt_jst.strftime('%Y-%m-%d %H:%M')
    except Exception:
        return ts[:16].replace('T', ' ')


def get_conn() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """テーブルを初期化する（存在しない場合のみ作成）。"""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS token_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'claude_code',
                project_path TEXT,
                project_name TEXT,
                session_id TEXT,
                model TEXT,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cache_creation_tokens INTEGER DEFAULT 0,
                cache_read_tokens INTEGER DEFAULT 0,
                web_search_count INTEGER DEFAULT 0,
                message_uuid TEXT UNIQUE
            );

            CREATE TABLE IF NOT EXISTS tool_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                session_id TEXT,
                project_path TEXT,
                project_name TEXT,
                tool_name TEXT,
                tool_target TEXT,
                associated_token_log_id INTEGER,
                FOREIGN KEY (associated_token_log_id) REFERENCES token_log(id)
            );

            CREATE TABLE IF NOT EXISTS scan_state (
                file_path TEXT PRIMARY KEY,
                last_size INTEGER,
                last_scanned TEXT
            );

            CREATE TABLE IF NOT EXISTS usage_snapshot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                five_hour_util REAL,
                seven_day_util REAL,
                seven_day_sonnet_util REAL,
                extra_usage_credits REAL,
                five_hour_resets_at TEXT,
                seven_day_resets_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_token_log_timestamp ON token_log(timestamp);
            CREATE INDEX IF NOT EXISTS idx_token_log_project ON token_log(project_name);
            CREATE INDEX IF NOT EXISTS idx_token_log_session ON token_log(session_id);
            CREATE INDEX IF NOT EXISTS idx_tool_log_assoc ON tool_log(associated_token_log_id);
            CREATE INDEX IF NOT EXISTS idx_usage_snapshot_ts ON usage_snapshot(timestamp);
        """)
    # Phase 2: 既存DBの usage_snapshot テーブルに新カラムを追加（マイグレーション）
    with get_conn() as conn:
        try:
            cursor = conn.execute("PRAGMA table_info(usage_snapshot)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            for col in ("five_hour_resets_at", "seven_day_resets_at"):
                if col not in existing_cols:
                    conn.execute(f"ALTER TABLE usage_snapshot ADD COLUMN {col} TEXT")
                    logger.info("usage_snapshot にカラム追加: %s", col)
        except Exception as e:
            logger.debug("usage_snapshot マイグレーション確認: %s", e)

    logger.info("データベース初期化完了: %s", config.DB_PATH)


def insert_token_log(
    timestamp: str, project_path: str, project_name: str, session_id: str,
    model: str, input_tokens: int, output_tokens: int,
    cache_creation_tokens: int, cache_read_tokens: int,
    web_search_count: int, message_uuid: str
) -> Optional[int]:
    """token_logに1件挿入。重複(message_uuid)はスキップ。挿入したIDを返す。"""
    try:
        with get_conn() as conn:
            cur = conn.execute(
                """INSERT OR IGNORE INTO token_log
                   (timestamp, project_path, project_name, session_id, model,
                    input_tokens, output_tokens, cache_creation_tokens,
                    cache_read_tokens, web_search_count, message_uuid)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (timestamp, project_path, project_name, session_id, model,
                 input_tokens, output_tokens, cache_creation_tokens,
                 cache_read_tokens, web_search_count, message_uuid)
            )
            return cur.lastrowid if cur.rowcount else None
    except Exception as e:
        logger.error("token_log挿入エラー: %s", e)
        return None


def insert_tool_log(
    timestamp: str, session_id: str, project_path: str, project_name: str,
    tool_name: str, tool_target: str, token_log_id: Optional[int]
) -> None:
    try:
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO tool_log
                   (timestamp, session_id, project_path, project_name,
                    tool_name, tool_target, associated_token_log_id)
                   VALUES (?,?,?,?,?,?,?)""",
                (timestamp, session_id, project_path, project_name,
                 tool_name, tool_target, token_log_id)
            )
    except Exception as e:
        logger.error("tool_log挿入エラー: %s", e)


def get_scan_state(file_path: str) -> Optional[int]:
    """前回スキャン時のファイルサイズを返す（未記録はNone）。"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_size FROM scan_state WHERE file_path=?", (file_path,)
        ).fetchone()
        return row["last_size"] if row else None


def update_scan_state(file_path: str, size: int) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO scan_state (file_path, last_size, last_scanned)
               VALUES (?,?,?)""",
            (file_path, size, datetime.now(timezone.utc).replace(tzinfo=None).isoformat())
        )


# === Phase 2: usage_snapshot 操作 ===

def insert_usage_snapshot(
    timestamp: str,
    five_hour_util: Optional[float] = None,
    seven_day_util: Optional[float] = None,
    seven_day_sonnet_util: Optional[float] = None,
    extra_usage_credits: Optional[float] = None,
    five_hour_resets_at: Optional[str] = None,
    seven_day_resets_at: Optional[str] = None,
) -> Optional[int]:
    """usage_snapshotに1件挿入。挿入したIDを返す。"""
    try:
        with get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO usage_snapshot
                   (timestamp, five_hour_util, seven_day_util,
                    seven_day_sonnet_util, extra_usage_credits,
                    five_hour_resets_at, seven_day_resets_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (timestamp, five_hour_util, seven_day_util,
                 seven_day_sonnet_util, extra_usage_credits,
                 five_hour_resets_at, seven_day_resets_at)
            )
            return cur.lastrowid if cur.rowcount else None
    except Exception as e:
        logger.error("usage_snapshot挿入エラー: %s", e)
        return None


def query_latest_usage_snapshot() -> Optional[dict]:
    """最新のusage_snapshotを1件返す。"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM usage_snapshot ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def query_usage_snapshots(since: Optional[str] = None,
                          until: Optional[str] = None,
                          limit: int = 1000) -> list:
    """指定期間のusage_snapshotを返す（時系列分析用）。"""
    where, params = _build_range_clause(since, until)
    with get_conn() as conn:
        rows = conn.execute(f"""
            SELECT * FROM usage_snapshot
            WHERE {where}
            ORDER BY timestamp DESC
            LIMIT ?
        """, params + [limit]).fetchall()
        return [dict(r) for r in rows]


# === 共通WHERE句ビルダー ===

def _build_range_clause(since: Optional[str], until: Optional[str],
                        col: str = "timestamp") -> Tuple[str, list]:
    """since/untilからWHERE句とパラメータを生成する。"""
    clauses = []
    params = []
    if since:
        clauses.append(f"{col} >= ?")
        params.append(since)
    if until:
        clauses.append(f"{col} <= ?")
        params.append(until)
    where = (" AND ".join(clauses)) if clauses else "1=1"
    return where, params


# === クエリ ===

def query_summary(since: Optional[str] = None, until: Optional[str] = None) -> dict:
    """指定期間の集計サマリーを返す。"""
    where, params = _build_range_clause(since, until)
    with get_conn() as conn:
        row = conn.execute(f"""
            SELECT
                COALESCE(SUM(input_tokens),0) as input_tokens,
                COALESCE(SUM(output_tokens),0) as output_tokens,
                COALESCE(SUM(cache_creation_tokens),0) as cache_creation_tokens,
                COALESCE(SUM(cache_read_tokens),0) as cache_read_tokens,
                COALESCE(SUM(web_search_count),0) as web_search_count,
                COUNT(*) as message_count
            FROM token_log
            WHERE {where}
        """, params).fetchone()
        return dict(row) if row else {}


def query_rows_for_cost(since: Optional[str] = None, until: Optional[str] = None) -> list:
    """指定期間のtoken_log行を全件返す（コスト計算用）。"""
    where, params = _build_range_clause(since, until)
    with get_conn() as conn:
        rows = conn.execute(f"""
            SELECT model, input_tokens, output_tokens,
                   cache_creation_tokens, cache_read_tokens
            FROM token_log WHERE {where}
        """, params).fetchall()
        return [dict(r) for r in rows]


def query_hourly_tokens(since: Optional[str] = None, until: Optional[str] = None) -> list:
    """時間別/日別トークン集計を返す（JST表示用）。期間に応じて自動で時間/日グループ化。"""
    where, params = _build_range_clause(since, until)

    # 期間の長さで粒度を決定
    if since and until:
        try:
            s = datetime.strptime(since[:19], '%Y-%m-%dT%H:%M:%S')
            e = datetime.strptime(until[:19], '%Y-%m-%dT%H:%M:%S')
            span_hours = (e - s).total_seconds() / 3600
        except Exception:
            span_hours = 48
    elif since:
        try:
            s = datetime.strptime(since[:19], '%Y-%m-%dT%H:%M:%S')
            span_hours = (datetime.now(timezone.utc).replace(tzinfo=None) - s).total_seconds() / 3600
        except Exception:
            span_hours = 48
    else:
        span_hours = 9999  # all

    if span_hours <= 48:
        group_fmt = '%Y-%m-%dT%H'
    else:
        group_fmt = '%Y-%m-%d'

    with get_conn() as conn:
        rows = conn.execute(f"""
            SELECT
                strftime('{group_fmt}', datetime(timestamp, '+9 hours')) as hour,
                model,
                SUM(input_tokens + output_tokens + cache_creation_tokens + cache_read_tokens) as total_tokens
            FROM token_log
            WHERE {where}
            GROUP BY hour, model
            ORDER BY hour
        """, params).fetchall()
        return [dict(r) for r in rows]


def query_project_stats(since: Optional[str] = None, until: Optional[str] = None) -> list:
    """プロジェクト別集計。"""
    where, params = _build_range_clause(since, until)
    with get_conn() as conn:
        rows = conn.execute(f"""
            SELECT
                project_name,
                SUM(input_tokens + output_tokens + cache_creation_tokens + cache_read_tokens) as total_tokens,
                COUNT(*) as message_count
            FROM token_log
            WHERE {where}
            GROUP BY project_name
            ORDER BY total_tokens DESC
            LIMIT 30
        """, params).fetchall()
        return [dict(r) for r in rows]


def query_tool_stats(since: Optional[str] = None, until: Optional[str] = None) -> list:
    """アクション（ツール）別集計。tool_logとtoken_logをJOINしてコスト・回数を返す。"""
    where, params = _build_range_clause(since, until, col="tl.timestamp")
    with get_conn() as conn:
        rows = conn.execute(f"""
            SELECT
                tl.tool_name,
                COUNT(*) as use_count,
                COALESCE(SUM(tk.input_tokens),0) as input_tokens,
                COALESCE(SUM(tk.output_tokens),0) as output_tokens,
                COALESCE(SUM(tk.cache_creation_tokens),0) as cache_creation_tokens,
                COALESCE(SUM(tk.cache_read_tokens),0) as cache_read_tokens,
                tk.model
            FROM tool_log tl
            LEFT JOIN token_log tk ON tl.associated_token_log_id = tk.id
            WHERE {where}
              AND tl.tool_name IS NOT NULL
              AND tl.tool_name != ''
            GROUP BY tl.tool_name
            ORDER BY (COALESCE(SUM(tk.input_tokens),0) + COALESCE(SUM(tk.output_tokens),0)
                      + COALESCE(SUM(tk.cache_creation_tokens),0)
                      + COALESCE(SUM(tk.cache_read_tokens),0)) DESC
        """, params).fetchall()
        return [dict(r) for r in rows]


def query_model_stats(since: Optional[str] = None, until: Optional[str] = None) -> list:
    """モデル別集計。"""
    where, params = _build_range_clause(since, until)
    with get_conn() as conn:
        rows = conn.execute(f"""
            SELECT
                model,
                SUM(input_tokens + output_tokens + cache_creation_tokens + cache_read_tokens) as total_tokens
            FROM token_log
            WHERE {where}
            GROUP BY model
            ORDER BY total_tokens DESC
        """, params).fetchall()
        return [dict(r) for r in rows]


def query_recent_messages(limit: int = 50, since: Optional[str] = None,
                          until: Optional[str] = None) -> list:
    """直近のメッセージ一覧。"""
    where, params = _build_range_clause(since, until)
    with get_conn() as conn:
        rows = conn.execute(f"""
            SELECT timestamp, project_name, model,
                   input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens,
                   session_id, message_uuid
            FROM token_log
            WHERE {where}
            ORDER BY timestamp DESC
            LIMIT ?
        """, params + [limit]).fetchall()
        return [dict(r) for r in rows]


def query_activity_log(since: Optional[str] = None, until: Optional[str] = None) -> list:
    """
    アクティビティログ用：セッション単位のサマリー + メッセージ別トークン + tool_log。
    """
    where, params = _build_range_clause(since, until)
    with get_conn() as conn:
        sessions = conn.execute(f"""
            SELECT
                session_id,
                project_name,
                model,
                MIN(timestamp) as first_ts,
                SUM(input_tokens) as input_tokens,
                SUM(output_tokens) as output_tokens,
                SUM(cache_creation_tokens) as cache_creation_tokens,
                SUM(cache_read_tokens) as cache_read_tokens,
                SUM(web_search_count) as web_search_count,
                COUNT(*) as msg_count
            FROM token_log
            WHERE {where}
              AND session_id IS NOT NULL
            GROUP BY session_id
            ORDER BY first_ts DESC
            LIMIT 200
        """, params).fetchall()

        result = []
        for s in sessions:
            sd = dict(s)
            cost = config.calc_cost(
                sd.get("model") or "default",
                sd.get("input_tokens", 0),
                sd.get("output_tokens", 0),
                sd.get("cache_creation_tokens", 0),
                sd.get("cache_read_tokens", 0)
            )
            sd["total_cost"] = cost

            # メッセージ別トークン情報を取得
            msg_where = f"session_id = ? AND {where}" if where != "1=1" else "session_id = ?"
            msg_params = [sd["session_id"]] + params if where != "1=1" else [sd["session_id"]]
            messages = conn.execute(f"""
                SELECT id, timestamp, input_tokens, output_tokens,
                       cache_creation_tokens, cache_read_tokens, model
                FROM token_log
                WHERE {msg_where}
                ORDER BY timestamp
            """, msg_params).fetchall()

            msg_list = []
            for m in messages:
                md = dict(m)
                msg_cost = config.calc_cost(
                    md.get("model") or sd.get("model") or "default",
                    md.get("input_tokens", 0),
                    md.get("output_tokens", 0),
                    md.get("cache_creation_tokens", 0),
                    md.get("cache_read_tokens", 0)
                )
                tools = conn.execute("""
                    SELECT tool_name, tool_target, timestamp
                    FROM tool_log
                    WHERE associated_token_log_id = ?
                    ORDER BY timestamp
                """, (md["id"],)).fetchall()
                md["cost"] = msg_cost
                md["tools"] = [dict(t) for t in tools]
                msg_list.append(md)

            sd["messages"] = msg_list
            result.append(sd)
        return result


def query_weekly_utilization_history() -> list:
    """直近7日間のseven_day_utilを日別に1ポイントずつ返す（各日の最終値）。

    Returns:
        [{"date": "2026-04-11", "util": 14.0}, ...] 日付昇順
    """
    since = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)).strftime('%Y-%m-%dT00:00:00')
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                date(timestamp) as day,
                seven_day_util
            FROM usage_snapshot
            WHERE timestamp >= ?
              AND seven_day_util IS NOT NULL
            ORDER BY timestamp ASC
        """, (since,)).fetchall()

    # 各日の最終レコードの値を採用
    daily = {}
    for r in rows:
        daily[r["day"]] = r["seven_day_util"]

    result = []
    for day_str in sorted(daily.keys()):
        result.append({"date": day_str, "util": daily[day_str]})
    return result


def get_total_record_count() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM token_log").fetchone()
        return row["cnt"] if row else 0


def get_db_size_mb() -> float:
    """データベースファイルのサイズをMBで返す。"""
    try:
        if config.DB_PATH.exists():
            return config.DB_PATH.stat().st_size / (1024 * 1024)
    except Exception:
        pass
    return 0.0


def cleanup_old_records() -> dict:
    """古いレコードとログファイルを削除し、DBを圧縮する。

    Returns:
        削除件数のdict: {"snapshot": N, "token_log": N, "tool_log": N, "log_files": N}
    """
    result = {"snapshot": 0, "token_log": 0, "tool_log": 0, "log_files": 0}

    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        with get_conn() as conn:
            # usage_snapshot: 30日以上前を削除
            cutoff_snapshot = (now - timedelta(days=config.RETENTION_DAYS_SNAPSHOT)).isoformat()
            cur = conn.execute(
                "DELETE FROM usage_snapshot WHERE timestamp < ?", (cutoff_snapshot,)
            )
            result["snapshot"] = cur.rowcount

            # token_log: 90日以上前を削除
            cutoff_token = (now - timedelta(days=config.RETENTION_DAYS_TOKEN_LOG)).isoformat()
            cur = conn.execute(
                "DELETE FROM token_log WHERE timestamp < ?", (cutoff_token,)
            )
            result["token_log"] = cur.rowcount

            # tool_log: 紐づくtoken_logが削除されたレコードを削除
            cur = conn.execute(
                """DELETE FROM tool_log
                   WHERE associated_token_log_id IS NOT NULL
                     AND associated_token_log_id NOT IN (SELECT id FROM token_log)"""
            )
            result["tool_log"] = cur.rowcount

        # VACUUM は別接続で実行（トランザクション外）
        conn2 = sqlite3.connect(str(config.DB_PATH), timeout=30)
        conn2.execute("VACUUM")
        conn2.close()

    except Exception as e:
        logger.error("DBローテーションエラー: %s", e)

    # ログファイル: 30日以上前を削除
    try:
        cutoff_date = date.today() - timedelta(days=config.RETENTION_DAYS_LOG_FILES)
        if config.LOG_DIR.exists():
            for f in config.LOG_DIR.iterdir():
                if f.is_file() and f.suffix == ".log":
                    try:
                        mtime = datetime.fromtimestamp(f.stat().st_mtime).date()
                        if mtime < cutoff_date:
                            f.unlink()
                            result["log_files"] += 1
                    except Exception:
                        pass
    except Exception as e:
        logger.error("ログファイルローテーションエラー: %s", e)

    total = sum(result.values())
    if total > 0:
        logger.info("DBローテーション完了: snapshot=%d件, token_log=%d件, tool_log=%d件, log_files=%d件",
                     result["snapshot"], result["token_log"], result["tool_log"], result["log_files"])
    else:
        logger.info("DBローテーション: 削除対象なし")

    return result


def vacuum_db() -> None:
    """手動VACUUM実行。"""
    try:
        conn = sqlite3.connect(str(config.DB_PATH), timeout=30)
        conn.execute("VACUUM")
        conn.close()
        logger.info("VACUUM完了")
    except Exception as e:
        logger.error("VACUUMエラー: %s", e)
