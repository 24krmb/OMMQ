# -*- coding: utf-8 -*-
"""资金流趋势：杠杆资金（两融）

内容（1×3）：
    1. 沪市 融资余额 / 两融余额 近 N 个交易日
    2. 沪市 融资余额 单日净增（红正绿负）
    3. 沪市 融资买入额 近 N 个交易日

数据源：
    - 沪市两融：上交所 ak.stock_margin_sse
口径说明 / 数据限制：
    - 东方财富 大盘 / 个股 主力资金流向接口（push2 / push2his）在本机被限流，无法取数；
    - 北向资金“当日净买入”自 2024-08-19 起交易所停止逐日披露，数据已停更，故本图不含北向；
    - 因此本图以「两融（杠杆资金）」作为当期资金流主口径，与主流终端口径一致。
输出：strategies/output/money_flow_trend_<日期>.png
运行：uv run python strategies/money_flow_trend.py [交易日数]   # 默认 60
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

OUT_DIR = "strategies/output"
N = 60              # 展示最近多少个交易日
UP_COLOR = "#F36"
DOWN_COLOR = "#0C9"


def latest_trade_date() -> dt.date:
    try:
        dates = ak.tool_trade_date_hist_sina()["trade_date"]
        today = dt.date.today()
        past = [d for d in dates if d <= today]
        return past[-1] if past else today
    except Exception:  # noqa: BLE001
        return dt.date.today()


def fetch_margin(n: int) -> pd.DataFrame:
    """沪市两融余额（近 n 个交易日，单位亿元）。"""
    end = dt.date.today()
    start = end - dt.timedelta(days=int(n * 1.9) + 40)
    df = ak.stock_margin_sse(start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"))
    df["日期"] = pd.to_datetime(df["信用交易日期"].astype(str))
    for c in ["融资余额", "融资买入额", "融券余量金额", "融资融券余额"]:
        df[c] = pd.to_numeric(df[c], errors="coerce") / 1e8
    df = df.sort_values("日期").tail(n).reset_index(drop=True)
    df["融资净增"] = df["融资余额"].diff()
    return df


def plot_balance(ax, df: pd.DataFrame) -> None:
    x = range(len(df))
    ax.bar(x, df["融资余额"], 0.6, color="#F36", label="融资余额")
    ax2 = ax.twinx()
    ax2.plot(x, df["融资融券余额"], color="#99F", linewidth=1.8, marker="", label="两融余额")
    ax2.set_ylabel("两融余额（亿元）", color="#27254c")
    ax2.tick_params(axis="y", labelcolor="#27254c")
    idx = list(x)
    step = max(1, len(idx) // 8)
    ax.set_xticks(idx[::step])
    ax.set_xticklabels([d.strftime("%m-%d") for d in df["日期"][::step]], rotation=45, fontsize=8)
    ax.set_ylabel("融资余额（亿元）")
    ax.set_title(f"沪市 融资余额 / 两融余额（近 {len(df)} 交易日）", fontsize=13)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=9, loc="lower left")
    ax.grid(axis="y", linestyle="--", alpha=0.3)


def plot_net(ax, df: pd.DataFrame) -> None:
    x = range(len(df))
    vals = df["融资净增"].fillna(0)
    colors = [UP_COLOR if v >= 0 else DOWN_COLOR for v in vals]
    ax.bar(x, vals, 0.7, color=colors)
    ax.axhline(0, color="#888", linewidth=0.8)
    idx = list(x)
    step = max(1, len(idx) // 8)
    ax.set_xticks(idx[::step])
    ax.set_xticklabels([d.strftime("%m-%d") for d in df["日期"][::step]], rotation=45, fontsize=8)
    ax.set_ylabel("融资净增（亿元）")
    ax.set_title("沪市 融资余额 单日净增（红=净买入 / 绿=净偿还）", fontsize=13)
    ax.grid(axis="y", linestyle="--", alpha=0.3)


def plot_buy(ax, df: pd.DataFrame) -> None:
    x = range(len(df))
    ax.bar(x, df["融资买入额"], 0.6, color="#FC3")
    idx = list(x)
    step = max(1, len(idx) // 8)
    ax.set_xticks(idx[::step])
    ax.set_xticklabels([d.strftime("%m-%d") for d in df["日期"][::step]], rotation=45, fontsize=8)
    ax.set_ylabel("融资买入额（亿元）")
    ax.set_title("沪市 融资买入额（近 N 交易日）", fontsize=13)
    ax.grid(axis="y", linestyle="--", alpha=0.3)


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else N
    date = latest_trade_date()

    margin = fetch_margin(n)

    fig, axes = plt.subplots(1, 3, figsize=(20, 6))
    plot_balance(axes[0], margin)
    plot_net(axes[1], margin)
    plot_buy(axes[2], margin)

    fig.suptitle(
        f"A股资金流趋势（杠杆资金·两融，数据日期 {date}）　来源：24K-Claw",
        fontsize=16, fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"money_flow_trend_{date:%Y%m%d}.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"图表已保存: {out}")

    last = margin.iloc[-1]
    print(f"\n[沪市两融] 最新交易日 {last['日期']:%Y-%m-%d}")
    print(f"  融资余额 {last['融资余额']:.0f} 亿元  两融余额 {last['融资融券余额']:.0f} 亿元")
    print(f"  融资买入额 {last['融资买入额']:.0f} 亿元  融资净增 {last['融资净增']:+.1f} 亿元")


if __name__ == "__main__":
    main()
