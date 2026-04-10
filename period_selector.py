"""Usage Tracker - 期間選択共通コンポーネント（F-8）"""
import tkinter as tk
from tkinter import ttk
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional, Tuple
from tkcalendar import DateEntry
import config

logger = logging.getLogger(__name__)


class PeriodSelector(tk.Frame):
    """
    期間選択UIコンポーネント。
    プリセットボタン（今日/1週間/1ヶ月/全期間/カスタム）＋
    カレンダー入力（DateEntry＋時間スピンボックス）を提供する。

    コールバックに (since_utc, until_utc) を渡す。
    since_utc/until_utc: 'YYYY-MM-DDTHH:MM:SS' 形式のUTC文字列。Noneは制限なし。
    """

    PRESETS = [
        ("今日", "today"),
        ("1週間", "week"),
        ("1ヶ月", "month"),
        ("全期間", "all"),
        ("カスタム", "custom"),
    ]

    def __init__(self, parent, on_change: Callable[[Optional[str], Optional[str]], None],
                 default: str = "today"):
        super().__init__(parent, bg=config.BG_COLOR)
        self._on_change = on_change
        self._current_preset = tk.StringVar(value=default)

        self._build_preset_row()
        self._build_custom_row()

        # カスタム行は初期非表示
        if default != "custom":
            self._custom_frame.pack_forget()

        # 初回コールバック発火
        self.after(50, lambda: self._on_preset_click(default))

    def _build_preset_row(self):
        row = tk.Frame(self, bg=config.BG_COLOR)
        row.pack(fill=tk.X, pady=(0, 2))

        tk.Label(row, text="期間:", font=config.FONT_BOLD,
                 bg=config.BG_COLOR).pack(side=tk.LEFT, padx=(0, 5))

        self._preset_buttons = {}
        for label, key in self.PRESETS:
            btn = tk.Button(
                row, text=label, font=config.FONT,
                relief=tk.FLAT, padx=8, pady=2,
                command=lambda k=key: self._on_preset_click(k)
            )
            btn.pack(side=tk.LEFT, padx=2)
            self._preset_buttons[key] = btn

        self._update_button_styles()

    def _build_custom_row(self):
        self._custom_frame = tk.Frame(self, bg=config.BG_COLOR)
        self._custom_frame.pack(fill=tk.X, pady=(0, 2))

        tk.Label(self._custom_frame, text="カスタム:", font=config.FONT,
                 bg=config.BG_COLOR).pack(side=tk.LEFT, padx=(0, 5))

        # 開始日
        self._start_date = DateEntry(
            self._custom_frame, width=10, font=config.FONT,
            date_pattern='yyyy/mm/dd', locale='ja_JP'
        )
        self._start_date.pack(side=tk.LEFT, padx=2)

        # 開始時間トグル
        self._start_time_on = tk.BooleanVar(value=False)
        self._start_time_chk = tk.Checkbutton(
            self._custom_frame, variable=self._start_time_on,
            bg=config.BG_COLOR, command=self._toggle_start_time
        )
        self._start_time_chk.pack(side=tk.LEFT)

        self._start_hour = ttk.Spinbox(
            self._custom_frame, from_=0, to=23, width=2,
            font=config.FONT, format="%02.0f", state="disabled"
        )
        self._start_hour.set("00")
        self._start_hour.pack(side=tk.LEFT)
        tk.Label(self._custom_frame, text=":", font=config.FONT,
                 bg=config.BG_COLOR).pack(side=tk.LEFT)
        self._start_min = ttk.Spinbox(
            self._custom_frame, from_=0, to=59, width=2,
            font=config.FONT, format="%02.0f", state="disabled"
        )
        self._start_min.set("00")
        self._start_min.pack(side=tk.LEFT)

        tk.Label(self._custom_frame, text="  \u301c  ", font=config.FONT,
                 bg=config.BG_COLOR).pack(side=tk.LEFT)

        # 終了日
        self._end_date = DateEntry(
            self._custom_frame, width=10, font=config.FONT,
            date_pattern='yyyy/mm/dd', locale='ja_JP'
        )
        self._end_date.pack(side=tk.LEFT, padx=2)

        # 終了時間トグル
        self._end_time_on = tk.BooleanVar(value=False)
        self._end_time_chk = tk.Checkbutton(
            self._custom_frame, variable=self._end_time_on,
            bg=config.BG_COLOR, command=self._toggle_end_time
        )
        self._end_time_chk.pack(side=tk.LEFT)

        self._end_hour = ttk.Spinbox(
            self._custom_frame, from_=0, to=23, width=2,
            font=config.FONT, format="%02.0f", state="disabled"
        )
        self._end_hour.set("23")
        self._end_hour.pack(side=tk.LEFT)
        tk.Label(self._custom_frame, text=":", font=config.FONT,
                 bg=config.BG_COLOR).pack(side=tk.LEFT)
        self._end_min = ttk.Spinbox(
            self._custom_frame, from_=0, to=59, width=2,
            font=config.FONT, format="%02.0f", state="disabled"
        )
        self._end_min.set("59")
        self._end_min.pack(side=tk.LEFT)

        # 適用ボタン
        self._apply_btn = tk.Button(
            self._custom_frame, text="  適用  ", font=config.FONT,
            bg=config.ACCENT_COLOR, fg="white", relief=tk.FLAT,
            command=self._apply_custom
        )
        self._apply_btn.pack(side=tk.LEFT, padx=(10, 0))

    def _toggle_start_time(self):
        state = "normal" if self._start_time_on.get() else "disabled"
        self._start_hour.config(state=state)
        self._start_min.config(state=state)
        if not self._start_time_on.get():
            self._start_hour.set("00")
            self._start_min.set("00")

    def _toggle_end_time(self):
        state = "normal" if self._end_time_on.get() else "disabled"
        self._end_hour.config(state=state)
        self._end_min.config(state=state)
        if not self._end_time_on.get():
            self._end_hour.set("23")
            self._end_min.set("59")

    def _update_button_styles(self):
        current = self._current_preset.get()
        for key, btn in self._preset_buttons.items():
            if key == current:
                btn.config(bg=config.ACCENT_COLOR, fg="white")
            else:
                btn.config(bg="#dddddd", fg="#333333")

    def _on_preset_click(self, preset: str):
        self._current_preset.set(preset)
        self._update_button_styles()

        if preset == "custom":
            self._custom_frame.pack(fill=tk.X, pady=(0, 2))
            return
        else:
            self._custom_frame.pack_forget()

        since, until = self._compute_preset_utc(preset)
        self._on_change(since, until)

    def _apply_custom(self):
        """カスタム期間の「適用」ボタン押下時。"""
        try:
            start_d = self._start_date.get_date()
            end_d = self._end_date.get_date()
            sh = int(self._start_hour.get())
            sm = int(self._start_min.get())
            eh = int(self._end_hour.get())
            em = int(self._end_min.get())

            start_jst = datetime(start_d.year, start_d.month, start_d.day, sh, sm, 0)
            end_jst = datetime(end_d.year, end_d.month, end_d.day, eh, em, 59)

            # JST→UTC変換
            start_utc = start_jst - timedelta(hours=9)
            end_utc = end_jst - timedelta(hours=9)

            since = start_utc.strftime('%Y-%m-%dT%H:%M:%S')
            until = end_utc.strftime('%Y-%m-%dT%H:%M:%S')
            self._on_change(since, until)
        except Exception as e:
            logger.error("カスタム期間適用エラー: %s", e)

    @staticmethod
    def _compute_preset_utc(preset: str) -> Tuple[Optional[str], Optional[str]]:
        """プリセット名から (since_utc, until_utc) を返す。"""
        now_utc = datetime.utcnow()
        now_jst = now_utc + timedelta(hours=9)
        until = None  # None = 現在まで

        if preset == "today":
            midnight_jst = now_jst.replace(hour=0, minute=0, second=0, microsecond=0)
            since = (midnight_jst - timedelta(hours=9)).strftime('%Y-%m-%dT%H:%M:%S')
        elif preset == "week":
            since = (now_utc - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%S')
        elif preset == "month":
            since = (now_utc - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%S')
        elif preset == "all":
            since = None
        else:
            since = None

        return since, until

    def get_period_utc(self) -> Tuple[Optional[str], Optional[str]]:
        """現在選択中の期間を (since_utc, until_utc) で返す。"""
        preset = self._current_preset.get()
        if preset == "custom":
            try:
                start_d = self._start_date.get_date()
                end_d = self._end_date.get_date()
                sh = int(self._start_hour.get())
                sm = int(self._start_min.get())
                eh = int(self._end_hour.get())
                em = int(self._end_min.get())
                start_jst = datetime(start_d.year, start_d.month, start_d.day, sh, sm, 0)
                end_jst = datetime(end_d.year, end_d.month, end_d.day, eh, em, 59)
                start_utc = start_jst - timedelta(hours=9)
                end_utc = end_jst - timedelta(hours=9)
                return (start_utc.strftime('%Y-%m-%dT%H:%M:%S'),
                        end_utc.strftime('%Y-%m-%dT%H:%M:%S'))
            except Exception:
                return None, None
        return self._compute_preset_utc(preset)

    def get_period_label(self) -> str:
        """現在の期間を表示用ラベル文字列で返す。"""
        preset = self._current_preset.get()
        labels = {"today": "今日", "week": "直近1週間", "month": "直近1ヶ月", "all": "全期間"}
        if preset in labels:
            return labels[preset]
        # カスタム
        try:
            start_d = self._start_date.get_date()
            end_d = self._end_date.get_date()
            sh = int(self._start_hour.get())
            sm = int(self._start_min.get())
            eh = int(self._end_hour.get())
            em = int(self._end_min.get())
            return f"{start_d.strftime('%m/%d')} {sh:02d}:{sm:02d} \u301c {end_d.strftime('%m/%d')} {eh:02d}:{em:02d}"
        except Exception:
            return "カスタム"
