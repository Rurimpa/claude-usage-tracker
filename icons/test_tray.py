"""トレイアイコン動作確認ツール

スライダーまたは数値入力で残量%を変更し、ゲージ表示をリアルタイム確認する。
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tkinter as tk
from PIL import ImageTk
from icons.gauge import make_gauge_icon, _get_lit_count, _get_color


class TrayIconTester(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("トレイアイコン動作確認")
        self.geometry("520x700")
        self.configure(bg="#2d2d2d")

        self._mode = tk.StringVar(value="session")
        self._dim = tk.BooleanVar(value=False)
        self._blink_active = False
        self._blink_state = False  # True=暗転中
        self._blink_job = None

        # ── プレビュー（拡大） ──
        self._preview_label = tk.Label(self, bg="#2d2d2d")
        self._preview_label.pack(pady=(20, 5))

        # ── 情報ラベル ──
        self._info_label = tk.Label(
            self, text="", font=("Meiryo", 13, "bold"), bg="#2d2d2d", fg="white"
        )
        self._info_label.pack(pady=5)

        # ── 16x16プレビュー ──
        small_frame = tk.Frame(self, bg="#2d2d2d")
        small_frame.pack(pady=5)
        tk.Label(small_frame, text="実際のトレイサイズ(16x16):",
                 font=("Meiryo", 9), bg="#2d2d2d", fg="#aaaaaa").pack(side=tk.LEFT)
        self._small_label = tk.Label(small_frame, bg="#2d2d2d")
        self._small_label.pack(side=tk.LEFT, padx=5)

        # ── スライダー ──
        tk.Label(self, text="残量%:", font=("Meiryo", 10),
                 bg="#2d2d2d", fg="white").pack(pady=(15, 0))
        self._slider = tk.Scale(
            self, from_=100, to=0, orient=tk.VERTICAL,
            command=self._on_slider_change,
            bg="#2d2d2d", fg="white", troughcolor="#555555",
            highlightthickness=0, length=200, width=30,
            font=("Meiryo", 10)
        )
        self._slider.set(100)
        self._slider.pack(pady=5)

        # ── 数値入力 ──
        input_frame = tk.Frame(self, bg="#2d2d2d")
        input_frame.pack(pady=5)
        tk.Label(input_frame, text="直接入力:", font=("Meiryo", 10),
                 bg="#2d2d2d", fg="white").pack(side=tk.LEFT, padx=5)
        self._entry = tk.Entry(input_frame, width=6, font=("Meiryo", 12))
        self._entry.insert(0, "100")
        self._entry.pack(side=tk.LEFT, padx=5)
        self._entry.bind("<Return>", self._on_entry_submit)
        tk.Button(input_frame, text="適用", font=("Meiryo", 10),
                  command=self._on_entry_submit).pack(side=tk.LEFT, padx=5)

        # ── モード切替 ──
        mode_frame = tk.Frame(self, bg="#2d2d2d")
        mode_frame.pack(pady=10)
        tk.Label(mode_frame, text="モード:", font=("Meiryo", 10),
                 bg="#2d2d2d", fg="white").pack(side=tk.LEFT, padx=5)
        for text, val in [("セッション", "session"), ("追加使用量", "extra")]:
            tk.Radiobutton(
                mode_frame, text=text, variable=self._mode, value=val,
                command=self._update_preview, font=("Meiryo", 10),
                bg="#2d2d2d", fg="white", selectcolor="#444444",
                activebackground="#2d2d2d", activeforeground="white"
            ).pack(side=tk.LEFT, padx=10)

        # ── 点滅テスト ──
        blink_frame = tk.Frame(self, bg="#2d2d2d")
        blink_frame.pack(pady=5)
        self._blink_btn = tk.Button(
            blink_frame, text="▶ 点滅開始", font=("Meiryo", 10),
            command=self._toggle_blink, width=14
        )
        self._blink_btn.pack(side=tk.LEFT, padx=5)
        self._blink_status = tk.Label(
            blink_frame, text="", font=("Meiryo", 9),
            bg="#2d2d2d", fg="#aaaaaa"
        )
        self._blink_status.pack(side=tk.LEFT, padx=5)

        # ── プリセットボタン ──
        preset_frame = tk.Frame(self, bg="#2d2d2d")
        preset_frame.pack(pady=10)
        for pct in [100, 95, 85, 75, 65, 55, 45, 35, 25, 15, 5, 0]:
            tk.Button(
                preset_frame, text=f"{pct}", width=3,
                font=("Meiryo", 9),
                command=lambda p=pct: self._set_pct(p)
            ).pack(side=tk.LEFT, padx=2)

        self._update_preview()

    def _on_slider_change(self, val):
        self._entry.delete(0, tk.END)
        self._entry.insert(0, str(int(float(val))))
        self._update_preview()

    def _on_entry_submit(self, event=None):
        try:
            val = int(self._entry.get())
            val = max(0, min(100, val))
            self._slider.set(val)
            self._entry.delete(0, tk.END)
            self._entry.insert(0, str(val))
            self._update_preview()
        except ValueError:
            pass

    def _set_pct(self, pct):
        self._slider.set(pct)
        self._entry.delete(0, tk.END)
        self._entry.insert(0, str(pct))
        self._update_preview()

    def _update_preview(self):
        pct = float(self._slider.get())
        mode = self._mode.get()
        dim = self._dim.get()

        img = make_gauge_icon(pct=pct, mode=mode, dim=dim)

        # 拡大プレビュー
        img_large = img.resize((192, 192), resample=0)
        self._tk_img = ImageTk.PhotoImage(img_large)
        self._preview_label.config(image=self._tk_img)

        # 実寸プレビュー
        img_small = img.resize((16, 16), resample=1)
        self._tk_small = ImageTk.PhotoImage(img_small)
        self._small_label.config(image=self._tk_small)

        # 情報表示
        lit = _get_lit_count(pct)
        color = _get_color(pct, mode)
        color_name = {
            (41, 128, 185): "青",
            (46, 204, 113): "黄緑",
            (230, 126, 34): "オレンジ",
            (231, 76, 60): "赤",
        }.get(color, str(color))

        if pct <= 0:
            info = "0%  →  赤バツ印"
        else:
            blink = ""
            if pct < 5:
                blink = " [早い点滅]"
            elif pct < 15:
                blink = " [ゆっくり点滅]"
            info = f"{int(pct)}%  →  {lit}段  {color_name}{blink}"
            if dim:
                info += "  (暗転)"

        self._info_label.config(text=info)


    def _toggle_blink(self):
        if self._blink_active:
            self._stop_blink()
        else:
            self._start_blink()

    def _start_blink(self):
        pct = float(self._slider.get())
        if pct >= 15:
            self._blink_status.config(text="15%未満で点滅します")
            return
        self._blink_active = True
        self._blink_state = False
        self._blink_btn.config(text="■ 点滅停止")
        interval = 500 if pct < 5 else 1500
        self._blink_status.config(
            text=f"{'早い' if pct < 5 else 'ゆっくり'}点滅中 ({interval}ms)")
        self._blink_tick(interval)

    def _stop_blink(self):
        self._blink_active = False
        self._blink_state = False
        self._dim.set(False)
        if self._blink_job:
            self.after_cancel(self._blink_job)
            self._blink_job = None
        self._blink_btn.config(text="▶ 点滅開始")
        self._blink_status.config(text="")
        self._update_preview()

    def _blink_tick(self, interval):
        if not self._blink_active:
            return
        self._blink_state = not self._blink_state
        self._dim.set(self._blink_state)
        self._update_preview()
        self._blink_job = self.after(interval, self._blink_tick, interval)


if __name__ == "__main__":
    app = TrayIconTester()
    app.mainloop()
