"""Usage Tracker - エントリーポイント"""
import sys
import os
import threading
import logging
import traceback
import ctypes
from datetime import datetime, timedelta
from pathlib import Path

# ── F-12: コンソールウィンドウを非表示にする ──
try:
    _console_hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if _console_hwnd:
        ctypes.windll.user32.ShowWindow(_console_hwnd, 0)  # SW_HIDE
except Exception:
    pass

# ── 最初期デバッグログ ──
_BASE_DIR = Path(__file__).parent
_DEBUG_LOG = _BASE_DIR / "logs" / "debug_startup.log"

def _debug(msg):
    try:
        _DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}] {msg}\n")
    except Exception:
        pass

_debug("=" * 50)
_debug(f"起動開始 Python={sys.executable} CWD={os.getcwd()}")


def setup_logging():
    from config import LOG_DIR
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"usage_tracker_{datetime.now().strftime('%Y%m%d')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(str(log_file), encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ]
    )
    _debug("setup_logging完了")

try:
    setup_logging()
except Exception as e:
    _debug(f"setup_logging失敗: {traceback.format_exc()}")

logger = logging.getLogger(__name__)

# ── シングルインスタンス制御 ──
_MUTEX_NAME = "Global\\ClaudeUsageTracker_SingleInstance"
_mutex_handle = None

def _acquire_mutex() -> bool:
    global _mutex_handle
    try:
        _mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, True, _MUTEX_NAME)
        last_err = ctypes.windll.kernel32.GetLastError()
        _debug(f"Mutex: handle={_mutex_handle}, last_err={last_err}")
        if last_err == 183:
            _debug("Mutex: 別インスタンス検出 → 起動中止")
            ctypes.windll.kernel32.CloseHandle(_mutex_handle)
            _mutex_handle = None
            return False
        _debug("Mutex: 取得成功")
        return True
    except Exception as e:
        _debug(f"Mutex: エラー {e}")
        return True

try:
    _debug("config import開始")
    import config
    config.load_settings()
    _debug(f"config OK: interval={config.SCAN_INTERVAL_SECONDS}")
    _debug("database import開始")
    import database
    _debug("scanner import開始")
    import scanner
    _debug("usage_api import開始")
    from usage_api import UsageAPIClient
    _debug("全import完了")
except Exception as e:
    _debug(f"import失敗: {traceback.format_exc()}")


