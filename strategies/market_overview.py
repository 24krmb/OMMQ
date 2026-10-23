# -*- coding: utf-8 -*-
"""A 股市场全景日报：四大指数走势 + 成交额 + 市场涨跌家数

内容：
    1. 上证指数 / 深证成指 / 创业板指 / 沪深300 近 N 个交易日走势（起点=100 归一化）
       叠加 上证综指成交额（双轴，亿元）
    2. 全市场 上涨 / 平盘 / 下跌 家数
    3. 全市场 涨停 / 跌停（含真实涨停 / 真实跌停）家数

数据源：
    - 指数日线（收盘）：新浪 ak.stock_zh_index_daily
      sh000001 上证综指 / sz399001 深证成指 / sz399006 创业板指 / sh000300 沪深300
    - 成交额：中证指数官网 ak.stock_zh_index_hist_csindex("000001")（上证综指成交金额，亿元）
    - 涨跌家数：乐咕乐股 ak.stock_market_activity_legu
说明：东方财富接口限流，故全部改用新浪 / 中证指数 / 乐咕数据源。
输出：strategies/output/market_overview_<日期>.png
运行：uv run python strategies/market_overview.py [交易日数]
"""

from __future__ import annotations

import datetime as dt
import os
import sys
import warnings

import akshare as ak
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

warnings.filterwarnings("ignore")
matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
matplotlib.rcParams["axes.unicode_minus"] = False
# 统一配色 24K-Claw：红 #F36 / 绿 #0C9 / 蓝 #99F / 黄 #FC3；字体色 #27254c
matplotlib.rcParams["text.color"] = "#27254c"
matplotlib.rcParams["axes.labelcolor"] = "#27254c"
matplotlib.rcParams["axes.titlecolor"] = "#27254c"
matplotlib.rcParams["xtick.color"] = "#27254c"
matplotlib.rcParams["ytick.color"] = "#27254c"

N = 60  # 展示最近多少个交易日
OUT_DIR = "strategies/output"
UP_COLOR = "#F36"    # 红涨
DOWN_COLOR = "#0C9"  # 绿跌
FLAT_COLOR = "#99F"  # 平盘

# 名称 -> 新浪代码
INDICES: dict[str, str] = {
    "上证指数": "sh000001",
    "深证成指": "sz399001",
    "创业板指": "sz399006",
    "沪深300": "sh000300",
}
LINE_COLORS = {
    "上证指数": "#F36",
    "深证成指": "#99F",
    "创业板指": "#FC3",
    "沪深300": "#0C9",
}


def latest_trade_date() -> dt.date:
    """最近一个已收盘交易日（含今天）。"""
    try:
        dates = ak.tool_trade_date_hist_sina()["trade_date"]
        today = dt.date.today()
        past = [d for d in dates if d <= today]
        return past[-1] if past else today
    except Exception:  # noqa: BLE001
        return dt.date.today()


def fetch_index(symbol: str, n: int) -> pd.Series:
    """指数日收盘（近 n 个交易日）。"""
    df = ak.stock_zh_index_daily(symbol=symbol)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")["close"].tail(n)


def fetch_sh_turnover(n: int) -> pd.Series:
    """上证综指成交额（亿元，近 n 个交易日，中证指数官网）。"""
    end = dt.date.today()
    start = end - dt.timedelta(days=int(n * 2.2) + 30)
    df = ak.stock_zh_index_hist_csindex(
        symbol="000001",
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
    )
    df["日期"] = pd.to_datetime(df["日期"])
    return df.set_index("日期")["成交金额"].tail(n)


def fetch_breadth() -> dict[str, object]:
    """全市场涨跌家数（乐咕乐股）。"""
    df = ak.stock_market_activity_legu()
    out: dict[str, object] = {}
    for _, row in df.iterrows():
        key = str(row["item"]).strip()
        val = row["value"]
        try:
            out[key] = float(val)
        except (TypeError, ValueError):
            out[key] = str(val)
    return out


