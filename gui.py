"""Usage Tracker - tkinter GUIメインウィンドウ（i18n対応）"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import math
import os
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import config
import database
import charts
import i18n
from period_selector import PeriodSelector

logger = logging.getLogger(__name__)

_ACTIVITY_COLS = ("time", "project", "model", "cost", "detail")


def _time_to_angle_static(h: int, m: int) -> float:
    """時:分をtkinter Canvasの角度（度）に変換。12時=90°、時計回り=角度減少。"""
    return 90 - ((h % 12) * 30 + m * 0.5)


def draw_clock_on_canvas(canvas: tk.Canvas, size: int, data: Optional[dict] = None,
                         show_numbers: bool = True):
    """アナログ時計盤を描画する共通関数（残量タブ・ミニウィジェット・ポップアップ共通）。"""
    canvas.delete("all")
    cx, cy = size // 2, size // 2
    radius = size // 2 - max(10, size // 30)

    # 背景円
    canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                       fill="#2c2c2c", outline="#555555", width=2)

    # 現在時刻（JST = UTC+9）
    now_jst = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=9)
    h_now, m_now = now_jst.hour, now_jst.minute

    # Usage APIデータから3パターン分岐
    arc_pct = 0.0
    arc_mode = "session"
    show_arc = False
    dead = False
    reset_time_jst = None
    five_hour_resets_at = None

    if data:
        fh = data.get("five_hour_util")
        extra_enabled = data.get("extra_usage_is_enabled", False)
        extra_util = data.get("extra_usage_util")

        if fh is not None and fh >= 100:
            if extra_enabled:
                if extra_util is None:
                    arc_pct = 100.0
                else:
                    arc_pct = max(0.0, 100.0 - extra_util)
                arc_mode = "extra"
                show_arc = True
            else:
                dead = True
        elif fh is not None:
            arc_pct = max(0.0, 100.0 - fh)
            arc_mode = "session"
            show_arc = True

        fr = data.get("five_hour_resets_at")
        five_hour_resets_at = fr
        if fr:
            try:
                ts = fr[:19]
                fmt = '%Y-%m-%dT%H:%M:%S' if 'T' in ts else '%Y-%m-%d %H:%M:%S'
                dt_utc = datetime.strptime(ts, fmt)
                reset_time_jst = dt_utc + timedelta(hours=9)
            except Exception:
                pass

    # 弧を描画（ペース比率で色を決定）
    if show_arc and reset_time_jst:
        # ペース色ロジック: セッション残量の弧にはペース比率で色を決定
        if arc_mode == "session" and five_hour_resets_at:
            try:
                ts = five_hour_resets_at[:19]
                fmt = '%Y-%m-%dT%H:%M:%S' if 'T' in ts else '%Y-%m-%d %H:%M:%S'
                dt_reset_utc = datetime.strptime(ts, fmt)
                now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
                session_start = dt_reset_utc - timedelta(hours=5)
                elapsed_seconds = (now_utc - session_start).total_seconds()
                elapsed_pct = max(0.0, min(100.0, elapsed_seconds / (5 * 3600) * 100))
                arc_color = config.get_session_pace_color(arc_pct, elapsed_pct)
            except Exception:
                arc_color = config.get_remaining_color(arc_pct, arc_mode)
        else:
            arc_color = config.get_remaining_color(arc_pct, arc_mode)

        # v3.5.1: 弧の角度 = 残量% × 150°（5時間 = 12h時計上で150°）
        # 弧の終端 = リセット時刻の位置
        # 弧の始端 = リセット時刻から「残量%×5時間」分だけ反時計回りに戻った位置
        reset_angle = _time_to_angle_static(reset_time_jst.hour, reset_time_jst.minute)
        arc_degrees = arc_pct / 100.0 * 150.0  # 5h = 150° on 12h clock
        if arc_degrees > 0:
            start_angle = reset_angle + arc_degrees  # リセットから逆方向に戻る
            extent = -arc_degrees  # 時計回りにリセット位置まで描画

            arc_margin = max(25, size // 12)
            canvas.create_arc(
                cx - radius + arc_margin, cy - radius + arc_margin,
                cx + radius - arc_margin, cy + radius - arc_margin,
                start=start_angle, extent=extent,
                fill=arc_color, outline="", stipple=""
            )

    # 分の目盛り（細い線）
    for i in range(60):
        if i % 5 == 0:
            continue
        angle_rad = math.radians(90 - i * 6)
        tick_outer = radius - max(5, size // 60)
        tick_inner = radius - max(10, size // 30)
        x1 = cx + tick_outer * math.cos(angle_rad)
        y1 = cy - tick_outer * math.sin(angle_rad)
        x2 = cx + tick_inner * math.cos(angle_rad)
        y2 = cy - tick_inner * math.sin(angle_rad)
        canvas.create_line(x1, y1, x2, y2, fill="#555555", width=1)

    # 時間の目盛り（太い線）+ 数字
    for i in range(12):
        angle_rad = math.radians(90 - i * 30)
        tick_outer = radius - max(5, size // 60)
        tick_inner = radius - max(18, size // 17)
        x1 = cx + tick_outer * math.cos(angle_rad)
        y1 = cy - tick_outer * math.sin(angle_rad)
        x2 = cx + tick_inner * math.cos(angle_rad)
        y2 = cy - tick_inner * math.sin(angle_rad)
        canvas.create_line(x1, y1, x2, y2, fill="white", width=2)
        if show_numbers:
            num = i if i > 0 else 12
            num_r = radius - max(30, size // 10)
            x_num = cx + num_r * math.cos(angle_rad)
            y_num = cy - num_r * math.sin(angle_rad)
            font_size = max(7, size // 27)
            canvas.create_text(x_num, y_num, text=str(num),
                               fill="white", font=(config.FONT_FAMILY, font_size))

    # 短針（時針）
    h_angle = math.radians(_time_to_angle_static(h_now, m_now))
    hand_width = max(3, size // 60)
    hx = cx + (radius * 0.45) * math.cos(h_angle)
    hy = cy - (radius * 0.45) * math.sin(h_angle)
    canvas.create_line(cx, cy, hx, hy, fill="white", width=hand_width, capstyle=tk.ROUND)

    # 長針（分針）— 短針と同じ太さ
    m_angle = math.radians(90 - m_now * 6)
    mx = cx + (radius * 0.65) * math.cos(m_angle)
    my = cy - (radius * 0.65) * math.sin(m_angle)
    canvas.create_line(cx, cy, mx, my, fill="#cccccc", width=hand_width, capstyle=tk.ROUND)

    # 中心の点
    dot_r = max(3, size // 60)
    canvas.create_oval(cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r, fill="white", outline="")

    # パターン3: セッション使い切り + 追加OFF → グレーアウト
    if dead:
        canvas.create_oval(cx - radius + 5, cy - radius + 5,
                           cx + radius - 5, cy + radius - 5,
                           fill="#444444", outline="", stipple="gray50")
        font_size = max(9, size // 23)
        canvas.create_text(cx, cy, text=i18n.t("clock_session_exhausted"),
                           fill="white", font=(config.FONT_FAMILY, font_size, "bold"))

_LANG_OPTIONS = [("English", "en"), ("日本語", "ja")]
_LANG_DISPLAY = {code: name for name, code in _LANG_OPTIONS}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(i18n.t("app_title", version=config.VERSION))
        self.geometry(f"{config.MIN_WIDTH}x{config.MIN_HEIGHT}")
        self.minsize(config.MIN_WIDTH, config.MIN_HEIGHT)
        self.configure(bg=config.BG_COLOR)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._scan_callback = None
        self._quit_callback = None
        self._usage_api_test_callback = None

        self._activity_sort_col = None
        self._activity_sort_reverse = False
        self._dash_since = self._dash_until = None
        self._analysis_since = self._analysis_until = None
        self._activity_since = self._activity_until = None

        # 残量タブ用
        self._remaining_data = None
        self._clock_timer_id = None

        # アクティビティ更新抑制用
        self._pending_usage_update = None

        style = ttk.Style()
        style.configure("TNotebook.Tab", font=config.FONT)
        style.configure("Treeview", font=config.FONT, rowheight=22)
        style.configure("Treeview.Heading", font=config.FONT_BOLD)

        self._build_menu()
        self._build_notebook()
        self._build_status_bar()

    def _on_close(self):
        self.withdraw()

    def _build_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label=i18n.t("menu_scan_now"), command=self._request_scan)
        file_menu.add_separator()
        file_menu.add_command(label=i18n.t("menu_exit"), command=self._quit_app)
        menubar.add_cascade(label=i18n.t("menu_file"), menu=file_menu)
        self.config(menu=menubar)

    def _build_notebook(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.tab_remaining = ttk.Frame(self.notebook)
        self.tab_dashboard = ttk.Frame(self.notebook)
        self.tab_analysis = ttk.Frame(self.notebook)
        self.tab_activity = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_remaining, text=i18n.t("tab_remaining"))
        self.notebook.add(self.tab_dashboard, text=i18n.t("tab_dashboard"))
        self.notebook.add(self.tab_analysis, text=i18n.t("tab_analysis"))
        self.notebook.add(self.tab_activity, text=i18n.t("tab_activity"))
        self.notebook.add(self.tab_settings, text=i18n.t("tab_settings"))
        self._build_remaining_tab()
        self._build_dashboard_tab()
        self._build_analysis_tab()
        self._build_activity_tab()
        self._build_settings_tab()
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _build_status_bar(self):
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self.status_var, bd=1, relief=tk.SUNKEN,
                 anchor=tk.W, font=config.FONT, bg=config.BG_COLOR, padx=5
                 ).pack(side=tk.BOTTOM, fill=tk.X)

    def set_status(self, msg: str):
        self.status_var.set(msg)
        try:
            self.update_idletasks()
        except Exception:
            pass

    # ════════════════════════════════════════════
    # 残量タブ
    # ════════════════════════════════════════════
    def _build_remaining_tab(self):
        p = self.tab_remaining

        # 上部バー: 最終更新時刻(左) + 更新ボタン(右)
        top_bar = tk.Frame(p, bg=config.BG_COLOR)
        top_bar.pack(fill=tk.X, padx=10, pady=(5, 0))
        self._rem_last_update = tk.Label(
            top_bar, text="", font=config.FONT_SMALL,
            bg=config.BG_COLOR, fg="#999999", anchor="w"
        )
        self._rem_last_update.pack(side=tk.LEFT, padx=5)
        self._rem_refresh_btn = tk.Button(
            top_bar, text=i18n.t("btn_remaining_refresh"), font=config.FONT,
            bg=config.ACCENT_COLOR, fg="white", relief=tk.FLAT,
            command=self._on_remaining_refresh
        )
        self._rem_refresh_btn.pack(side=tk.RIGHT, padx=5)

        # ── 2カラム grid レイアウト ──
        grid = tk.Frame(p, bg=config.BG_COLOR)
        grid.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.rowconfigure(0, weight=1)
        grid.rowconfigure(1, weight=0)  # 区切り線
        grid.rowconfigure(2, weight=0)
        grid.rowconfigure(3, weight=0)

        # ═══ 上段左: 時計盤 + セッション情報 ═══
        top_left = tk.Frame(grid, bg=config.BG_COLOR)
        top_left.grid(row=0, column=0, sticky="", padx=5, pady=5)

        self._clock_size = 300
        self._clock_canvas = tk.Canvas(
            top_left, width=self._clock_size, height=self._clock_size,
            bg=config.BG_COLOR, highlightthickness=0
        )
        self._clock_canvas.pack()

        # セッション (5h) テキスト — 時計盤の下、中央揃え
        self._rem_session_frame = tk.Frame(top_left, bg=config.BG_COLOR)
        self._rem_session_frame.pack(fill=tk.X, pady=(8, 0))
        tk.Label(self._rem_session_frame, text=i18n.t("session_5h"),
                 font=config.FONT_BOLD, bg=config.BG_COLOR, fg="#555555",
                 anchor="center").pack(fill=tk.X)
        self._rem_session_pct = tk.Label(self._rem_session_frame, text="--",
                                          font=(config.FONT_FAMILY, 18, "bold"),
                                          bg=config.BG_COLOR, fg="#888888", anchor="center")
        self._rem_session_pct.pack(fill=tk.X)
        self._rem_session_reset = tk.Label(self._rem_session_frame, text="",
                                            font=config.FONT, bg=config.BG_COLOR,
                                            fg="#888888", anchor="center")
        self._rem_session_reset.pack(fill=tk.X)

        # ═══ 上段右: ミニグラフ + 週間情報 ═══
        top_right = tk.Frame(grid, bg=config.BG_COLOR)
        top_right.grid(row=0, column=1, sticky="new", padx=5, pady=5)

        self._pace_graph = tk.Canvas(
            top_right, height=self._clock_size,
            bg="#2c2c2c", highlightthickness=1, highlightbackground="#555555"
        )
        self._pace_graph.pack(fill=tk.X)

        # 週間 (全モデル) テキスト — グラフの下
        self._rem_weekly_frame = tk.Frame(top_right, bg=config.BG_COLOR)
        self._rem_weekly_frame.pack(fill=tk.X, pady=(8, 0))
        tk.Label(self._rem_weekly_frame, text=i18n.t("weekly_all"),
                 font=config.FONT_BOLD, bg=config.BG_COLOR, fg="#555555",
                 anchor="center").pack(fill=tk.X)
        self._rem_weekly_pct = tk.Label(self._rem_weekly_frame, text="--",
                                         font=(config.FONT_FAMILY, 18, "bold"),
                                         bg=config.BG_COLOR, fg="#888888", anchor="center")
        self._rem_weekly_pct.pack(fill=tk.X)
        self._rem_weekly_reset = tk.Label(self._rem_weekly_frame, text="",
                                           font=config.FONT, bg=config.BG_COLOR,
                                           fg="#888888", anchor="center")
        self._rem_weekly_reset.pack(fill=tk.X)
        self._rem_weekly_digital = tk.Label(self._rem_weekly_frame, text="",
                                             font=config.FONT, bg=config.BG_COLOR,
                                             fg="#888888", anchor="center")
        self._rem_weekly_digital.pack(fill=tk.X)
        self._pace_warn_label = tk.Label(
            self._rem_weekly_frame, text="", font=(config.FONT_FAMILY, 9),
            bg=config.BG_COLOR, fg="#888888", anchor="center"
        )
        self._pace_warn_label.pack(fill=tk.X, pady=(2, 0))

        # ═══ 区切り線 ═══
        sep = tk.Frame(grid, bg="#cccccc", height=1)
        sep.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=(8, 4))

        # ═══ 下段左: 追加使用量 ═══
        self._rem_extra_frame = tk.Frame(grid, bg=config.BG_COLOR)
        self._rem_extra_frame.grid(row=2, column=0, sticky="", padx=5, pady=(4, 0))
        self._rem_extra_label = tk.Label(self._rem_extra_frame, text=i18n.t("extra_usage"),
                 font=config.FONT_BOLD, bg=config.BG_COLOR, fg="#555555",
                 anchor="center")
        self._rem_extra_label.pack(fill=tk.X)
        self._rem_extra_pct = tk.Label(self._rem_extra_frame, text="--",
                                        font=(config.FONT_FAMILY, 16, "bold"),
                                        bg=config.BG_COLOR, fg="#888888", anchor="center")
        self._rem_extra_pct.pack(fill=tk.X)

        # ═══ 下段右: 週間 (Sonnet) ═══
        self._rem_sonnet_frame = tk.Frame(grid, bg=config.BG_COLOR)
        self._rem_sonnet_frame.grid(row=2, column=1, sticky="", padx=5, pady=(4, 0))
        tk.Label(self._rem_sonnet_frame, text=i18n.t("weekly_sonnet"),
                 font=config.FONT_BOLD, bg=config.BG_COLOR, fg="#555555",
                 anchor="center").pack(fill=tk.X)
        self._rem_sonnet_pct = tk.Label(self._rem_sonnet_frame, text="--",
                                         font=(config.FONT_FAMILY, 16, "bold"),
                                         bg=config.BG_COLOR, fg="#888888", anchor="center")
        self._rem_sonnet_pct.pack(fill=tk.X)

        # ═══ キャラクター (下部中央) ═══
        self._char_photo = None
        char_path = Path(__file__).parent / "icons" / "tss.png"
        if char_path.exists():
            try:
                from PIL import Image, ImageTk
                img = Image.open(char_path).convert("RGBA")
                img = img.resize((60, 60), Image.LANCZOS)
                self._char_photo = ImageTk.PhotoImage(img)
                char_label = tk.Label(grid, image=self._char_photo, bg=config.BG_COLOR)
                char_label.grid(row=3, column=0, columnspan=2, pady=(5, 0))
            except Exception:
                pass

        # 待機中メッセージ（初期表示用、上段右に配置）
        self._rem_no_data = tk.Label(top_right, text=i18n.t("remaining_no_data"),
                                      font=config.FONT, bg=config.BG_COLOR, fg="#999999")
        self._rem_no_data.pack(fill=tk.X, pady=5)

        # 初期描画（時計のみ、データなし）
        self._draw_clock_face()
        self._start_clock_timer()

    def _on_remaining_refresh(self):
        """残量タブの更新ボタン押下時。"""
        self._rem_refresh_btn.config(state=tk.DISABLED)
        if self._usage_api_test_callback:
            self._usage_api_test_callback()
        # 3秒後にボタンを再有効化（連打防止）
        self.after(3000, lambda: self._rem_refresh_btn.config(state=tk.NORMAL))

    def _draw_clock_face(self):
        """アナログ時計盤を描画する（共通関数を呼び出す）。"""
        draw_clock_on_canvas(self._clock_canvas, self._clock_size, self._remaining_data)

    def _start_clock_timer(self):
        """毎分時計盤を更新するタイマーを開始する。"""
        self._draw_clock_face()
        self._clock_timer_id = self.after(60000, self._start_clock_timer)

    def update_remaining_tab(self, data: Optional[dict]):
        """Usage APIデータで残量タブを更新する。"""
        if data is None:
            return
        self._remaining_data = data
        self._draw_clock_face()

        # 最終更新時刻を更新
        now_jst = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=9)
        self._rem_last_update.config(
            text=i18n.t("last_update", time=now_jst.strftime('%H:%M:%S'))
        )

        fh = data.get("five_hour_util")
        sd = data.get("seven_day_util")
        sn = data.get("seven_day_sonnet_util")
        ee = data.get("extra_usage_is_enabled", False)
        eu = data.get("extra_usage_util")
        fr = data.get("five_hour_resets_at")
        sr = data.get("seven_day_resets_at")

        has_data = any(v is not None for v in [fh, sd, sn])
        self._rem_no_data.pack_forget() if has_data else self._rem_no_data.pack(fill=tk.X, pady=5)

        is_exhausted = fh is not None and fh >= 100

        # ── セッション (5h) ──
        if fh is not None:
            if is_exhausted:
                self._rem_session_pct.config(
                    text=i18n.t("clock_session_exhausted"),
                    fg="#e74c3c", font=(config.FONT_FAMILY, 14, "bold")
                )
                self._rem_session_reset.config(text="")
            else:
                rem = max(0.0, 100.0 - fh)
                c = config.get_remaining_color(rem, "session")
                self._rem_session_pct.config(
                    text=i18n.t("remaining_pct", value=f"{rem:.0f}"),
                    fg=c, font=(config.FONT_FAMILY, 18, "bold")
                )
                if fr:
                    self._rem_session_reset.config(text=self._format_reset_label(fr))
        else:
            self._rem_session_pct.config(text="--", fg="#888888",
                                          font=(config.FONT_FAMILY, 18, "bold"))
            self._rem_session_reset.config(text="")

        # ── 週間 (全モデル) ──
        if sd is not None:
            rem = max(0.0, 100.0 - sd)
            c = config.get_remaining_color(rem, "session")
            self._rem_weekly_pct.config(
                text=i18n.t("remaining_pct", value=f"{rem:.0f}"), fg=c
            )
            if sr:
                self._rem_weekly_reset.config(text=self._format_reset_label(sr))
                self._rem_weekly_digital.config(text=self._format_reset_digital(sr))
        else:
            self._rem_weekly_pct.config(text="--", fg="#888888")
            self._rem_weekly_reset.config(text="")
            self._rem_weekly_digital.config(text="")

        # ── 週間 (Sonnet) ──
        if sn is not None:
            rem = max(0.0, 100.0 - sn)
            c = config.get_remaining_color(rem, "session")
            self._rem_sonnet_pct.config(
                text=i18n.t("remaining_pct", value=f"{rem:.0f}"), fg=c
            )
        else:
            self._rem_sonnet_pct.config(text="--", fg="#888888")

        # ── 追加使用量 ──
        if ee:
            self._rem_extra_frame.grid()
            if is_exhausted:
                # セッション枯渇時: 追加使用量を大きく目立たせる
                self._rem_extra_pct.config(font=(config.FONT_FAMILY, 20, "bold"))
            else:
                self._rem_extra_pct.config(font=(config.FONT_FAMILY, 16, "bold"))

            if eu is None:
                self._rem_extra_pct.config(text=i18n.t("extra_unlimited"),
                                            fg=config.REMAINING_COLOR_GREEN)
            else:
                rem = max(0.0, 100.0 - eu)
                c = config.get_remaining_color(rem, "extra")
                self._rem_extra_pct.config(
                    text=i18n.t("remaining_pct", value=f"{rem:.0f}"), fg=c
                )
        else:
            self._rem_extra_frame.grid()
            self._rem_extra_pct.config(
                text=i18n.t("extra_unused"), fg="#888888",
                font=(config.FONT_FAMILY, 16, "bold")
            )

        # ミニグラフ更新
        self._draw_pace_graph(data)

    def _draw_pace_graph(self, data: dict):
        """週間消費ペースのミニグラフを描画する。"""
        canvas = self._pace_graph
        canvas.update_idletasks()
        canvas.delete("all")
        cw = canvas.winfo_width()
        if cw < 100:
            cw = 600  # 初回描画時のフォールバック
        ch = int(canvas.cget("height"))
        pad_l, pad_r, pad_t, pad_b = 45, 80, 20, 30
        gw = cw - pad_l - pad_r
        gh = ch - pad_t - pad_b

        sr = data.get("seven_day_resets_at")
        sd_util = data.get("seven_day_util")
        if sd_util is None:
            return

        remaining_pct = max(0.0, 100.0 - sd_util)

        # リセットまでの残り日数
        days_remaining = 7.0
        dt_reset = None
        if sr:
            try:
                ts = sr[:19]
                fmt = '%Y-%m-%dT%H:%M:%S' if 'T' in ts else '%Y-%m-%d %H:%M:%S'
                dt_reset = datetime.strptime(ts, fmt)
                delta = dt_reset - datetime.now(timezone.utc).replace(tzinfo=None)
                days_remaining = max(0.01, delta.total_seconds() / 86400)
            except Exception:
                pass

        days_elapsed = 7.0 - days_remaining

        # Y軸グリッド（0%, 50%, 100%）
        for pct_val in (0, 50, 100):
            y = pad_t + gh - (pct_val / 100.0) * gh
            canvas.create_line(pad_l, y, pad_l + gw, y, fill="#444444", width=1, dash=(2, 4))
            canvas.create_text(pad_l - 8, y, text=f"{pct_val}%",
                               fill="#999999", font=(config.FONT_FAMILY, 10), anchor="e")

        # X軸: 曜日ラベル（リセット起点で7日間）
        weekday_keys = ["weekday_mon", "weekday_tue", "weekday_wed",
                        "weekday_thu", "weekday_fri", "weekday_sat", "weekday_sun"]
        if dt_reset:
            reset_jst = dt_reset + timedelta(hours=9)
            start_jst = reset_jst - timedelta(days=7)
        else:
            now_jst = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=9)
            start_jst = now_jst - timedelta(days=days_elapsed)

        for d in range(7):
            day_dt = start_jst + timedelta(days=d)
            wdkey = weekday_keys[day_dt.weekday()]
            x = pad_l + (d / 7.0) * gw
            canvas.create_text(x, ch - 6, text=i18n.t(wdkey),
                               fill="#999999", font=(config.FONT_FAMILY, 9), anchor="s")

        # 基準ライン（100%→0%、明るいグレー太線）
        x_start = pad_l
        y_start = pad_t
        x_end = pad_l + gw
        y_end = pad_t + gh
        canvas.create_line(x_start, y_start, x_end, y_end,
                           fill="#aaaaaa", width=2)
        canvas.create_text(x_end + 4, y_end - 6, text=i18n.t("pace_label_ideal"),
                           fill="#aaaaaa", font=(config.FONT_FAMILY, 10), anchor="w")

        # 基準値（理想ペースでの残量）
        baseline = max(0.0, 100.0 * (1.0 - days_elapsed / 7.0))

        # 色判定
        if remaining_pct >= baseline * 1.10:
            line_color = config.REMAINING_COLOR_BLUE
            warn_key = "pace_ok"
        elif remaining_pct >= baseline * 0.95:
            line_color = config.REMAINING_COLOR_YELLOW
            warn_key = "pace_warn"
        else:
            line_color = config.REMAINING_COLOR_RED
            warn_key = "pace_danger"

        # 実消費ライン：始点(100%) → 終点(今の残量%) の直線1本
        now_x = pad_l + (days_elapsed / 7.0) * gw
        now_y = pad_t + gh - (remaining_pct / 100.0) * gh
        canvas.create_line(pad_l, pad_t, now_x, now_y,
                           fill=line_color, width=2)

        # 最新ポイントにマーカー
        canvas.create_oval(now_x - 5, now_y - 5, now_x + 5, now_y + 5,
                           fill=line_color, outline="white", width=1)
        canvas.create_text(now_x, now_y - 14, text=f"{remaining_pct:.0f}%",
                           fill=line_color, font=(config.FONT_FAMILY, 11, "bold"))

        # 「今」の縦点線 + ラベル
        canvas.create_line(now_x, pad_t, now_x, pad_t + gh,
                           fill="#cccccc", width=1, dash=(3, 3))
        canvas.create_text(now_x, pad_t - 5, text=i18n.t("pace_now"),
                           fill="#cccccc", font=(config.FONT_FAMILY, 9), anchor="s")

        # 実消費ラベル
        canvas.create_text(pad_l + gw + 4, pad_t + 6, text=i18n.t("pace_label_actual"),
                           fill=line_color, font=(config.FONT_FAMILY, 10), anchor="w")

        # 警告テキスト
        self._pace_warn_label.config(text=i18n.t(warn_key), fg=line_color)

    def _format_reset_label(self, resets_at: str) -> str:
        """リセット日時をラベル用にフォーマット。"""
        try:
            ts = resets_at[:19]
            fmt = '%Y-%m-%dT%H:%M:%S' if 'T' in ts else '%Y-%m-%d %H:%M:%S'
            dt_utc = datetime.strptime(ts, fmt)
            dt_jst = dt_utc + timedelta(hours=9)
            return i18n.t("reset_at_datetime", dt=dt_jst.strftime('%m/%d %H:%M'))
        except Exception:
            return ""

    def _format_reset_digital(self, resets_at: str) -> str:
        """リセットまでの残り時間をデジタル表示（「2日 14時間後」等）。"""
        try:
            ts = resets_at[:19]
            fmt = '%Y-%m-%dT%H:%M:%S' if 'T' in ts else '%Y-%m-%d %H:%M:%S'
            dt_reset = datetime.strptime(ts, fmt)
            delta = dt_reset - datetime.now(timezone.utc).replace(tzinfo=None)
            if delta.total_seconds() <= 0:
                return i18n.t("reset_done")
            total_hours = int(delta.total_seconds() // 3600)
            days = total_hours // 24
            hours = total_hours % 24
            mins = int((delta.total_seconds() % 3600) // 60)
            if days > 0:
                return i18n.t("reset_in_days_hours", days=days, hours=hours)
            elif hours > 0:
                return i18n.t("reset_in_hours_mins", hours=hours, mins=mins)
            else:
                return i18n.t("resets_in_m", m=mins)
        except Exception:
            return ""

    def _on_tab_changed(self, event=None):
        """タブ切替時に保留中の更新を反映する。"""
        if self._pending_usage_update is not None:
            data, error = self._pending_usage_update
            self._pending_usage_update = None
            self._apply_usage_update(data, error)

    # ════════════════════════════════════════════
    # ダッシュボード
    # ════════════════════════════════════════════
    def _build_dashboard_tab(self):
        p = self.tab_dashboard
        self._dash_period = PeriodSelector(p, on_change=self._on_dash_period_change, default="today")
        self._dash_period.pack(fill=tk.X, padx=10, pady=(5, 0))
        sf = tk.Frame(p, bg=config.BG_COLOR, pady=3)
        sf.pack(fill=tk.X, padx=10)
        self.lbl_period_label = tk.Label(sf, text="", font=config.FONT, bg=config.BG_COLOR, fg="#555555")
        self.lbl_period_label.pack(side=tk.LEFT, padx=(0, 10))
        self.lbl_today_input = tk.Label(sf, text="", font=config.FONT_BOLD, bg=config.BG_COLOR, fg="#333333")
        self.lbl_today_input.pack(side=tk.LEFT, padx=10)
        self.lbl_today_output = tk.Label(sf, text="", font=config.FONT_BOLD, bg=config.BG_COLOR, fg="#333333")
        self.lbl_today_output.pack(side=tk.LEFT, padx=10)
        self.lbl_today_cost = tk.Label(sf, text="", font=config.FONT_LARGE, bg=config.BG_COLOR, fg=config.ACCENT_COLOR)
        self.lbl_today_cost.pack(side=tk.LEFT, padx=15)
        self.lbl_today_count = tk.Label(sf, text="", font=config.FONT, bg=config.BG_COLOR, fg="#555555")
        self.lbl_today_count.pack(side=tk.LEFT, padx=10)
        gf = tk.Frame(p, bg=config.BG_COLOR)
        gf.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)
        self.hourly_canvas_frame = tk.Frame(gf, bg=config.BG_COLOR)
        self.hourly_canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.pie_canvas_frame = tk.Frame(gf, bg=config.BG_COLOR, width=260)
        self.pie_canvas_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(3, 5))
        self.pie_canvas_frame.pack_propagate(False)
        lf = tk.LabelFrame(p, text=i18n.t("recent_messages"), font=config.FONT, bg=config.BG_COLOR, padx=5, pady=3)
        lf.pack(fill=tk.X, padx=10, pady=(3, 5))
        cols = ("timestamp", "project", "model", "input", "output", "cost")
        self.recent_tree = ttk.Treeview(lf, columns=cols, show="headings", height=10)
        for c, w, key, anc in [("timestamp", 140, "col_time", "center"), ("project", 160, "col_project", "w"),
                                ("model", 100, "col_model", "center"), ("input", 80, "input_prefix", "e"),
                                ("output", 80, "output_prefix", "e"), ("cost", 80, "col_cost", "e")]:
            self.recent_tree.heading(c, text=i18n.t(key).rstrip(": "))
            self.recent_tree.column(c, width=w, anchor=anc)
        vsb = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=self.recent_tree.yview)
        self.recent_tree.configure(yscrollcommand=vsb.set)
        self.recent_tree.pack(side=tk.LEFT, fill=tk.X, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

    def _on_dash_period_change(self, since, until):
        self._dash_since, self._dash_until = since, until
        self._refresh_dashboard()

    def _refresh_dashboard(self):
        since, until = self._dash_since, self._dash_until
        s = database.query_summary(since, until)
        inp = s.get("input_tokens", 0) + s.get("cache_creation_tokens", 0) + s.get("cache_read_tokens", 0)
        out = s.get("output_tokens", 0)
        cnt = s.get("message_count", 0)
        rows = database.query_rows_for_cost(since, until)
        cost = sum(config.calc_cost(r.get("model", "default"), r.get("input_tokens", 0), r.get("output_tokens", 0), r.get("cache_creation_tokens", 0), r.get("cache_read_tokens", 0)) for r in rows)
        pl = self._dash_period.get_period_label()
        self.lbl_period_label.config(text=f"{i18n.t('period_prefix')}{pl}")
        self.lbl_today_input.config(text=f"{i18n.t('input_prefix')}{inp:,}")
        self.lbl_today_output.config(text=f"{i18n.t('output_prefix')}{out:,}")
        self.lbl_today_cost.config(text=f"{i18n.t('cost_prefix')}{cost:.3f}")
        self.lbl_today_count.config(text=f"{i18n.t('messages_prefix')}{cnt}")
        for w in self.hourly_canvas_frame.winfo_children():
            w.destroy()
        try:
            hd = database.query_hourly_tokens(since, until)
            fig = charts.make_hourly_bar_chart(hd, title=i18n.t("chart_token_consumption", period=pl))
            FigureCanvasTkAgg(fig, master=self.hourly_canvas_frame).get_tk_widget().pack(fill=tk.BOTH, expand=True)
        except Exception as e:
            logger.error("Chart error: %s", e)
        for w in self.pie_canvas_frame.winfo_children():
            w.destroy()
        try:
            md = database.query_model_stats(since, until)
            fig2 = charts.make_model_pie_chart(md, title=i18n.t("chart_by_model", period=pl))
            FigureCanvasTkAgg(fig2, master=self.pie_canvas_frame).get_tk_widget().pack(fill=tk.BOTH, expand=True)
        except Exception as e:
            logger.error("Chart error: %s", e)
        self.recent_tree.delete(*self.recent_tree.get_children())
        for r in database.query_recent_messages(50, since, until):
            ts = database.utc_to_jst_str(r.get("timestamp", ""))
            ti = r.get("input_tokens", 0) + r.get("cache_creation_tokens", 0) + r.get("cache_read_tokens", 0)
            c = config.calc_cost(r.get("model", "default"), r.get("input_tokens", 0), r.get("output_tokens", 0), r.get("cache_creation_tokens", 0), r.get("cache_read_tokens", 0))
            self.recent_tree.insert("", tk.END, values=(ts, r.get("project_name") or "", config.get_model_display(r.get("model") or ""), f'{ti:,}', f'{r.get("output_tokens", 0):,}', f"${c:.3f}"))

    # ════════════════════════════════════════════
    # 分析
    # ════════════════════════════════════════════
    def _build_analysis_tab(self):
        p = self.tab_analysis
        cf = tk.Frame(p, bg=config.BG_COLOR)
        cf.pack(fill=tk.X, padx=10, pady=(5, 0))
        tk.Label(cf, text=i18n.t("analysis_axis"), font=config.FONT_BOLD, bg=config.BG_COLOR).pack(side=tk.LEFT, padx=(0, 5))
        self._analysis_axis = tk.StringVar(value=i18n.t("axis_project"))
        self._analysis_combo = ttk.Combobox(cf, textvariable=self._analysis_axis, values=[i18n.t("axis_project"), i18n.t("axis_action")], state="readonly", width=15, font=config.FONT)
        self._analysis_combo.pack(side=tk.LEFT, padx=5)
        self._analysis_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_analysis())
        self._analysis_period = PeriodSelector(p, on_change=self._on_analysis_period_change, default="all")
        self._analysis_period.pack(fill=tk.X, padx=10, pady=(2, 0))
        self._analysis_canvas_frame = tk.Frame(p, bg=config.BG_COLOR)
        self._analysis_canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _on_analysis_period_change(self, since, until):
        self._analysis_since, self._analysis_until = since, until
        self._refresh_analysis()

    def _refresh_analysis(self):
        axis = self._analysis_axis.get()
        since, until = self._analysis_since, self._analysis_until
        for w in self._analysis_canvas_frame.winfo_children():
            w.destroy()
        try:
            if axis == i18n.t("axis_action"):
                fig = charts.make_tool_bar_chart(database.query_tool_stats(since, until))
            else:
                fig = charts.make_project_bar_chart(database.query_project_stats(since, until))
            FigureCanvasTkAgg(fig, master=self._analysis_canvas_frame).get_tk_widget().pack(fill=tk.BOTH, expand=True)
        except Exception as e:
            logger.error("Analysis chart error: %s", e)

    # ════════════════════════════════════════════
    # アクティビティ
    # ════════════════════════════════════════════
    def _build_activity_tab(self):
        p = self.tab_activity
        self._activity_period = PeriodSelector(p, on_change=self._on_activity_period_change, default="today")
        self._activity_period.pack(fill=tk.X, padx=10, pady=(5, 0))
        cf = tk.Frame(p, bg=config.BG_COLOR)
        cf.pack(fill=tk.X, padx=10, pady=2)
        tk.Button(cf, text=i18n.t("btn_refresh"), command=self._refresh_activity, font=config.FONT, bg=config.ACCENT_COLOR, fg="white", relief=tk.FLAT).pack(side=tk.RIGHT, padx=5)
        tf = tk.Frame(p)
        tf.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))
        self._activity_headings = {c: i18n.t(f"col_{c}") for c in _ACTIVITY_COLS}
        self.activity_tree = ttk.Treeview(tf, columns=_ACTIVITY_COLS, show="tree headings")
        self.activity_tree.column("#0", width=30, minwidth=30, stretch=False)
        for c, w, anc in [("time", 130, "center"), ("project", 160, "w"), ("model", 100, "center"), ("cost", 80, "e"), ("detail", 250, "w")]:
            self.activity_tree.heading(c, text=self._activity_headings[c], command=lambda col=c: self._sort_activity(col))
            self.activity_tree.column(c, width=w, anchor=anc)
        vsb = ttk.Scrollbar(tf, orient=tk.VERTICAL, command=self.activity_tree.yview)
        hsb = ttk.Scrollbar(tf, orient=tk.HORIZONTAL, command=self.activity_tree.xview)
        self.activity_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.activity_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _on_activity_period_change(self, since, until):
        self._activity_since, self._activity_until = since, until
        self._refresh_activity()

    def _sort_activity(self, col):
        if self._activity_sort_col == col:
            self._activity_sort_reverse = not self._activity_sort_reverse
        else:
            self._activity_sort_col = col
            self._activity_sort_reverse = False
        idx = list(_ACTIVITY_COLS).index(col)
        items = [(iid, self.activity_tree.item(iid, 'values')) for iid in self.activity_tree.get_children('')]
        if col == "cost":
            items.sort(key=lambda x: float(x[1][idx].replace('$', '').replace(',', '') or '0'), reverse=self._activity_sort_reverse)
        else:
            items.sort(key=lambda x: x[1][idx] if idx < len(x[1]) else "", reverse=self._activity_sort_reverse)
        for i, (iid, _) in enumerate(items):
            self.activity_tree.move(iid, '', i)
        for c in _ACTIVITY_COLS:
            txt = self._activity_headings[c]
            if c == col:
                txt += " \u25bc" if self._activity_sort_reverse else " \u25b2"
            self.activity_tree.heading(c, text=txt, command=lambda cc=c: self._sort_activity(cc))

    def _refresh_activity(self):
        since, until = self._activity_since, self._activity_until
        self.activity_tree.delete(*self.activity_tree.get_children())
        self._activity_sort_col = None
        self._activity_sort_reverse = False
        for c in _ACTIVITY_COLS:
            self.activity_tree.heading(c, text=self._activity_headings[c], command=lambda cc=c: self._sort_activity(cc))
        try:
            sessions = database.query_activity_log(since, until)
        except Exception as e:
            logger.error("Activity query error: %s", e)
            return
        for s in sessions:
            ts = database.utc_to_jst_str(s.get("first_ts", ""))
            messages = s.get("messages", [])
            all_tools = [t.get("tool_target", "")[:20] for msg in messages for t in msg.get("tools", [])]
            tool_summary = "\u3001".join(all_tools[:3])
            if len(all_tools) > 3:
                tool_summary += f" +{len(all_tools) - 3}"
            pid = self.activity_tree.insert("", tk.END, text="\u25b6", values=(ts, s.get("project_name") or "", config.get_model_display(s.get("model") or ""), f'${s.get("total_cost", 0):.3f}', tool_summary), open=False)
            for i, msg in enumerate(messages):
                ti = msg.get("input_tokens", 0) + msg.get("cache_creation_tokens", 0) + msg.get("cache_read_tokens", 0)
                tools = msg.get("tools", [])
                td = (tools[0].get("tool_target", "") + (f" +{len(tools)-1}" if len(tools) > 1 else "")) if tools else "text only"
                pfx = "  \u2514" if i == len(messages) - 1 else "  \u251c"
                self.activity_tree.insert(pid, tk.END, text=pfx, values=(database.utc_to_jst_str(msg.get("timestamp", "")), f"in {ti:,} / out {msg.get('output_tokens', 0):,}", "", f"${msg.get('cost', 0):.3f}", td))

    # ════════════════════════════════════════════
    # 設定
    # ════════════════════════════════════════════
    def _build_settings_tab(self):
        p = self.tab_settings
        canvas = tk.Canvas(p, bg=config.BG_COLOR, highlightthickness=0)
        sb = ttk.Scrollbar(p, orient=tk.VERTICAL, command=canvas.yview)
        sf = tk.Frame(canvas, bg=config.BG_COLOR)
        sf.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=sf, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", lambda ev: canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        # 基本情報
        inf = tk.LabelFrame(sf, text=i18n.t("basic_info"), font=config.FONT_BOLD, bg=config.BG_COLOR, padx=10, pady=10)
        inf.pack(fill=tk.X, padx=15, pady=10)
        for lbl, val in [(i18n.t("scan_path"), str(config.PROJECTS_DIR)), (i18n.t("database"), str(config.DB_PATH)), (i18n.t("log_folder"), str(config.LOG_DIR))]:
            r = tk.Frame(inf, bg=config.BG_COLOR)
            r.pack(fill=tk.X, pady=2)
            tk.Label(r, text=lbl, font=config.FONT_BOLD, bg=config.BG_COLOR, width=22, anchor="w").pack(side=tk.LEFT)
            tk.Label(r, text=val, font=config.FONT, bg=config.BG_COLOR, anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)

        # スキャン間隔
        ir = tk.Frame(inf, bg=config.BG_COLOR)
        ir.pack(fill=tk.X, pady=2)
        tk.Label(ir, text=i18n.t("auto_scan_interval"), font=config.FONT_BOLD, bg=config.BG_COLOR, width=22, anchor="w").pack(side=tk.LEFT)
        interval_labels = [i18n.t(k) for k in ("interval_10s", "interval_30s", "interval_1m", "interval_2m", "interval_5m")]
        interval_values = [10, 30, 60, 120, 300]
        self._interval_map = dict(zip(interval_labels, interval_values))
        self._interval_rmap = dict(zip(interval_values, interval_labels))
        self._interval_var = tk.StringVar(value=self._interval_rmap.get(config.SCAN_INTERVAL_SECONDS, i18n.t("interval_30s")))
        ttk.Combobox(ir, textvariable=self._interval_var, values=interval_labels, state="readonly", width=8, font=config.FONT).pack(side=tk.LEFT, padx=5)
        self._interval_var.trace_add("write", lambda *_: self._on_interval_change())

        self.lbl_rec_count = tk.Label(inf, text="", font=config.FONT_BOLD, bg=config.BG_COLOR, fg=config.ACCENT_COLOR)
        self.lbl_rec_count.pack(anchor="w", pady=(5, 0))

        # DB容量表示
        db_row = tk.Frame(inf, bg=config.BG_COLOR)
        db_row.pack(fill=tk.X, pady=2)
        tk.Label(db_row, text=i18n.t("db_size_label"), font=config.FONT_BOLD,
                 bg=config.BG_COLOR, width=22, anchor="w").pack(side=tk.LEFT)
        self.lbl_db_size = tk.Label(db_row, text="", font=config.FONT,
                                     bg=config.BG_COLOR, anchor="w")
        self.lbl_db_size.pack(side=tk.LEFT, padx=5)
        tk.Button(db_row, text=i18n.t("btn_optimize_db"), font=config.FONT,
                  bg=config.ACCENT_COLOR, fg="white", relief=tk.FLAT,
                  command=self._optimize_db).pack(side=tk.LEFT, padx=5)

        # 言語設定
        lang_frame = tk.LabelFrame(sf, text=i18n.t("language_label"), font=config.FONT_BOLD, bg=config.BG_COLOR, padx=10, pady=10)
        lang_frame.pack(fill=tk.X, padx=15, pady=(0, 10))
        lr = tk.Frame(lang_frame, bg=config.BG_COLOR)
        lr.pack(fill=tk.X, pady=2)
        tk.Label(lr, text=i18n.t("language_label"), font=config.FONT_BOLD, bg=config.BG_COLOR, width=22, anchor="w").pack(side=tk.LEFT)
        self._lang_var = tk.StringVar(value=_LANG_DISPLAY.get(config.LANGUAGE, "English"))
        lang_combo = ttk.Combobox(lr, textvariable=self._lang_var, values=[n for n, _ in _LANG_OPTIONS], state="readonly", width=12, font=config.FONT)
        lang_combo.pack(side=tk.LEFT, padx=5)
        lang_combo.bind("<<ComboboxSelected>>", self._on_lang_change)

        # 自動起動設定
        auto_frame = tk.LabelFrame(sf, text=i18n.t("autostart_section"), font=config.FONT_BOLD,
                                    bg=config.BG_COLOR, padx=10, pady=10)
        auto_frame.pack(fill=tk.X, padx=15, pady=(0, 10))
        self._autostart_var = tk.BooleanVar(value=config.is_autostart_enabled())
        self._autostart_cb = tk.Checkbutton(
            auto_frame, text=i18n.t("autostart_label"), variable=self._autostart_var,
            font=config.FONT, bg=config.BG_COLOR, activebackground=config.BG_COLOR,
            command=self._on_autostart_change
        )
        self._autostart_cb.pack(anchor="w")

        # OAuth認証
        af = tk.LabelFrame(sf, text=i18n.t("oauth_auth"), font=config.FONT_BOLD, bg=config.BG_COLOR, padx=10, pady=10)
        af.pack(fill=tk.X, padx=15, pady=(0, 10))
        from usage_api import UsageAPIClient
        ai = UsageAPIClient().get_auth_info()
        if ai["status"] == "ok":
            tk.Label(af, text=i18n.t("oauth_status_ok"), font=config.FONT_BOLD, bg=config.BG_COLOR, fg="#27ae60", anchor="w").pack(fill=tk.X)
            for line in [i18n.t("oauth_token", token=ai["token_masked"]), i18n.t("oauth_subscription", type=ai["subscription_type"]), i18n.t("oauth_path", path=ai["credentials_path"])]:
                tk.Label(af, text=line, font=config.FONT, bg=config.BG_COLOR, fg="#555555", anchor="w").pack(fill=tk.X, pady=1)
        else:
            tk.Label(af, text=i18n.t("oauth_status_error"), font=config.FONT_BOLD, bg=config.BG_COLOR, fg="#e74c3c", anchor="w").pack(fill=tk.X)
            tk.Label(af, text=ai.get("error", ""), font=config.FONT, bg=config.BG_COLOR, fg="#e74c3c", anchor="w").pack(fill=tk.X)

        # Usage API
        uf = tk.LabelFrame(sf, text=i18n.t("usage_api"), font=config.FONT_BOLD, bg=config.BG_COLOR, padx=10, pady=10)
        uf.pack(fill=tk.X, padx=15, pady=(0, 10))
        ar = tk.Frame(uf, bg=config.BG_COLOR)
        ar.pack(fill=tk.X, pady=2)
        tk.Label(ar, text=i18n.t("api_polling_interval"), font=config.FONT_BOLD, bg=config.BG_COLOR, width=22, anchor="w").pack(side=tk.LEFT)
        api_labels = [i18n.t(k) for k in ("interval_1m", "interval_2m", "interval_5m")]
        api_values = [60, 120, 300]
        self._api_interval_map = dict(zip(api_labels, api_values))
        self._api_interval_rmap = dict(zip(api_values, api_labels))
        self._api_interval_var = tk.StringVar(value=self._api_interval_rmap.get(config.USAGE_API_INTERVAL_SECONDS, i18n.t("interval_2m")))
        ttk.Combobox(ar, textvariable=self._api_interval_var, values=api_labels, state="readonly", width=8, font=config.FONT).pack(side=tk.LEFT, padx=5)
        self._api_interval_var.trace_add("write", lambda *_: self._on_api_interval_change())

        or_ = tk.Frame(uf, bg=config.BG_COLOR)
        or_.pack(fill=tk.X, pady=2)
        tk.Label(or_, text=i18n.t("org_id_label"), font=config.FONT_BOLD, bg=config.BG_COLOR, width=22, anchor="w").pack(side=tk.LEFT)
        self._orgid_entry = tk.Entry(or_, width=40, font=config.FONT)
        self._orgid_entry.insert(0, config.ORG_ID)
        self._orgid_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(or_, text=i18n.t("btn_save"), font=config.FONT, command=self._save_orgid).pack(side=tk.LEFT, padx=2)
        tk.Label(or_, text=i18n.t("org_id_hint"), font=config.FONT_SMALL, bg=config.BG_COLOR, fg="#999999").pack(side=tk.LEFT, padx=5)

        tr = tk.Frame(uf, bg=config.BG_COLOR)
        tr.pack(fill=tk.X, pady=(5, 2))
        tk.Button(tr, text=i18n.t("btn_api_test"), font=config.FONT, bg=config.ACCENT_COLOR, fg="white", relief=tk.FLAT, command=self._test_usage_api).pack(side=tk.LEFT)

        self.lbl_api_status = tk.Label(uf, text=i18n.t("api_status_untested"), font=config.FONT, bg=config.BG_COLOR, fg="#888888", anchor="w")
        self.lbl_api_status.pack(fill=tk.X, pady=(5, 0))
        self.lbl_api_data = tk.Label(uf, text="", font=config.FONT, bg=config.BG_COLOR, fg="#333333", anchor="w", justify=tk.LEFT)
        self.lbl_api_data.pack(fill=tk.X, pady=(2, 0))

        # ボタン群
        bf = tk.Frame(sf, bg=config.BG_COLOR)
        bf.pack(fill=tk.X, padx=15, pady=10)
        for txt, cmd in [(i18n.t("btn_scan_now"), self._request_scan), (i18n.t("btn_open_log"), self._open_log_folder), (i18n.t("btn_csv_export"), self._export_csv)]:
            tk.Button(bf, text=f"  {txt}  ", command=cmd, font=config.FONT, height=2, bg=config.ACCENT_COLOR, fg="white", relief=tk.FLAT).pack(side=tk.LEFT, padx=5)

        self._update_rec_count()

    def _on_interval_change(self):
        sec = self._interval_map.get(self._interval_var.get())
        if sec:
            config.SCAN_INTERVAL_SECONDS = sec
            config.save_settings()

    def _on_api_interval_change(self):
        sec = self._api_interval_map.get(self._api_interval_var.get())
        if sec:
            config.USAGE_API_INTERVAL_SECONDS = sec
            config.save_settings()

    def _on_autostart_change(self):
        """自動起動チェックボックスの状態変更。"""
        if self._autostart_var.get():
            ok = config.enable_autostart()
            if not ok:
                self._autostart_var.set(False)
        else:
            config.disable_autostart()

    def _on_lang_change(self, event=None):
        for name, code in _LANG_OPTIONS:
            if name == self._lang_var.get():
                if code == config.LANGUAGE:
                    return
                config.LANGUAGE = code
                config.save_settings()
                if messagebox.askyesno("Language", i18n.t("restart_required") + "\n\nRestart now?"):
                    self._restart_app()
                break

    def _restart_app(self):
        """アプリを自動再起動する。"""
        import subprocess
        import sys
        try:
            subprocess.Popen([sys.executable] + sys.argv)
        except Exception as e:
            logger.error("再起動失敗: %s", e)
            return
        if self._quit_callback:
            self._quit_callback()
        else:
            self.destroy()

    def _save_orgid(self):
        config.ORG_ID = self._orgid_entry.get().strip()
        config.save_settings()

    def _test_usage_api(self):
        self.lbl_api_status.config(text=i18n.t("api_status_testing"), fg="#f39c12")
        if self._usage_api_test_callback:
            self._usage_api_test_callback()

    def _is_user_browsing_activity(self) -> bool:
        """ユーザーがアクティビティタブを操作中かどうか判定する。"""
        try:
            current_tab = self.notebook.index(self.notebook.select())
            activity_tab_index = self.notebook.index(self.tab_activity)
            if current_tab != activity_tab_index:
                return False
        except Exception:
            return False
        # Treeviewにフォーカスがあるか
        try:
            if self.focus_get() == self.activity_tree:
                return True
        except Exception:
            pass
        # スクロール位置が先頭以外か
        try:
            first_visible = self.activity_tree.yview()[0]
            if first_visible > 0.01:
                return True
        except Exception:
            pass
        return False

    def update_usage_status(self, data: Optional[dict], error: Optional[str]):
        # アクティビティ閲覧中なら更新を保留
        if data and not error and self._is_user_browsing_activity():
            self._pending_usage_update = (data, error)
            return
        self._apply_usage_update(data, error)

    def _apply_usage_update(self, data: Optional[dict], error: Optional[str]):
        if error:
            self.lbl_api_status.config(text=i18n.t("api_status_error"), fg="#e74c3c")
            self.lbl_api_data.config(text=error, fg="#e74c3c")
            return
        if data:
            now_jst = database.utc_to_jst_str(datetime.now(timezone.utc).replace(tzinfo=None).isoformat())
            self.lbl_api_status.config(text=i18n.t("api_status_ok", time=now_jst), fg="#27ae60")
            lines = []
            fh, sd, sn = data.get("five_hour_util"), data.get("seven_day_util"), data.get("seven_day_sonnet_util")
            ee, eu = data.get("extra_usage_is_enabled", False), data.get("extra_usage_util")
            if fh is not None:
                lines.append(f"{i18n.t('session_5h')} {i18n.t('remaining_pct', value=f'{max(0,100-fh):.1f}')}")
            if sd is not None:
                lines.append(f"{i18n.t('weekly_all')} {i18n.t('remaining_pct', value=f'{max(0,100-sd):.1f}')}")
            if sn is not None:
                lines.append(f"{i18n.t('weekly_sonnet')} {i18n.t('remaining_pct', value=f'{max(0,100-sn):.1f}')}")
            if ee:
                lines.append(f"{i18n.t('extra_usage')} {i18n.t('extra_unlimited') if eu is None else i18n.t('remaining_pct', value=f'{max(0,100-eu):.1f}')}")
            self.lbl_api_data.config(text="\n".join(lines) or i18n.t("api_no_data"), fg="#333333")

    def _update_rec_count(self):
        self.lbl_rec_count.config(text=i18n.t("db_record_count", count=f"{database.get_total_record_count():,}"))
        try:
            size = database.get_db_size_mb()
            self.lbl_db_size.config(text=f"{size:.2f} MB")
        except Exception:
            pass

    def _optimize_db(self):
        """手動VACUUM実行。"""
        try:
            before = database.get_db_size_mb()
            database.vacuum_db()
            after = database.get_db_size_mb()
            self.lbl_db_size.config(text=i18n.t("db_optimized", before=f"{before:.2f}", after=f"{after:.2f}"))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _open_log_folder(self):
        try:
            config.LOG_DIR.mkdir(parents=True, exist_ok=True)
            os.startfile(str(config.LOG_DIR))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialfile="claude_usage_export.csv")
        if not path:
            return
        try:
            with database.get_conn() as conn:
                rows = conn.execute("SELECT * FROM token_log ORDER BY timestamp DESC").fetchall()
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                if rows:
                    w = csv.DictWriter(f, fieldnames=rows[0].keys())
                    w.writeheader()
                    w.writerows([dict(r) for r in rows])
            messagebox.showinfo("Export", f"Saved:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def set_scan_callback(self, cb):
        self._scan_callback = cb

    def set_quit_callback(self, cb):
        self._quit_callback = cb

    def set_usage_api_test_callback(self, cb):
        self._usage_api_test_callback = cb

    def _request_scan(self):
        if self._scan_callback:
            self._scan_callback()

    def _quit_app(self):
        if self._quit_callback:
            self._quit_callback()
        else:
            self.destroy()

    def _refresh_all(self):
        for fn in (self._refresh_dashboard, self._refresh_analysis, self._refresh_activity, self._update_rec_count):
            try:
                fn()
            except Exception as e:
                logger.error("Refresh error: %s", e)

    def refresh_from_scan(self):
        self._refresh_all()
        self.set_status(i18n.t("last_scan", time=datetime.now().strftime('%H:%M:%S')))

    def update_scan_progress(self, done: int, total: int):
        self.set_status(i18n.t("scan_progress", done=done, total=total) if total > 0 else "")