class UsageTrackerApp:
    def __init__(self):
        self.app_gui = None
        self.tray_icon = None
        self._stop_event = threading.Event()
        self._scan_lock = threading.Lock()
        self._usage_client = UsageAPIClient()
        self._usage_data = None

    def run(self):
        logger.info("Usage Tracker 起動 (v%s)", config.VERSION)
        logger.info("DB: %s", config.DB_PATH)
        logger.info("スキャン対象: %s", config.PROJECTS_DIR)
        logger.info("スキャン間隔: %d秒, Usage API間隔: %d秒",
                     config.SCAN_INTERVAL_SECONDS, config.USAGE_API_INTERVAL_SECONDS)

        database.init_db()

        self._start_gui()

        scan_thread = threading.Thread(
            target=self._background_scan_loop, daemon=True, name="ScanLoop"
        )
        scan_thread.start()

        tray_thread = threading.Thread(
            target=self._run_tray, daemon=True, name="TrayIcon"
        )
        tray_thread.start()

        init_thread = threading.Thread(
            target=self._initial_scan, daemon=True, name="InitialScan"
        )
        init_thread.start()

        if config.USAGE_API_ENABLED:
            api_thread = threading.Thread(
                target=self._usage_api_loop, daemon=True, name="UsageAPI"
            )
            api_thread.start()

        try:
            self.app_gui.mainloop()
        except Exception as e:
            logger.error("GUIメインループエラー: %s", e)
        finally:
            self._stop_event.set()
            _release_mutex()
            logger.info("Usage Tracker 終了")

    def _start_gui(self):
        try:
            from gui import App
            self.app_gui = App()
            self.app_gui.set_scan_callback(self._trigger_scan)
            self.app_gui.set_quit_callback(self._quit_all)
            self.app_gui.set_usage_api_test_callback(self._test_usage_api)
            logger.info("GUI構築完了")
        except Exception as e:
            _debug(f"_start_gui: エラー {traceback.format_exc()}")
            logger.error("GUI構築エラー: %s", e, exc_info=True)

    def _initial_scan(self):
        logger.info("初回スキャン開始")
        try:
            def progress(done, total):
                if self.app_gui and not self._stop_event.is_set():
                    self.app_gui.after(0, self.app_gui.update_scan_progress, done, total)
            n = scanner.scan_all(progress_cb=progress, incremental=True)
            logger.info("初回スキャン完了: %d件新規", n)
            if self.app_gui and not self._stop_event.is_set():
                self.app_gui.after(0, self.app_gui.refresh_from_scan)
        except Exception as e:
            logger.error("初回スキャンエラー: %s", e)

    def _background_scan_loop(self):
        while not self._stop_event.is_set():
            elapsed = 0
            while elapsed < config.SCAN_INTERVAL_SECONDS:
                if self._stop_event.wait(1):
                    return
                elapsed += 1
            self._trigger_scan()

    def _trigger_scan(self):
        if self._scan_lock.locked():
            return
        t = threading.Thread(target=self._do_scan, daemon=True, name="DiffScan")
        t.start()

    def _do_scan(self):
        with self._scan_lock:
            try:
                def progress(done, total):
                    if self.app_gui and not self._stop_event.is_set():
                        self.app_gui.after(0, self.app_gui.update_scan_progress, done, total)
                n = scanner.scan_all(progress_cb=progress, incremental=True)
                if n > 0:
                    logger.info("差分スキャン完了: %d件新規", n)
                if self.app_gui and not self._stop_event.is_set():
                    self.app_gui.after(0, self.app_gui.refresh_from_scan)
            except Exception as e:
                logger.error("差分スキャンエラー: %s", e)

    # ════════════════════════════════════════════
    # Usage API ポーリング（v3.0.0: OAuth）
    # ════════════════════════════════════════════

    def _usage_api_loop(self):
        logger.info("Usage API ポーリング開始（間隔: %d秒）", config.USAGE_API_INTERVAL_SECONDS)
        if self._stop_event.wait(10):
            return
        while not self._stop_event.is_set():
            self._fetch_and_update_usage()
            elapsed = 0
            while elapsed < config.USAGE_API_INTERVAL_SECONDS:
                if self._stop_event.wait(1):
                    return
                elapsed += 1

    def _fetch_and_update_usage(self):
        data = self._usage_client.fetch_usage()
        if data is None:
            logger.warning("Usage API 取得失敗: %s", self._usage_client.last_error)
            if self.tray_icon:
                err_msg = self._usage_client.last_error or "不明なエラー"
                try:
                    self.tray_icon.title = f"Usage Tracker\n{err_msg}"
                except Exception:
                    pass
            if self.app_gui and not self._stop_event.is_set():
                self.app_gui.after(0, self.app_gui.update_usage_status,
                                   None, self._usage_client.last_error)
            return

        self._usage_data = data

        try:
            database.insert_usage_snapshot(
                timestamp=datetime.utcnow().isoformat() + "Z",
                five_hour_util=data.get("five_hour_util"),
                seven_day_util=data.get("seven_day_util"),
                seven_day_sonnet_util=data.get("seven_day_sonnet_util"),
                five_hour_resets_at=data.get("five_hour_resets_at"),
                seven_day_resets_at=data.get("seven_day_resets_at"),
            )
        except Exception as e:
            logger.error("usage_snapshot 保存エラー: %s", e)

        self._update_tray_from_data(data)
        self._update_tray_tooltip(data)

        if self.app_gui and not self._stop_event.is_set():
            self.app_gui.after(0, self.app_gui.update_usage_status, data, None)

    def _update_tray_from_data(self, data: dict):
        """F-14: 3パターン分岐でトレイアイコンを更新。"""
        five_hour = data.get("five_hour_util")
        extra_enabled = data.get("extra_usage_is_enabled", False)
        extra_util = data.get("extra_usage_util")

        if five_hour is not None and five_hour >= 100:
            if extra_enabled:
                if extra_util is None:
                    self.update_tray_icon(100.0, "extra")
                else:
                    self.update_tray_icon(max(0.0, 100.0 - extra_util), "extra")
            else:
                self.update_tray_icon(0.0, "session")
        elif five_hour is not None:
            self.update_tray_icon(max(0.0, 100.0 - five_hour), "session")

    def _update_tray_tooltip(self, data: dict):
        """F-6: ツールチップを%表示で更新。"""
        if not self.tray_icon:
            return
        parts = []
        five_hour = data.get("five_hour_util")
        extra_enabled = data.get("extra_usage_is_enabled", False)
        extra_util = data.get("extra_usage_util")

        if five_hour is not None:
            rem = max(0.0, 100.0 - five_hour)
            parts.append(f"セッション: 残り{rem:.0f}%")
        if extra_enabled:
            if extra_util is None:
                parts.append("追加使用量: 無制限")
            else:
                rem = max(0.0, 100.0 - extra_util)
                parts.append(f"追加使用量: 残り{rem:.0f}%")

        tooltip = "Claude Usage Tracker"
        if parts:
            tooltip += "\n" + " | ".join(parts)
        try:
            self.tray_icon.title = tooltip
        except Exception:
            pass

    def _test_usage_api(self):
        def _do_test():
            data = self._usage_client.fetch_usage()
            if self.app_gui and not self._stop_event.is_set():
                if data:
                    self._usage_data = data
                    self.app_gui.after(0, self.app_gui.update_usage_status, data, None)
                    self._update_tray_from_data(data)
                    self._update_tray_tooltip(data)
                else:
                    self.app_gui.after(0, self.app_gui.update_usage_status,
                                       None, self._usage_client.last_error)
        t = threading.Thread(target=_do_test, daemon=True, name="UsageAPITest")
        t.start()

    # ════════════════════════════════════════════
    # トレイアイコン
    # ════════════════════════════════════════════

    def _run_tray(self):
        try:
            import pystray
            from icons.gauge import make_gauge_icon

            self._tray_pct = 100.0
            self._tray_mode = "session"
            self._tray_dim = False

            img = make_gauge_icon(pct=self._tray_pct, mode=self._tray_mode)

            def on_left_click(icon, item):
                self._show_usage_popup()

            def quit_app(icon, item):
                icon.stop()
                self._quit_all()

            tooltip = "Claude Usage Tracker\nUsage API データ未取得"

            menu = pystray.Menu(
                pystray.MenuItem("使用量を表示", on_left_click, default=True),
                pystray.MenuItem("ダッシュボードを開く", self._show_dashboard),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("終了", quit_app),
            )
            self.tray_icon = pystray.Icon(
                "Claude Usage Tracker", img, tooltip, menu
            )
            logger.info("トレイアイコン起動（ゲージ表示）")

            blink_thread = threading.Thread(
                target=self._tray_blink_loop, daemon=True, name="TrayBlink"
            )
            blink_thread.start()
            self.tray_icon.run()
        except ImportError as e:
            logger.warning("pystray/Pillow不足: %s", e)
        except Exception as e:
            logger.error("トレイアイコンエラー: %s", e)

    def _show_dashboard(self, icon=None, item=None):
        if self.app_gui and not self._stop_event.is_set():
            self.app_gui.after(0, self.app_gui.deiconify)
            self.app_gui.after(0, self.app_gui.lift)

    def _show_usage_popup(self, icon=None, item=None):
        if not self.app_gui or self._stop_event.is_set():
            return
        self.app_gui.after(0, self._create_tray_popup)

    def _create_tray_popup(self):
        """F-5: 使用量ポップアップ。"""
        import tkinter as tk

        popup = tk.Toplevel(self.app_gui)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg="#2c3e50")

        screen_w = popup.winfo_screenwidth()
        screen_h = popup.winfo_screenheight()
        popup_w, popup_h = 360, 260
        popup.geometry(f"{popup_w}x{popup_h}+{screen_w - popup_w - 10}+{screen_h - popup_h - 50}")

        title_frame = tk.Frame(popup, bg="#1a6b9a")
        title_frame.pack(fill=tk.X)
        tk.Label(title_frame, text="  Claude Usage Tracker", font=("Meiryo", 10, "bold"),
                 bg="#1a6b9a", fg="white", anchor="w", pady=4).pack(fill=tk.X, padx=5)

        data = self._usage_data
        body = tk.Frame(popup, bg="#2c3e50", padx=12, pady=8)
        body.pack(fill=tk.BOTH, expand=True)

        def row(label, value, color="white"):
            r = tk.Frame(body, bg="#2c3e50")
            r.pack(fill=tk.X, pady=2)
            tk.Label(r, text=label, font=("Meiryo", 9), bg="#2c3e50",
                     fg="#bdc3c7", anchor="w", width=18).pack(side=tk.LEFT)
            tk.Label(r, text=value, font=("Meiryo", 10, "bold"), bg="#2c3e50",
                     fg=color, anchor="e").pack(side=tk.RIGHT)

        if data:
            fh = data.get("five_hour_util")
            sd = data.get("seven_day_util")
            sn = data.get("seven_day_sonnet_util")
            ee = data.get("extra_usage_is_enabled", False)
            eu = data.get("extra_usage_util")
            fr = data.get("five_hour_resets_at")
            sr = data.get("seven_day_resets_at")

            if fh is not None:
                rem = max(0.0, 100.0 - fh)
                c = "#2ecc71" if rem > 50 else "#f1c40f" if rem > 20 else "#e74c3c"
                row("セッション (5h):", f"残り {rem:.0f}%", c)
                if fr:
                    rs = _format_reset_time(fr)
                    if rs:
                        row("", rs, "#7f8c8d")

            if sd is not None:
                rem = max(0.0, 100.0 - sd)
                c = "#2ecc71" if rem > 50 else "#f1c40f" if rem > 20 else "#e74c3c"
                row("週間 (全モデル):", f"残り {rem:.0f}%", c)
                if sr:
                    rs = _format_reset_time(sr)
                    if rs:
                        row("", rs, "#7f8c8d")

            if sn is not None:
                rem = max(0.0, 100.0 - sn)
                c = "#2ecc71" if rem > 50 else "#f1c40f" if rem > 20 else "#e74c3c"
                row("週間 (Sonnet):", f"残り {rem:.0f}%", c)

            if ee:
                if eu is None:
                    row("追加使用量:", "無制限", "#2ecc71")
                else:
                    rem = max(0.0, 100.0 - eu)
                    c = "#2ecc71" if rem > 50 else "#f1c40f" if rem > 20 else "#e74c3c"
                    row("追加使用量:", f"残り {rem:.0f}%", c)
        else:
            tk.Label(body, text="Usage API データ未取得",
                     font=("Meiryo", 10), bg="#2c3e50", fg="#95a5a6").pack(pady=15)

        link = tk.Frame(popup, bg="#2c3e50")
        link.pack(fill=tk.X, padx=12, pady=(0, 8))
        lbl = tk.Label(link, text="ダッシュボードを開く →", font=("Meiryo", 8),
                       bg="#2c3e50", fg="#3498db", cursor="hand2")
        lbl.pack(anchor="e")
        lbl.bind("<Button-1>", lambda e: (popup.destroy(), self._show_dashboard()))

        auto_close = popup.after(8000, popup.destroy)
        popup.bind("<Button-1>", lambda e: popup.after_cancel(auto_close) if auto_close else None)
        popup.bind("<FocusOut>", lambda e: popup.destroy())
        popup.focus_set()

    def _tray_blink_loop(self):
        import time
        from icons.gauge import make_gauge_icon
        while not self._stop_event.is_set():
            pct = self._tray_pct
            if 0 < pct <= 10:
                interval = 0.5 if pct <= 5 else 1.5
                self._tray_dim = not self._tray_dim
                try:
                    if self.tray_icon:
                        self.tray_icon.icon = make_gauge_icon(
                            pct=pct, mode=self._tray_mode, dim=self._tray_dim
                        )
                except Exception:
                    pass
                time.sleep(interval)
            else:
                self._tray_dim = False
                time.sleep(1)

    def update_tray_icon(self, pct: float, mode: str = "session"):
        from icons.gauge import make_gauge_icon
        self._tray_pct = pct
        self._tray_mode = mode
        try:
            if self.tray_icon:
                self.tray_icon.icon = make_gauge_icon(pct=pct, mode=mode, dim=self._tray_dim)
        except Exception:
            pass

    def _quit_all(self):
        logger.info("アプリ終了処理開始")
        self._stop_event.set()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        if self.app_gui:
            try:
                self.app_gui.after(0, self.app_gui.destroy)
            except Exception:
                pass
        _release_mutex()