def plot_index(ax, closes: dict[str, pd.Series], turnover: pd.Series, n: int) -> None:
    """四大指数归一化走势 + 上证成交额双轴。"""
    ax2 = ax.twinx()
    # 成交额柱（右轴，先画以置底）
    ax2.bar(
        turnover.index, turnover.values, width=1.0,
        color="#99F", alpha=0.55, label="上证综指成交额（右轴）",
    )
    ax2.set_ylabel("成交额（亿元）", color="#27254c", fontsize=11)
    ax2.tick_params(axis="y", labelcolor="#27254c")
    ax2.set_ylim(0, turnover.max() * 3.2)

    for name, s in closes.items():
        base = s.iloc[0]
        rebased = s / base * 100
        ax.plot(
            s.index, rebased.values, marker="", linewidth=1.6,
            color=LINE_COLORS.get(name, None), label=name,
        )
        ax.annotate(
            f"{rebased.iloc[-1]:.1f}",
            xy=(rebased.index[-1], rebased.iloc[-1]),
            xytext=(5, 0), textcoords="offset points",
            color="#27254c", fontsize=10, va="center",
        )

    ax.axhline(100, color="#bbb", linewidth=0.8, linestyle="--")
    ax.set_ylabel("归一化（起点=100）", fontsize=11)
    ax.set_title(f"四大指数近 {n} 个交易日走势（起点=100）与沪市成交额", fontsize=13)
    ax.grid(linestyle="--", alpha=0.3)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=9, ncol=2)
    ax.tick_params(axis="x", rotation=30, labelsize=9)


def plot_breadth_bar(ax, breadth: dict[str, object]) -> None:
    """上涨 / 平盘 / 下跌 家数。"""
    keys = ["上涨", "平盘", "下跌"]
    vals = [float(breadth.get(k, 0) or 0) for k in keys]
    colors = [UP_COLOR, FLAT_COLOR, DOWN_COLOR]
    bars = ax.bar(keys, vals, color=colors, width=0.6)
    ax.set_title("全市场涨跌家数", fontsize=13)
    ax.set_ylabel("家数")
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{int(v)}",
                ha="center", va="bottom", fontsize=11)


def plot_limit_bar(ax, breadth: dict[str, object]) -> None:
    """涨停 / 跌停（含真实口径）。"""
    keys = ["涨停", "跌停", "真实涨停", "真实跌停"]
    vals = [float(breadth.get(k, 0) or 0) for k in keys]
    colors = [UP_COLOR, DOWN_COLOR, "#F36", "#0C9"]
    bars = ax.bar(keys, vals, color=colors, width=0.6)
    ax.set_title("全市场涨跌停家数", fontsize=13)
    ax.set_ylabel("家数")
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{int(v)}",
                ha="center", va="bottom", fontsize=11)


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else N
    date = latest_trade_date()

    closes = {name: fetch_index(sym, n) for name, sym in INDICES.items()}
    turnover = fetch_sh_turnover(n)
    breadth = fetch_breadth()

    fig = plt.figure(figsize=(15, 9))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.7, 1.0], hspace=0.28, wspace=0.22)
    ax_top = fig.add_subplot(gs[0, :])
    ax_bl = fig.add_subplot(gs[1, 0])
    ax_br = fig.add_subplot(gs[1, 1])

    plot_index(ax_top, closes, turnover, n)
    plot_breadth_bar(ax_bl, breadth)
    plot_limit_bar(ax_br, breadth)

    stat = breadth.get("统计日期", "")
    fig.suptitle(
        f"A股市场全景日报（数据日期 {date}，活跃度统计 {stat}）　来源：24K-Claw",
        fontsize=16, fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"market_overview_{date:%Y%m%d}.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"图表已保存: {out}")

    print("\n[四大指数 区间表现]")
    for name, s in closes.items():
        base = s.iloc[0]
        print(f"  {name:6s} 期末 {s.iloc[-1]:9.2f}  区间 {(s.iloc[-1]/base-1)*100:+.2f}%")
    print(f"\n[沪市成交额] 最新 {turnover.iloc[-1]:.0f} 亿元  近{n}日均值 {turnover.mean():.0f} 亿元")
    print("\n[市场涨跌家数]")
    for k in ["上涨", "平盘", "下跌", "涨停", "跌停", "真实涨停", "真实跌停", "停牌"]:
        if k in breadth:
            print(f"  {k:6s} {int(float(breadth[k] or 0))}")


if __name__ == "__main__":
    main()
