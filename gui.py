"""Usage Tracker - tkinter GUIメインウィンドウ"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import os
import csv
from datetime import datetime
from pathlib import Path
from typing import Optional
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import config
import database
import charts
from period_selector import PeriodSelector

logger = logging.getLogger(__name__)

_ACTIVITY_HEADINGS = {
    "time": "時刻",
    "project": "プロジェクト",
    "model": "モデル",
    "cost": "コスト",
    "detail": "詳細",
}

_INTERVAL_OPTIONS = [("10秒", 10), ("30秒", 30), ("1分", 60), ("2分", 120), ("5分", 300)]
_INTERVAL_MAP = {label: val for label, val in _INTERVAL_OPTIONS}
_INTERVAL_DISPLAY = {val: label for label, val in _INTERVAL_OPTIONS}

_API_INTERVAL_OPTIONS = [("1分", 60), ("2分", 120), ("3分", 180), ("5分", 300)]
_API_INTERVAL_MAP = {label: val for label, val in _API_INTERVAL_OPTIONS}
_API_INTERVAL_DISPLAY = {val: label for label, val in _API_INTERVAL_OPTIONS}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Claude Usage Tracker v{config.VERSION}")
        self.geometry(f"{config.MIN_WIDTH}x{config.MIN_HEIGHT}")
        self.minsize(config.MIN_WIDTH, config.MIN_HEIGHT)
        self.configure(bg=config.BG_COLOR)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._scan_callback = None
        self._quit_callback = None
        self._usage_api_test_callback = None

        self._activity_sort_col = None
        self._activity_sort_reverse = False

        self._dash_since = None
        self._dash_until = None
        self._analysis_since = None
        self._analysis_until = None
        self._activity_since = None
        self._activity_until = None

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
        file_menu.add_command(label="今すぐスキャン", command=self._request_scan)
        file_menu.add_separator()
        file_menu.add_command(label="終了", command=self._quit_app)
        menubar.add_cascade(label="ファイル", menu=file_menu)
        self.config(menu=menubar)

    def _build_notebook(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.tab_dashboard = ttk.Frame(self.notebook)
        self.tab_analysis = ttk.Frame(self.notebook)
        self.tab_activity = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_dashboard, text="  ダッシュボード  ")
        self.notebook.add(self.tab_analysis, text="  分析  ")
        self.notebook.add(self.tab_activity, text="  アクティビティ  ")
        self.notebook.add(self.tab_settings, text="  設定  ")

        self._build_dashboard_tab()
        self._build_analysis_tab()
        self._build_activity_tab()
        self._build_settings_tab()

    def _build_status_bar(self):
        self.status_var = tk.StringVar(value="準備完了")
        bar = tk.Label(self, textvariable=self.status_var, bd=1, relief=tk.SUNKEN,
                       anchor=tk.W, font=config.FONT, bg=config.BG_COLOR, padx=5)
        bar.pack(side=tk.BOTTOM, fill=tk.X)

    def set_status(self, msg: str):
        self.status_var.set(msg)
        try:
            self.update_idletasks()
        except Exception:
            pass

    # ════════════════════════════════════════════
    # ダッシュボードタブ
    # ════════════════════════════════════════════
    def _build_dashboard_tab(self):
        parent = self.tab_dashboard
        self._dash_period = PeriodSelector(parent, on_change=self._on_dash_period_change, default="today")
        self._dash_period.pack(fill=tk.X, padx=10, pady=(5, 0))

        summary_frame = tk.Frame(parent, bg=config.BG_COLOR, pady=3)
        summary_frame.pack(fill=tk.X, padx=10)
        self.lbl_period_label = tk.Label(summary_frame, text="期間: 今日", font=config.FONT, bg=config.BG_COLOR, fg="#555555")
        self.lbl_period_label.pack(side=tk.LEFT, padx=(0, 10))
        self.lbl_today_input = tk.Label(summary_frame, text="入力: -", font=config.FONT_BOLD, bg=config.BG_COLOR, fg="#333333")
        self.lbl_today_input.pack(side=tk.LEFT, padx=10)
        self.lbl_today_output = tk.Label(summary_frame, text="出力: -", font=config.FONT_BOLD, bg=config.BG_COLOR, fg="#333333")
        self.lbl_today_output.pack(side=tk.LEFT, padx=10)
        self.lbl_today_cost = tk.Label(summary_frame, text="コスト: -", font=config.FONT_LARGE, bg=config.BG_COLOR, fg=config.ACCENT_COLOR)
        self.lbl_today_cost.pack(side=tk.LEFT, padx=15)
        self.lbl_today_count = tk.Label(summary_frame, text="メッセージ: -", font=config.FONT, bg=config.BG_COLOR, fg="#555555")
        self.lbl_today_count.pack(side=tk.LEFT, padx=10)

        graph_frame = tk.Frame(parent, bg=config.BG_COLOR)
        graph_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)
        self.hourly_canvas_frame = tk.Frame(graph_frame, bg=config.BG_COLOR)
        self.hourly_canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.pie_canvas_frame = tk.Frame(graph_frame, bg=config.BG_COLOR, width=260)
        self.pie_canvas_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(3, 5))
        self.pie_canvas_frame.pack_propagate(False)

        list_frame = tk.LabelFrame(parent, text="  直近のメッセージ  ", font=config.FONT, bg=config.BG_COLOR, padx=5, pady=3)
        list_frame.pack(fill=tk.X, padx=10, pady=(3, 5))
        cols = ("timestamp", "project", "model", "input", "output", "cost")
        self.recent_tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=10)
        for c, w, label, anchor in [("timestamp", 140, "時刻", "center"), ("project", 160, "プロジェクト", "w"),
                                     ("model", 100, "モデル", "center"), ("input", 80, "入力tokens", "e"),
                                     ("output", 80, "出力tokens", "e"), ("cost", 80, "コスト", "e")]:
            self.recent_tree.heading(c, text=label)
            self.recent_tree.column(c, width=w, anchor=anchor)
        vsb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.recent_tree.yview)
        self.recent_tree.configure(yscrollcommand=vsb.set)
        self.recent_tree.pack(side=tk.LEFT, fill=tk.X, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

    def _on_dash_period_change(self, since, until):
        self._dash_since = since
        self._dash_until = until
        self._refresh_dashboard()

    def _refresh_dashboard(self):
        since, until = self._dash_since, self._dash_until
        s = database.query_summary(since, until)
        inp = s.get("input_tokens", 0) + s.get("cache_creation_tokens", 0) + s.get("cache_read_tokens", 0)
        out = s.get("output_tokens", 0)
        cnt = s.get("message_count", 0)
        rows = database.query_rows_for_cost(since, until)
        cost_total = sum(config.calc_cost(r.get("model", "default"), r.get("input_tokens", 0), r.get("output_tokens", 0), r.get("cache_creation_tokens", 0), r.get("cache_read_tokens", 0)) for r in rows)
        period_label = self._dash_period.get_period_label()
        self.lbl_period_label.config(text=f"期間: {period_label}")
        self.lbl_today_input.config(text=f"入力: {inp:,}")
        self.lbl_today_output.config(text=f"出力: {out:,}")
        self.lbl_today_cost.config(text=f"コスト: ${cost_total:.3f}")
        self.lbl_today_count.config(text=f"メッセージ: {cnt}")
        for w in self.hourly_canvas_frame.winfo_children():
            w.destroy()
        try:
            hourly = database.query_hourly_tokens(since, until)
            fig = charts.make_hourly_bar_chart(hourly, title=f"トークン消費（{period_label}）")
            FigureCanvasTkAgg(fig, master=self.hourly_canvas_frame).get_tk_widget().pack(fill=tk.BOTH, expand=True)
        except Exception as e:
            logger.error("時系列グラフエラー: %s", e)
        for w in self.pie_canvas_frame.winfo_children():
            w.destroy()
        try:
            model_data = database.query_model_stats(since, until)
            fig2 = charts.make_model_pie_chart(model_data, title=f"モデル別（{period_label}）")
            FigureCanvasTkAgg(fig2, master=self.pie_canvas_frame).get_tk_widget().pack(fill=tk.BOTH, expand=True)
        except Exception as e:
            logger.error("円グラフエラー: %s", e)
        self.recent_tree.delete(*self.recent_tree.get_children())
        for r in database.query_recent_messages(50, since, until):
            ts = database.utc_to_jst_str(r.get("timestamp", ""))
            total_input = r.get("input_tokens", 0) + r.get("cache_creation_tokens", 0) + r.get("cache_read_tokens", 0)
            cost = config.calc_cost(r.get("model", "default"), r.get("input_tokens", 0), r.get("output_tokens", 0), r.get("cache_creation_tokens", 0), r.get("cache_read_tokens", 0))
            self.recent_tree.insert("", tk.END, values=(ts, r.get("project_name") or "", config.get_model_display(r.get("model") or ""), f'{total_input:,}', f'{r.get("output_tokens", 0):,}', f"${cost:.3f}"))

    # ════════════════════════════════════════════
    # 分析タブ
    # ════════════════════════════════════════════
    def _build_analysis_tab(self):
        parent = self.tab_analysis
        ctrl_frame = tk.Frame(parent, bg=config.BG_COLOR)
        ctrl_frame.pack(fill=tk.X, padx=10, pady=(5, 0))
        tk.Label(ctrl_frame, text="分析軸:", font=config.FONT_BOLD, bg=config.BG_COLOR).pack(side=tk.LEFT, padx=(0, 5))
        self._analysis_axis = tk.StringVar(value="プロジェクト別")
        self._analysis_combo = ttk.Combobox(ctrl_frame, textvariable=self._analysis_axis, values=["プロジェクト別", "アクション別"], state="readonly", width=15, font=config.FONT)
        self._analysis_combo.pack(side=tk.LEFT, padx=5)
        self._analysis_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_analysis())
        self._analysis_period = PeriodSelector(parent, on_change=self._on_analysis_period_change, default="all")
        self._analysis_period.pack(fill=tk.X, padx=10, pady=(2, 0))
        self._analysis_canvas_frame = tk.Frame(parent, bg=config.BG_COLOR)
        self._analysis_canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _on_analysis_period_change(self, since, until):
        self._analysis_since = since
        self._analysis_until = until
        self._refresh_analysis()

    def _refresh_analysis(self):
        axis = self._analysis_axis.get()
        since, until = self._analysis_since, self._analysis_until
        for w in self._analysis_canvas_frame.winfo_children():
            w.destroy()
        try:
            if axis == "アクション別":
                data = database.query_tool_stats(since, until)
                fig = charts.make_tool_bar_chart(data)
            else:
                data = database.query_project_stats(since, until)
                fig = charts.make_project_bar_chart(data)
            FigureCanvasTkAgg(fig, master=self._analysis_canvas_frame).get_tk_widget().pack(fill=tk.BOTH, expand=True)
        except Exception as e:
            logger.error("分析グラフエラー: %s", e)

    # ════════════════════════════════════════════
    # アクティビティログタブ
    # ════════════════════════════════════════════
    def _build_activity_tab(self):
        parent = self.tab_activity
        self._activity_period = PeriodSelector(parent, on_change=self._on_activity_period_change, default="today")
        self._activity_period.pack(fill=tk.X, padx=10, pady=(5, 0))
        ctrl_frame = tk.Frame(parent, bg=config.BG_COLOR)
        ctrl_frame.pack(fill=tk.X, padx=10, pady=2)
        tk.Button(ctrl_frame, text="  更新  ", command=self._refresh_activity, font=config.FONT, bg=config.ACCENT_COLOR, fg="white", relief=tk.FLAT).pack(side=tk.RIGHT, padx=5)
        tree_frame = tk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))
        cols = ("time", "project", "model", "cost", "detail")
        self.activity_tree = ttk.Treeview(tree_frame, columns=cols, show="tree headings")
        self.activity_tree.column("#0", width=30, minwidth=30, stretch=False)
        for c, w, label, anchor in [("time", 130, "時刻", "center"), ("project", 160, "プロジェクト", "w"), ("model", 100, "モデル", "center"), ("cost", 80, "コスト", "e"), ("detail", 250, "詳細", "w")]:
            self.activity_tree.heading(c, text=label, command=lambda col=c: self._sort_activity(col))
            self.activity_tree.column(c, width=w, anchor=anchor)
        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.activity_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.activity_tree.xview)
        self.activity_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.activity_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _on_activity_period_change(self, since, until):
        self._activity_since = since
        self._activity_until = until
        self._refresh_activity()

    def _sort_activity(self, col):
        if self._activity_sort_col == col:
            self._activity_sort_reverse = not self._activity_sort_reverse
        else:
            self._activity_sort_col = col
            self._activity_sort_reverse = False
        col_idx = {"time": 0, "project": 1, "model": 2, "cost": 3, "detail": 4}[col]
        items = [(iid, self.activity_tree.item(iid, 'values')) for iid in self.activity_tree.get_children('')]
        key_fn = (lambda item: float(item[1][col_idx].replace('$', '').replace(',', '')) if item[1][col_idx] else 0.0) if col == "cost" else (lambda item: item[1][col_idx] if col_idx < len(item[1]) else "")
        items.sort(key=key_fn, reverse=self._activity_sort_reverse)
        for idx, (iid, _) in enumerate(items):
            self.activity_tree.move(iid, '', idx)
        for c in ("time", "project", "model", "cost", "detail"):
            text = _ACTIVITY_HEADINGS[c]
            if c == col:
                text += " \u25bc" if self._activity_sort_reverse else " \u25b2"
            self.activity_tree.heading(c, text=text, command=lambda cc=c: self._sort_activity(cc))

    def _refresh_activity(self):
        since, until = self._activity_since, self._activity_until
        self.activity_tree.delete(*self.activity_tree.get_children())
        self._activity_sort_col = None
        self._activity_sort_reverse = False
        for c in ("time", "project", "model", "cost", "detail"):
            self.activity_tree.heading(c, text=_ACTIVITY_HEADINGS[c], command=lambda cc=c: self._sort_activity(cc))
        try:
            sessions = database.query_activity_log(since, until)
        except Exception as e:
            logger.error("アクティビティクエリエラー: %s", e)
            return
        for s in sessions:
            ts = database.utc_to_jst_str(s.get("first_ts", ""))
            cost_str = f'${s.get("total_cost", 0):.3f}'
            model_str = config.get_model_display(s.get("model") or "")
            proj = s.get("project_name") or ""
            messages = s.get("messages", [])
            all_tools = [t.get("tool_target", "")[:20] for msg in messages for t in msg.get("tools", [])]
            tool_summary = "\u3001".join(all_tools[:3])
            if len(all_tools) > 3:
                tool_summary += f" 他{len(all_tools) - 3}件"
            parent_id = self.activity_tree.insert("", tk.END, text="\u25b6", values=(ts, proj, model_str, cost_str, tool_summary), open=False)
            if messages:
                for i, msg in enumerate(messages):
                    msg_ts = database.utc_to_jst_str(msg.get("timestamp", ""))
                    total_in = msg.get("input_tokens", 0) + msg.get("cache_creation_tokens", 0) + msg.get("cache_read_tokens", 0)
                    total_out = msg.get("output_tokens", 0)
                    msg_cost = msg.get("cost", 0)
                    tools = msg.get("tools", [])
                    tool_desc = (tools[0].get("tool_target", "") + (f" 他{len(tools)-1}件" if len(tools) > 1 else "")) if tools else "テキスト応答のみ"
                    prefix = "  \u2514" if i == len(messages) - 1 else "  \u251c"
                    self.activity_tree.insert(parent_id, tk.END, text=prefix, values=(msg_ts, f"\u5165\u529b {total_in:,} / \u51fa\u529b {total_out:,}", "", f"${msg_cost:.3f}", tool_desc))

    # ════════════════════════════════════════════
    # 設定タブ（v3.0.0: OAuth認証）
    # ════════════════════════════════════════════
    def _build_settings_tab(self):
        parent = self.tab_settings
        canvas = tk.Canvas(parent, bg=config.BG_COLOR, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=config.BG_COLOR)
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        # ── 基本情報 ──
        info_frame = tk.LabelFrame(scroll_frame, text="  基本情報  ", font=config.FONT_BOLD, bg=config.BG_COLOR, padx=10, pady=10)
        info_frame.pack(fill=tk.X, padx=15, pady=10)
        def add_info(label, value):
            f = tk.Frame(info_frame, bg=config.BG_COLOR)
            f.pack(fill=tk.X, pady=2)
            tk.Label(f, text=label, font=config.FONT_BOLD, bg=config.BG_COLOR, width=22, anchor="w").pack(side=tk.LEFT)
            tk.Label(f, text=value, font=config.FONT, bg=config.BG_COLOR, anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)
        add_info("スキャン対象パス:", str(config.PROJECTS_DIR))
        add_info("データベース:", str(config.DB_PATH))
        add_info("ログフォルダ:", str(config.LOG_DIR))

        interval_row = tk.Frame(info_frame, bg=config.BG_COLOR)
        interval_row.pack(fill=tk.X, pady=2)
        tk.Label(interval_row, text="自動スキャン間隔:", font=config.FONT_BOLD, bg=config.BG_COLOR, width=22, anchor="w").pack(side=tk.LEFT)
        self._interval_var = tk.StringVar(value=_INTERVAL_DISPLAY.get(config.SCAN_INTERVAL_SECONDS, f"{config.SCAN_INTERVAL_SECONDS}秒"))
        ttk.Combobox(interval_row, textvariable=self._interval_var, values=[l for l, _ in _INTERVAL_OPTIONS], state="readonly", width=8, font=config.FONT).pack(side=tk.LEFT, padx=5)
        self._interval_var.trace_add("write", lambda *_: self._on_interval_change())

        self.lbl_rec_count = tk.Label(info_frame, text="", font=config.FONT_BOLD, bg=config.BG_COLOR, fg=config.ACCENT_COLOR)
        self.lbl_rec_count.pack(anchor="w", pady=(5, 0))

        # ── OAuth認証（v3.0.0） ──
        auth_frame = tk.LabelFrame(scroll_frame, text="  OAuth 認証  ", font=config.FONT_BOLD, bg=config.BG_COLOR, padx=10, pady=10)
        auth_frame.pack(fill=tk.X, padx=15, pady=(0, 10))

        # 認証情報を表示
        from usage_api import UsageAPIClient
        auth_info = UsageAPIClient().get_auth_info()

        if auth_info["status"] == "ok":
            auth_color = "#27ae60"
            auth_text = "OAuth認証: 有効"
            detail_lines = [
                f"トークン: {auth_info['token_masked']}",
                f"サブスクリプション: {auth_info['subscription_type']}",
                f"認証ファイル: {auth_info['credentials_path']}",
            ]
        else:
            auth_color = "#e74c3c"
            auth_text = "OAuth認証: エラー"
            detail_lines = [auth_info.get("error", "不明なエラー")]

        tk.Label(auth_frame, text=auth_text, font=config.FONT_BOLD, bg=config.BG_COLOR, fg=auth_color, anchor="w").pack(fill=tk.X)
        for line in detail_lines:
            tk.Label(auth_frame, text=line, font=config.FONT, bg=config.BG_COLOR, fg="#555555", anchor="w").pack(fill=tk.X, pady=1)

        # Usage API 設定
        api_frame = tk.LabelFrame(scroll_frame, text="  Usage API  ", font=config.FONT_BOLD, bg=config.BG_COLOR, padx=10, pady=10)
        api_frame.pack(fill=tk.X, padx=15, pady=(0, 10))

        api_interval_row = tk.Frame(api_frame, bg=config.BG_COLOR)
        api_interval_row.pack(fill=tk.X, pady=2)
        tk.Label(api_interval_row, text="API ポーリング間隔:", font=config.FONT_BOLD, bg=config.BG_COLOR, width=22, anchor="w").pack(side=tk.LEFT)
        self._api_interval_var = tk.StringVar(value=_API_INTERVAL_DISPLAY.get(config.USAGE_API_INTERVAL_SECONDS, f"{config.USAGE_API_INTERVAL_SECONDS}秒"))
        ttk.Combobox(api_interval_row, textvariable=self._api_interval_var, values=[l for l, _ in _API_INTERVAL_OPTIONS], state="readonly", width=8, font=config.FONT).pack(side=tk.LEFT, padx=5)
        self._api_interval_var.trace_add("write", lambda *_: self._on_api_interval_change())

        # Organization ID（フォールバック）
        orgid_row = tk.Frame(api_frame, bg=config.BG_COLOR)
        orgid_row.pack(fill=tk.X, pady=2)
        tk.Label(orgid_row, text="Organization ID:", font=config.FONT_BOLD, bg=config.BG_COLOR, width=22, anchor="w").pack(side=tk.LEFT)
        self._orgid_entry = tk.Entry(orgid_row, width=40, font=config.FONT)
        self._orgid_entry.insert(0, config.ORG_ID)
        self._orgid_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(orgid_row, text="保存", font=config.FONT, command=self._save_orgid).pack(side=tk.LEFT, padx=2)
        tk.Label(orgid_row, text="（通常は自動取得。取得できない場合のみ手動入力）", font=config.FONT_SMALL, bg=config.BG_COLOR, fg="#999999").pack(side=tk.LEFT, padx=5)

        # テストボタン
        test_row = tk.Frame(api_frame, bg=config.BG_COLOR)
        test_row.pack(fill=tk.X, pady=(5, 2))
        tk.Button(test_row, text="  Usage API テスト  ", font=config.FONT, bg=config.ACCENT_COLOR, fg="white", relief=tk.FLAT, command=self._test_usage_api).pack(side=tk.LEFT)

        # ステータス表示
        self.lbl_api_status = tk.Label(api_frame, text="Usage API: 未テスト", font=config.FONT, bg=config.BG_COLOR, fg="#888888", anchor="w")
        self.lbl_api_status.pack(fill=tk.X, pady=(5, 0))
        self.lbl_api_data = tk.Label(api_frame, text="", font=config.FONT, bg=config.BG_COLOR, fg="#333333", anchor="w", justify=tk.LEFT)
        self.lbl_api_data.pack(fill=tk.X, pady=(2, 0))

        # ── ボタン群 ──
        btn_frame = tk.Frame(scroll_frame, bg=config.BG_COLOR)
        btn_frame.pack(fill=tk.X, padx=15, pady=10)
        for text, cmd in [("  今すぐスキャン  ", self._request_scan), ("  ログフォルダを開く  ", self._open_log_folder), ("  CSVエクスポート  ", self._export_csv)]:
            tk.Button(btn_frame, text=text, command=cmd, font=config.FONT, height=2, bg=config.ACCENT_COLOR, fg="white", relief=tk.FLAT).pack(side=tk.LEFT, padx=5)

        self._update_rec_count()

    def _on_interval_change(self):
        display = self._interval_var.get()
        seconds = _INTERVAL_MAP.get(display)
        if seconds:
            config.SCAN_INTERVAL_SECONDS = seconds
            config.save_settings()

    def _on_api_interval_change(self):
        display = self._api_interval_var.get()
        seconds = _API_INTERVAL_MAP.get(display)
        if seconds:
            config.USAGE_API_INTERVAL_SECONDS = seconds
            config.save_settings()

    def _save_orgid(self):
        config.ORG_ID = self._orgid_entry.get().strip()
        config.save_settings()
        self.set_status("Organization ID を保存しました")

    def _test_usage_api(self):
        self.lbl_api_status.config(text="Usage API: テスト中...", fg="#f39c12")
        if self._usage_api_test_callback:
            self._usage_api_test_callback()

    def update_usage_status(self, data: Optional[dict], error: Optional[str]):
        if error:
            self.lbl_api_status.config(text="Usage API: エラー", fg="#e74c3c")
            self.lbl_api_data.config(text=error, fg="#e74c3c")
            return
        if data:
            now_jst = database.utc_to_jst_str(datetime.utcnow().isoformat())
            self.lbl_api_status.config(text=f"Usage API: 接続成功 (最終取得: {now_jst})", fg="#27ae60")
            lines = []
            fh = data.get("five_hour_util")
            sd = data.get("seven_day_util")
            sn = data.get("seven_day_sonnet_util")
            ee = data.get("extra_usage_is_enabled", False)
            eu = data.get("extra_usage_util")
            if fh is not None:
                lines.append(f"セッション (5h): 残り {max(0, 100 - fh):.1f}%")
            if sd is not None:
                lines.append(f"週間 (全モデル): 残り {max(0, 100 - sd):.1f}%")
            if sn is not None:
                lines.append(f"週間 (Sonnet): 残り {max(0, 100 - sn):.1f}%")
            if ee:
                lines.append(f"追加使用量: {'無制限' if eu is None else f'残り {max(0, 100 - eu):.1f}%'}")
            self.lbl_api_data.config(text="\n".join(lines) if lines else "(データなし)", fg="#333333")

    def _update_rec_count(self):
        self.lbl_rec_count.config(text=f"DBレコード総数: {database.get_total_record_count():,} 件")

    def _open_log_folder(self):
        try:
            config.LOG_DIR.mkdir(parents=True, exist_ok=True)
            os.startfile(str(config.LOG_DIR))
        except Exception as e:
            messagebox.showerror("エラー", str(e))

    def _export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialfile="claude_usage_export.csv")
        if not path:
            return
        try:
            with database.get_conn() as conn:
                rows = conn.execute("SELECT * FROM token_log ORDER BY timestamp DESC").fetchall()
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                if rows:
                    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows([dict(r) for r in rows])
            messagebox.showinfo("エクスポート完了", f"保存しました:\n{path}")
        except Exception as e:
            messagebox.showerror("エラー", str(e))

    # ── コールバック設定 ──
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

    # ── 更新メソッド ──
    def _refresh_all(self):
        for fn in (self._refresh_dashboard, self._refresh_analysis, self._refresh_activity, self._update_rec_count):
            try:
                fn()
            except Exception as e:
                logger.error("更新エラー: %s", e)

    def refresh_from_scan(self):
        self._refresh_all()
        self.set_status(f"最終スキャン: {datetime.now().strftime('%H:%M:%S')}")

    def update_scan_progress(self, done: int, total: int):
        self.set_status(f"スキャン中... {done}/{total} ファイル" if total > 0 else "スキャン完了")