def _format_reset_time(resets_at: str) -> str:
    try:
        ts = resets_at[:19]
        fmt = '%Y-%m-%dT%H:%M:%S' if 'T' in ts else '%Y-%m-%d %H:%M:%S'
        dt_reset = datetime.strptime(ts, fmt)
        delta = dt_reset - datetime.utcnow()
        if delta.total_seconds() <= 0:
            return "リセット済み"
        h = int(delta.total_seconds() // 3600)
        m = int((delta.total_seconds() % 3600) // 60)
        return f"{h}時間{m}分後リセット" if h > 0 else f"{m}分後リセット"
    except Exception:
        return ""


def _release_mutex():
    global _mutex_handle
    if _mutex_handle:
        try:
            ctypes.windll.kernel32.ReleaseMutex(_mutex_handle)
            ctypes.windll.kernel32.CloseHandle(_mutex_handle)
            _mutex_handle = None
        except Exception:
            pass


if __name__ == "__main__":
    _debug("__main__ 開始")
    try:
        if not _acquire_mutex():
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showwarning(
                "Usage Tracker",
                "Claude Usage Tracker はすでに起動しています。\nタスクトレイを確認してください。"
            )
            root.destroy()
            sys.exit(0)
        app = UsageTrackerApp()
        app.run()
    except Exception as e:
        _debug(f"致命的エラー: {traceback.format_exc()}")
        logger.error("致命的エラー: %s", e, exc_info=True)
