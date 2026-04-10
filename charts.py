"""Usage Tracker - matplotlibグラフ生成"""
import logging
from collections import defaultdict
from matplotlib.figure import Figure
import config

logger = logging.getLogger(__name__)

try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = ["Meiryo", "MS Gothic", "DejaVu Sans"]
except Exception as e:
    logger.warning("matplotlib初期化警告: %s", e)


def make_hourly_bar_chart(hourly_data: list, title: str = None, fig: Figure = None) -> Figure:
    """
    時間別/日別トークン消費棒グラフを返す。
    hourly_data: [{"hour": "2026-04-10T14" or "2026-04-10", "model": "...", "total_tokens": 12345}, ...]
    title: グラフタイトル（省略時は自動判定）
    """
    if fig is None:
        fig = Figure(figsize=(7, 3), facecolor=config.BG_COLOR)
    ax = fig.add_subplot(111)
    ax.set_facecolor(config.BG_COLOR)
    fig.patch.set_facecolor(config.BG_COLOR)

    if not hourly_data:
        ax.text(0.5, 0.5, "データなし", ha="center", va="center",
                transform=ax.transAxes, fontsize=11, color="#888888")
        ax.set_axis_off()
        return fig

    models = sorted({r["model"] for r in hourly_data if r.get("model")})
    hours_set = sorted({r["hour"] for r in hourly_data if r.get("hour")})

    if not hours_set:
        ax.text(0.5, 0.5, "データなし", ha="center", va="center", transform=ax.transAxes)
        return fig

    model_hour_tokens: dict = defaultdict(lambda: defaultdict(int))
    for r in hourly_data:
        model_hour_tokens[r["model"]][r["hour"]] += r.get("total_tokens", 0)

    n_models = max(len(models), 1)
    bar_width = 0.8 / n_models
    x = list(range(len(hours_set)))

    for i, model in enumerate(models):
        vals = [model_hour_tokens[model].get(h, 0) for h in hours_set]
        offset = (i - (n_models - 1) / 2) * bar_width
        ax.bar(
            [xi + offset for xi in x],
            vals,
            width=bar_width,
            label=config.get_model_display(model),
            color=config.get_model_color(model),
            alpha=0.85
        )

    # X軸ラベル: 時間単位 or 日単位を自動判定
    labels = []
    for h in hours_set:
        if len(h) == 13 and 'T' in h:
            labels.append(h[-2:] + ":00")
        elif len(h) == 10:
            labels.append(h[5:7] + "/" + h[8:10])
        else:
            labels.append(h[-5:] if len(h) >= 5 else h)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, fontsize=7, ha="right")
    ax.set_ylabel("トークン数", fontsize=8)
    ax.legend(fontsize=8, loc="upper left")

    if title:
        ax.set_title(title, fontsize=9)
    else:
        if hours_set and len(hours_set[0]) == 13:
            ax.set_title("時間別トークン消費", fontsize=9)
        else:
            ax.set_title("日別トークン消費", fontsize=9)

    ax.tick_params(axis="both", labelsize=7)
    fig.tight_layout(pad=1.5)
    return fig


def make_model_pie_chart(model_data: list, title: str = None, fig: Figure = None) -> Figure:
    """
    モデル別円グラフ。
    model_data: [{"model": "...", "total_tokens": 12345}, ...]
    """
    if fig is None:
        fig = Figure(figsize=(4, 3), facecolor=config.BG_COLOR)
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor(config.BG_COLOR)

    filtered = [r for r in model_data if r.get("total_tokens", 0) > 0]

    if not filtered:
        ax.text(0.5, 0.5, "データなし", ha="center", va="center",
                transform=ax.transAxes, fontsize=10, color="#888888")
        ax.set_axis_off()
        return fig

    labels = [config.get_model_display(r["model"]) for r in filtered]
    values = [r["total_tokens"] for r in filtered]
    colors = [config.get_model_color(r["model"]) for r in filtered]

    ax.pie(values, labels=labels, colors=colors, autopct="%1.0f%%",
           textprops={"fontsize": 8}, startangle=90)
    ax.set_title(title or "モデル別使用比率", fontsize=9)
    fig.tight_layout()
    return fig


