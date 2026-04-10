"""トレイアイコン ゲージ生成モジュール（F-4/F-7）

マスコット背景 + 半透明ゲージオーバーレイ方式。
縦バー10段ブロック、点灯ブロックのみ描画（消灯=透明）。

段数マッピング:
    100〜95  → 10段（青/黄緑）
    95未満〜85 → 9段
    85未満〜75 → 8段
    75未満〜65 → 7段
    65未満〜55 → 6段（ここまで青/黄緑）
    55未満〜45 → 5段（黄色）
    45未満〜35 → 4段
    35未満〜25 → 3段（ここまで黄色）
    25未満〜15 → 2段（赤）
    15未満〜1  → 1段（赤、15未満でゆっくり点滅、5未満で早い点滅）
    0          → 赤バツ印

使い方:
    from icons.gauge import make_gauge_icon
    img = make_gauge_icon(pct=85, mode="session")
    img = make_gauge_icon(pct=40, mode="extra", dim=True)
    img = make_gauge_icon(pct=0, mode="session")  # 赤バツ印
"""
from pathlib import Path
from PIL import Image, ImageDraw

# ゲージ設定
ICON_SIZE = 64
NUM_BLOCKS = 10
SEGMENT_GAP = 1
PADDING = 4
GAUGE_ALPHA = 204  # ゲージの透明度（80%）

# 色定義
COLOR_BLUE = (41, 128, 185)       # セッション >50%
COLOR_GREEN = (46, 204, 113)      # 追加使用量 >50%
COLOR_YELLOW = (240, 200, 0)      # >20%〜50%
COLOR_RED = (231, 76, 60)         # ≤20%

# 背景画像パス
_ICONS_DIR = Path(__file__).parent
_BG_PATH = _ICONS_DIR / "IMG_6619s2.png"
_bg_cache = None


def _load_bg() -> Image.Image:
    """背景マスコット画像を読み込む（キャッシュ付き）。"""
    global _bg_cache
    if _bg_cache is None:
        if _BG_PATH.exists():
            _bg_cache = Image.open(_BG_PATH).convert("RGBA")
        else:
            # フォールバック: ダークグレー背景
            _bg_cache = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (50, 50, 50, 255))
    return _bg_cache.copy()


def _get_lit_count(pct: float) -> int:
    """残量%から点灯ブロック数を返す。"""
    if pct >= 95:
        return 10
    elif pct >= 85:
        return 9
    elif pct >= 75:
        return 8
    elif pct >= 65:
        return 7
    elif pct >= 55:
        return 6
    elif pct >= 45:
        return 5
    elif pct >= 35:
        return 4
    elif pct >= 25:
        return 3
    elif pct >= 15:
        return 2
    elif pct >= 1:
        return 1
    else:
        return 0  # 0% → バツ印


def _get_color(pct: float, mode: str) -> tuple:
    """残量%とモードに応じたゲージ色(R,G,B)を返す。"""
    if pct > 50:
        return COLOR_BLUE if mode == "session" else COLOR_GREEN
    elif pct > 20:
        return COLOR_YELLOW
    else:
        return COLOR_RED


def _draw_cross(draw: ImageDraw.Draw) -> None:
    """0%用の赤バツ印を描画する（黒縁取り付き）。"""
    margin = 10
    x1, y1 = margin, margin
    x2, y2 = ICON_SIZE - 1 - margin, ICON_SIZE - 1 - margin
    # 縁取り（黒）
    draw.line([x1, y1, x2, y2], fill=(0, 0, 0, 255), width=12)
    draw.line([x1, y2, x2, y1], fill=(0, 0, 0, 255), width=12)
    # 本体（赤）
    draw.line([x1, y1, x2, y2], fill=COLOR_RED + (255,), width=8)
    draw.line([x1, y2, x2, y1], fill=COLOR_RED + (255,), width=8)


def make_gauge_icon(pct: float = 100.0, mode: str = "session",
                    dim: bool = False) -> Image.Image:
    """
    マスコット背景 + 半透明ゲージのアイコンを生成する。

    Args:
        pct: 残量% (0〜100)
        mode: "session"(セッション) or "extra"(追加使用量)
        dim: True=点滅の暗転フレーム（バー色を暗くする）

    Returns:
        64x64 RGBA PIL Image
    """
    pct = max(0.0, min(100.0, pct))
    lit_count = _get_lit_count(pct)

    # 背景マスコット
    bg = _load_bg()

    # 0% → 背景 + 赤バツ印
    if lit_count == 0:
        draw = ImageDraw.Draw(bg)
        _draw_cross(draw)
        return bg

    # ゲージ色
    color = _get_color(pct, mode)
    if dim:
        color = tuple(c // 3 for c in color)

    # ゲージオーバーレイ（点灯ブロックのみ、消灯=透明）
    overlay = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    area_top = PADDING
    area_bottom = ICON_SIZE - 1 - PADDING
    area_height = area_bottom - area_top

    bar_width = (ICON_SIZE - PADDING * 2) // 2
    bar_left = (ICON_SIZE - bar_width) // 2

    block_h = (area_height - SEGMENT_GAP * (NUM_BLOCKS - 1)) / NUM_BLOCKS

    for i in range(NUM_BLOCKS):
        is_lit = (NUM_BLOCKS - 1 - i) < lit_count
        if is_lit:
            y_top = area_top + int(i * (block_h + SEGMENT_GAP))
            y_bottom = area_top + int(i * (block_h + SEGMENT_GAP) + block_h)
            y_bottom = min(y_bottom, area_bottom)
            draw.rectangle([bar_left, y_top, bar_left + bar_width, y_bottom],
                           fill=color + (GAUGE_ALPHA,))

    return Image.alpha_composite(bg, overlay)
