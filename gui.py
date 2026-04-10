"""Usage Tracker - tkinter GUIメインウィンドウ（i18n対応）"""
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
import i18n
from period_selector import PeriodSelector

logger = logging.getLogger(__name__)

_ACTIVITY_COLS = ("time", "project", "model", "cost", "detail")

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
        self.tab_dashboard = ttk.Frame(self.notebook)
        self.tab_analysis = ttk.Frame(self.notebook)
        self.tab_activity = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_dashboard, text=i18n.t("tab_dashboard"))
        self.notebook.add(self.tab_analysis, text=i18n.t("tab_analysis"))
        self.notebook.add(self.tab_activity, text=i18n.t("tab_activity"))
        self.notebook.add(self.tab_settings, text=i18n.t("tab_settings"))
        self._build_dashboard_tab()
        self._build_analysis_tab()
        self._build_activity_tab()
        self._build_settings_tab()

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

    def _on_lang_change(self, event=None):
        for name, code in _LANG_OPTIONS:
            if name == self._lang_var.get():
                config.LANGUAGE = code
                config.save_settings()
                messagebox.showinfo("Language", i18n.t("restart_required"))
                break

    def _save_orgid(self):
        config.ORG_ID = self._orgid_entry.get().strip()
        config.save_settings()

    def _test_usage_api(self):
        self.lbl_api_status.config(text=i18n.t("api_status_testing"), fg="#f39c12")
        if self._usage_api_test_callback:
            self._usage_api_test_callback()

    def update_usage_status(self, data: Optional[dict], error: Optional[str]):
        if error:
            self.lbl_api_status.config(text=i18n.t("api_status_error"), fg="#e74c3c")
            self.lbl_api_data.config(text=error, fg="#e74c3c")
            return
        if data:
            now_jst = database.utc_to_jst_str(datetime.utcnow().isoformat())
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
