"""Usage Tracker - エントリーポイント"""
import sys
import os
import threading
import logging
import traceback
import ctypes
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── F-12: コンソールウィンドウを非表示にする ──
try:
    _console_hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if _console_hwnd:
        ctypes.windll.user32.ShowWindow(_console_hwnd, 0)  # SW_HIDE
        ctypes.windll.kernel32.FreeConsole()
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
    _debug("i18n import開始")
    import i18n
    i18n.load(config.LANGUAGE)
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
        self._mini_widget = None  # F-18: ミニウィジェット
        self._usage_api_test_callback = None  # ミニウィジェットからも参照
        self._widget_last_poll = 0  # 連打防止用

    def run(self):
        logger.info("Usage Tracker 起動 (v%s)", config.VERSION)
        logger.info("DB: %s", config.DB_PATH)
        logger.info("スキャン対象: %s", config.PROJECTS_DIR)
        logger.info("スキャン間隔: %d秒, Usage API間隔: %d秒",
                     config.SCAN_INTERVAL_SECONDS, config.USAGE_API_INTERVAL_SECONDS)

        database.init_db()
        database.cleanup_old_records()

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
            self._usage_api_test_callback = self._test_usage_api
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
                timestamp=datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z",
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
            self.app_gui.after(0, self.app_gui.update_remaining_tab, data)
            self.app_gui.after(0, self._update_mini_widget)

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
        """F-6: ツールチップを罫線付きフォーマットで更新。"""
        if not self.tray_icon:
            return
        BAR = "━" * 14
        items = []
        five_hour = data.get("five_hour_util")
        seven_day = data.get("seven_day_util")
        extra_enabled = data.get("extra_usage_is_enabled", False)
        extra_util = data.get("extra_usage_util")

        if five_hour is not None:
            rem = max(0.0, 100.0 - five_hour)
            items.append(i18n.t("tray_tooltip_session", value=f"{rem:.0f}"))
        if seven_day is not None:
            rem = max(0.0, 100.0 - seven_day)
            items.append(i18n.t("tray_tooltip_weekly", value=f"{rem:.0f}"))
        if extra_enabled:
            if extra_util is None:
                items.append(i18n.t("tray_tooltip_extra_unlimited"))
            else:
                rem = max(0.0, 100.0 - extra_util)
                items.append(i18n.t("tray_tooltip_extra_pct", value=f"{rem:.0f}"))

        # 罫線付きフォーマット
        body = "\n\n".join(items)
        tooltip = f"{BAR}\nClaude Usage Tracker\n\n{body}\n{BAR}"

        # Windows ツールチップは最大128文字
        if len(tooltip) > 127:
            tooltip = "Claude Usage Tracker\n\n" + "\n\n".join(items)
        if len(tooltip) > 127:
            tooltip = "Claude Usage Tracker\n" + "\n".join(items)
        if len(tooltip) > 127:
            tooltip = tooltip[:124] + "..."

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
                    self.app_gui.after(0, self.app_gui.update_remaining_tab, data)
                    self._update_tray_from_data(data)
                    self._update_tray_tooltip(data)
                    self.app_gui.after(0, self._update_mini_widget)
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

            tooltip = f"Claude Usage Tracker\n{i18n.t('tray_tooltip_pending')}"

            def toggle_widget(icon, item):
                self._toggle_mini_widget()

            menu = pystray.Menu(
                pystray.MenuItem(i18n.t("tray_show_usage"), on_left_click, default=True),
                pystray.MenuItem(i18n.t("tray_open_dashboard"), self._show_dashboard),
                pystray.MenuItem(i18n.t("tray_mini_widget"), toggle_widget),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(i18n.t("tray_exit"), quit_app),
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
        """F-5/F-19/F-20: 使用量ポップアップ（縦長レイアウト・時計盤+テキスト+キャラアイコン）。"""
        import tkinter as tk
        from gui import draw_clock_on_canvas

        BG = "#2c2c2c"
        ACCENT = "#E07B39"

        popup = tk.Toplevel(self.app_gui)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg=BG)

        screen_w = popup.winfo_screenwidth()
        screen_h = popup.winfo_screenheight()
        popup_w, popup_h = 360, 560
        popup.geometry(f"{popup_w}x{popup_h}+{screen_w - popup_w - 10}+{screen_h - popup_h - 50}")

        # タイトルバー（Claudeオレンジ）
        title_frame = tk.Frame(popup, bg=ACCENT)
        title_frame.pack(fill=tk.X)
        tk.Label(title_frame, text="  Claude Usage Tracker", font=("Meiryo", 10, "bold"),
                 bg=ACCENT, fg="white", anchor="w", pady=4).pack(fill=tk.X, padx=5)

        # メインコンテンツ（縦長レイアウト）
        content = tk.Frame(popup, bg=BG, padx=12, pady=8)
        content.pack(fill=tk.BOTH, expand=True)

        # 上部: 時計盤 + キャラアイコン（横並び）
        top_row = tk.Frame(content, bg=BG)
        top_row.pack(fill=tk.X)

        # 時計盤Canvas
        clock_size = 180
        clock_canvas = tk.Canvas(top_row, width=clock_size, height=clock_size,
                                  bg=BG, highlightthickness=0)
        clock_canvas.pack(side=tk.LEFT, padx=(0, 8))
        draw_clock_on_canvas(clock_canvas, clock_size, self._usage_data, show_numbers=True)

        # キャラクター画像（時計盤の右隣）
        char_path = Path(__file__).parent / "icons" / "tss.png"
        self._popup_char_photo = None  # 参照保持でGC回避
        if char_path.exists():
            try:
                from PIL import Image, ImageTk
                img = Image.open(char_path).convert("RGBA")
                img = img.resize((100, 100), Image.LANCZOS)
                self._popup_char_photo = ImageTk.PhotoImage(img)
                char_label = tk.Label(top_row, image=self._popup_char_photo,
                                       bg=BG)
                char_label.pack(side=tk.LEFT, anchor="s", pady=(0, 5))
            except Exception:
                pass

        # 区切り線
        tk.Frame(content, bg="#555555", height=1).pack(fill=tk.X, pady=(8, 6))

        # テキスト情報エリア
        info_frame = tk.Frame(content, bg=BG)
        info_frame.pack(fill=tk.X)

        def row(label, value, color="white"):
            r = tk.Frame(info_frame, bg=BG)
            r.pack(fill=tk.X, pady=2)
            tk.Label(r, text=label, font=("Meiryo", 11), bg=BG,
                     fg=ACCENT, anchor="w").pack(side=tk.LEFT)
            tk.Label(r, text=value, font=("Meiryo", 12, "bold"), bg=BG,
                     fg=color, anchor="e").pack(side=tk.RIGHT)

        def sub_row(text):
            tk.Label(info_frame, text=text, font=("Meiryo", 10), bg=BG,
                     fg="#888888", anchor="e").pack(fill=tk.X, pady=(0, 1))

        data = self._usage_data
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
                c = config.get_remaining_color(rem, "session")
                row(i18n.t("session_5h"), i18n.t("remaining_pct", value=f"{rem:.0f}"), c)
                if fr:
                    rs = _format_reset_time(fr)
                    if rs:
                        sub_row(rs)
            if sd is not None:
                rem = max(0.0, 100.0 - sd)
                c = config.get_remaining_color(rem, "session")
                row(i18n.t("weekly_all"), i18n.t("remaining_pct", value=f"{rem:.0f}"), c)
                if sr:
                    rs = _format_reset_time(sr)
                    if rs:
                        sub_row(rs)
            if sn is not None:
                rem = max(0.0, 100.0 - sn)
                c = config.get_remaining_color(rem, "session")
                row(i18n.t("weekly_sonnet"), i18n.t("remaining_pct", value=f"{rem:.0f}"), c)
            if ee:
                if eu is None:
                    row(i18n.t("extra_usage"), i18n.t("extra_unlimited"),
                        config.REMAINING_COLOR_GREEN)
                else:
                    rem = max(0.0, 100.0 - eu)
                    c = config.get_remaining_color(rem, "extra")
                    row(i18n.t("extra_usage"), i18n.t("remaining_pct", value=f"{rem:.0f}"), c)
        else:
            tk.Label(info_frame, text=i18n.t("api_data_pending"),
                     font=("Meiryo", 12), bg=BG, fg="#95a5a6").pack(pady=15)

        # フッター
        link = tk.Frame(popup, bg=BG)
        link.pack(fill=tk.X, padx=12, pady=(0, 8))
        lbl = tk.Label(link, text=f"{i18n.t('open_dashboard')} →", font=("Meiryo", 10),
                       bg=BG, fg=ACCENT, cursor="hand2")
        lbl.pack(anchor="e")
        lbl.bind("<Button-1>", lambda e: (popup.destroy(), self._show_dashboard()))

        auto_close_id = popup.after(8000, popup.destroy)

        def _on_popup_click(e):
            try:
                popup.after_cancel(auto_close_id)
            except Exception:
                pass
            try:
                popup.destroy()
            except Exception:
                pass

        popup.bind("<Button-1>", _on_popup_click)
        popup.bind("<FocusOut>", lambda e: popup.destroy())
        popup.focus_set()

    # ════════════════════════════════════════════
    # F-18: ミニウィジェット（フローティング残量表示）
    # ════════════════════════════════════════════

    def _toggle_mini_widget(self, icon=None, item=None):
        """ミニウィジェットの表示/非表示を切り替える。"""
        if not self.app_gui or self._stop_event.is_set():
            return
        self.app_gui.after(0, self._do_toggle_mini_widget)

    def _do_toggle_mini_widget(self):
        if self._mini_widget and self._mini_widget.winfo_exists():
            self._mini_widget.destroy()
            self._mini_widget = None
        else:
            self._create_mini_widget()

    def _create_mini_widget(self):
        """F-18: ミニウィジェット作成（キャラ→時計盤→テキスト 縦配置）。"""
        import tkinter as tk
        from gui import draw_clock_on_canvas

        BG = "#2c2c2c"
        self._widget_clock_size = config.MINI_WIDGET_SIZE
        sz = self._widget_clock_size
        pad = max(6, sz // 25)

        w = tk.Toplevel(self.app_gui)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.configure(bg=BG)
        self._mini_widget = w

        # 外側パディング付きフレーム
        outer = tk.Frame(w, bg=BG, padx=pad, pady=pad)
        outer.pack(fill=tk.BOTH, expand=True)
        self._widget_outer = outer

        # ── (1) キャラクター画像（上部中央） ──
        self._widget_char_photo = None
        self._widget_char_img_original = None
        self._widget_char_label = None
        char_path = Path(__file__).parent / "icons" / "tss.png"
        if char_path.exists():
            try:
                from PIL import Image, ImageTk
                self._widget_char_img_original = Image.open(char_path).convert("RGBA")
                char_sz = max(30, sz // 4)
                img = self._widget_char_img_original.resize(
                    (char_sz, char_sz), Image.LANCZOS)
                self._widget_char_photo = ImageTk.PhotoImage(img)
                self._widget_char_label = tk.Label(
                    outer, image=self._widget_char_photo, bg=BG)
                self._widget_char_label.pack(pady=(0, 4))
            except Exception:
                pass

        # ── (2) 時計盤Canvas（中央） ──
        self._widget_canvas = tk.Canvas(outer, width=sz, height=sz,
                                         bg=BG, highlightthickness=0)
        self._widget_canvas.pack(pady=(0, 6))

        # ── (3) テキスト情報（下部・左右分離レイアウト） ──
        font_sz = max(10, sz // 16)
        self._widget_text_frame = tk.Frame(outer, bg=BG)
        self._widget_text_frame.pack(fill=tk.X)

        ACCENT_W = "#E07B39"

        # Session行
        r1 = tk.Frame(self._widget_text_frame, bg=BG)
        r1.pack(fill=tk.X, pady=1)
        self._widget_session_lbl = tk.Label(
            r1, text="", font=("Meiryo", font_sz), bg=BG,
            fg=ACCENT_W, anchor="w")
        self._widget_session_lbl.pack(side=tk.LEFT)
        self._widget_session_val = tk.Label(
            r1, text="--", font=("Meiryo", font_sz, "bold"), bg=BG,
            fg="#888888", anchor="e")
        self._widget_session_val.pack(side=tk.RIGHT)
        self._widget_session_row = r1

        # Weekly行
        r2 = tk.Frame(self._widget_text_frame, bg=BG)
        r2.pack(fill=tk.X, pady=1)
        self._widget_weekly_lbl = tk.Label(
            r2, text="", font=("Meiryo", font_sz), bg=BG,
            fg=ACCENT_W, anchor="w")
        self._widget_weekly_lbl.pack(side=tk.LEFT)
        self._widget_weekly_val = tk.Label(
            r2, text="--", font=("Meiryo", font_sz, "bold"), bg=BG,
            fg="#888888", anchor="e")
        self._widget_weekly_val.pack(side=tk.RIGHT)
        self._widget_weekly_row = r2

        # Extra行
        r3 = tk.Frame(self._widget_text_frame, bg=BG)
        r3.pack(fill=tk.X, pady=1)
        self._widget_extra_lbl = tk.Label(
            r3, text="", font=("Meiryo", font_sz), bg=BG,
            fg=ACCENT_W, anchor="w")
        self._widget_extra_lbl.pack(side=tk.LEFT)
        self._widget_extra_val = tk.Label(
            r3, text="", font=("Meiryo", font_sz, "bold"), bg=BG,
            fg="#888888", anchor="e")
        self._widget_extra_val.pack(side=tk.RIGHT)
        self._widget_extra_row = r3

        # 初期描画
        draw_clock_on_canvas(self._widget_canvas, sz, self._usage_data,
                             show_numbers=(sz >= 120))
        self._update_widget_text()

        # 位置: 画面右下（自動サイズ計算）
        w.update_idletasks()
        total_w = w.winfo_reqwidth()
        total_h = w.winfo_reqheight()
        x = w.winfo_screenwidth() - total_w - 20
        y = w.winfo_screenheight() - total_h - 80
        w.geometry(f"{total_w}x{total_h}+{x}+{y}")

        # ドラッグ移動
        def start_drag(event):
            w._drag_x = event.x
            w._drag_y = event.y
            w._dragged = False

        def on_drag(event):
            w._dragged = True
            nx = w.winfo_x() + event.x - w._drag_x
            ny = w.winfo_y() + event.y - w._drag_y
            w.geometry(f"+{nx}+{ny}")

        def on_release(event):
            if not getattr(w, '_dragged', False):
                # ドラッグなし = クリック → Usage APIポーリング
                self._widget_poll_usage()

        w.bind("<ButtonPress-1>", start_drag)
        w.bind("<B1-Motion>", on_drag)
        w.bind("<ButtonRelease-1>", on_release)

        # 右クリックで閉じる
        w.bind("<Button-3>", lambda e: self._do_toggle_mini_widget())

        # ホイールで拡縮
        def on_mousewheel(event):
            delta = 20 if event.delta > 0 else -20
            new_size = max(120, min(400, self._widget_clock_size + delta))
            if new_size == self._widget_clock_size:
                return
            self._widget_clock_size = new_size
            config.MINI_WIDGET_SIZE = new_size
            config.save_settings()
            self._resize_mini_widget(new_size)

        w.bind("<MouseWheel>", on_mousewheel)

    def _resize_mini_widget(self, new_size):
        """ミニウィジェットのサイズを変更する（ホイール拡縮対応）。"""
        from gui import draw_clock_on_canvas

        sz = new_size
        pad = max(6, sz // 25)

        # 外側パディング更新
        self._widget_outer.config(padx=pad, pady=pad)

        # キャラクター画像リサイズ
        if self._widget_char_img_original and self._widget_char_label:
            try:
                from PIL import Image, ImageTk
                char_sz = max(30, sz // 4)
                img = self._widget_char_img_original.resize(
                    (char_sz, char_sz), Image.LANCZOS)
                self._widget_char_photo = ImageTk.PhotoImage(img)
                self._widget_char_label.config(image=self._widget_char_photo)
            except Exception:
                pass

        # Clock canvas リサイズ
        self._widget_canvas.config(width=sz, height=sz)

        # フォントリサイズ（ラベル + 値）
        font_sz = max(10, sz // 16)
        for lbl in (self._widget_session_lbl, self._widget_weekly_lbl, self._widget_extra_lbl):
            lbl.config(font=("Meiryo", font_sz))
        for val in (self._widget_session_val, self._widget_weekly_val, self._widget_extra_val):
            val.config(font=("Meiryo", font_sz, "bold"))

        # ラベルテキスト更新（サイズに応じた長短切替）
        self._update_widget_text()

        # 時計盤再描画
        draw_clock_on_canvas(self._widget_canvas, sz, self._usage_data,
                             show_numbers=(sz >= 120))

        # ウィンドウジオメトリ自動更新
        self._mini_widget.update_idletasks()
        total_w = self._mini_widget.winfo_reqwidth()
        total_h = self._mini_widget.winfo_reqheight()
        self._mini_widget.geometry(f"{total_w}x{total_h}")

    def _update_widget_text(self):
        """ミニウィジェットのテキスト情報を更新する（i18n対応・左右分離レイアウト）。"""
        if not hasattr(self, '_widget_session_lbl') or not self._widget_session_lbl:
            return

        sz = self._widget_clock_size
        # サイズ160px以上: フルラベル、未満: 略称
        if sz >= 160:
            s_pre = i18n.t("widget_session") + ":"
            w_pre = i18n.t("widget_weekly") + ":"
            e_pre = i18n.t("widget_extra") + ":"
        else:
            s_pre = "S:"
            w_pre = "W:"
            e_pre = "E:"

        data = self._usage_data
        if not data:
            self._widget_session_lbl.config(text=s_pre)
            self._widget_session_val.config(text="--", fg="#888888")
            self._widget_weekly_lbl.config(text=w_pre)
            self._widget_weekly_val.config(text="--", fg="#888888")
            self._widget_extra_lbl.config(text="")
            self._widget_extra_val.config(text="")
            return

        fh = data.get("five_hour_util")
        sd = data.get("seven_day_util")
        ee = data.get("extra_usage_is_enabled", False)
        eu = data.get("extra_usage_util")

        self._widget_session_lbl.config(text=s_pre)
        if fh is not None:
            rem = max(0.0, 100.0 - fh)
            c = config.get_remaining_color(rem, "session")
            self._widget_session_val.config(text=f"{rem:.0f}%", fg=c)
        else:
            self._widget_session_val.config(text="--", fg="#888888")

        self._widget_weekly_lbl.config(text=w_pre)
        if sd is not None:
            rem = max(0.0, 100.0 - sd)
            c = config.get_remaining_color(rem, "session")
            self._widget_weekly_val.config(text=f"{rem:.0f}%", fg=c)
        else:
            self._widget_weekly_val.config(text="--", fg="#888888")

        if ee:
            self._widget_extra_lbl.config(text=e_pre)
            if eu is None:
                self._widget_extra_val.config(
                    text="∞", fg=config.REMAINING_COLOR_GREEN)
            else:
                rem = max(0.0, 100.0 - eu)
                c = config.get_remaining_color(rem, "extra")
                self._widget_extra_val.config(text=f"{rem:.0f}%", fg=c)
        else:
            self._widget_extra_lbl.config(text="")
            self._widget_extra_val.config(text="")

    def _widget_poll_usage(self):
        """ミニウィジェット左クリック: Usage APIを即座にポーリング（3秒連打防止）。"""
        import time
        now = time.time()
        if now - self._widget_last_poll < 3:
            return
        self._widget_last_poll = now
        if self._usage_api_test_callback:
            self._usage_api_test_callback()
        elif hasattr(self, '_test_usage_api'):
            self._test_usage_api()

    def _update_mini_widget(self):
        """ミニウィジェットの時計盤とテキスト情報を更新する。"""
        if not self._mini_widget or not self._mini_widget.winfo_exists():
            return
        try:
            from gui import draw_clock_on_canvas
            sz = self._widget_clock_size
            draw_clock_on_canvas(self._widget_canvas, sz, self._usage_data,
                                 show_numbers=(sz >= 120))
            self._update_widget_text()
        except Exception:
            pass

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
        delta = dt_reset - datetime.now(timezone.utc).replace(tzinfo=None)
        if delta.total_seconds() <= 0:
            return i18n.t("reset_done")
        h = int(delta.total_seconds() // 3600)
        m = int((delta.total_seconds() % 3600) // 60)
        return i18n.t("resets_in_hm", h=h, m=m) if h > 0 else i18n.t("resets_in_m", m=m)
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
                i18n.t("already_running")
            )
            root.destroy()
            sys.exit(0)
        app = UsageTrackerApp()
        app.run()
    except Exception as e:
        _debug(f"致命的エラー: {traceback.format_exc()}")
        logger.error("致命的エラー: %s", e, exc_info=True)