def make_project_bar_chart(project_data: list, fig: Figure = None) -> Figure:
    """
    プロジェクト別横棒グラフ（F-9: プロジェクト外をグレー＋破線セパレータで分離）。
    project_data: [{"project_name": "...", "total_tokens": 12345}, ...]
    """
    if fig is None:
        fig = Figure(figsize=(7, 5), facecolor=config.BG_COLOR)
    ax = fig.add_subplot(111)
    ax.set_facecolor(config.BG_COLOR)
    fig.patch.set_facecolor(config.BG_COLOR)

    filtered = [r for r in project_data if r.get("total_tokens", 0) > 0]

    if not filtered:
        ax.text(0.5, 0.5, "データなし", ha="center", va="center",
                transform=ax.transAxes, fontsize=11, color="#888888")
        ax.set_axis_off()
        return fig

    # プロジェクト内 / プロジェクト外を分離
    normal = []
    external = []
    for r in filtered:
        pname = r.get("project_name") or ""
        if not pname or pname == "unknown":
            external.append(r)
        else:
            normal.append(r)

    # 上位15件に制限
    normal = normal[:15]

    # 結合: 通常プロジェクト + プロジェクト外
    combined = normal + external
    if not combined:
        ax.text(0.5, 0.5, "データなし", ha="center", va="center",
                transform=ax.transAxes, fontsize=11, color="#888888")
        ax.set_axis_off()
        return fig

    # 下から上に並べる
    names = [r.get("project_name") or "(プロジェクト外)" for r in combined][::-1]
    values = [r.get("total_tokens", 0) for r in combined][::-1]

    # 色: プロジェクト外はグレー
    ext_count = len(external)
    colors = []
    for i in range(len(combined)):
        if i < ext_count:
            colors.append("#999999")
        else:
            colors.append(config.ACCENT_COLOR)
    colors = colors[::-1]

    y = list(range(len(names)))
    ax.barh(y, values, color=colors, alpha=0.85)
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xlabel("総トークン数", fontsize=8)
    ax.set_title("プロジェクト別トークン消費", fontsize=9)
    ax.tick_params(axis="both", labelsize=7)

    # プロジェクト外との境界に破線セパレータ
    if normal and external:
        sep_y = ext_count - 0.5
        ax.axhline(y=sep_y, color='gray', linestyle='--', linewidth=0.8)

    fig.tight_layout(pad=1.5)
    return fig


def make_tool_bar_chart(tool_data: list, fig: Figure = None) -> Figure:
    """
    アクション（ツール）別横棒グラフ（F-9）。
    tool_data: [{"tool_name": "Read", "use_count": 42, "input_tokens": ..., ...}, ...]
    """
    if fig is None:
        fig = Figure(figsize=(7, 5), facecolor=config.BG_COLOR)
    ax = fig.add_subplot(111)
    ax.set_facecolor(config.BG_COLOR)
    fig.patch.set_facecolor(config.BG_COLOR)

    if not tool_data:
        ax.text(0.5, 0.5, "データなし", ha="center", va="center",
                transform=ax.transAxes, fontsize=11, color="#888888")
        ax.set_axis_off()
        return fig

    # コスト計算・ソート
    items = []
    for r in tool_data:
        cost = config.calc_cost(
            r.get("model") or "default",
            r.get("input_tokens", 0),
            r.get("output_tokens", 0),
            r.get("cache_creation_tokens", 0),
            r.get("cache_read_tokens", 0)
        )
        items.append({
            "name": r.get("tool_name", "?"),
            "cost": cost,
            "count": r.get("use_count", 0),
        })

    items.sort(key=lambda x: x["cost"], reverse=True)
    items = items[:15]

    # 下から上に並べる
    names = [it["name"] for it in items][::-1]
    costs = [it["cost"] for it in items][::-1]
    counts = [it["count"] for it in items][::-1]

    # ツール名に応じた色
    tool_colors = {
        "Read": "#3498db", "Write": "#e74c3c", "Edit": "#e67e22",
        "Bash": "#2ecc71", "Glob": "#9b59b6", "Grep": "#1abc9c",
        "WebSearch": "#f39c12", "WebFetch": "#d35400", "Agent": "#8e44ad",
        "Skill": "#2c3e50", "TodoWrite": "#7f8c8d",
    }
    colors = [tool_colors.get(n, config.ACCENT_COLOR) for n in names]

    y = list(range(len(names)))
    ax.barh(y, costs, color=colors, alpha=0.85)
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xlabel("コスト ($)", fontsize=8)
    ax.set_title("アクション別コスト消費", fontsize=9)
    ax.tick_params(axis="both", labelsize=7)

    # バーラベルにコストと回数を表示
    for i, (c, n) in enumerate(zip(costs, counts)):
        if c > 0:
            ax.text(c, i, f' ${c:.2f} ({n}回)', va='center', fontsize=7)

    fig.tight_layout(pad=1.5)
    return fig
