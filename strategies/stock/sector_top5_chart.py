# -*- coding: utf-8 -*-
"""最新交易日 A 股 行业(申万一级)/ 概念 板块涨跌幅 TOP5 中文图表

行业口径:申万一级行业(与 Wind 一致)
    数据源:申万宏源研究-指数系列实时行情 AKShare: ak.index_realtime_sw("一级行业")
    涨跌幅 = 最新价 / 昨收盘 - 1

概念口径:概念板块
    数据源:AKShare: ak.stock_sector_spot(indicator="概念")( newFLJK 概念板块)

说明:东方财富 clist 接口在限流,故行业改用申万一级、概念改用源。
输出:reports/YYYYMMDD/03.png(编号规则见 strategies/plot_paths.py)
运行:uv run python strategies/sector_top5_chart.py
"""

from __future__ import annotations
import datetime as dt
import os
import warnings
import akshare as ak
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from plot_paths import report_image_path

warnings.filterwarnings("ignore")  # 抑制申万接口 verify=False 的 InsecureRequestWarning
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC","Noto Sans SC","Microsoft YaHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False

matplotlib.rcParams["text.color"] = "#27254c"
matplotlib.rcParams["axes.labelcolor"] = "#27254c"
matplotlib.rcParams["axes.titlecolor"] = "#27254c"
matplotlib.rcParams["xtick.color"] = "#27254c"
matplotlib.rcParams["ytick.color"] = "#27254c"

TOP_N = 5
UP_COLOR = "#F36"    # 红涨
DOWN_COLOR = "#0C9"  # 绿跌

def latest_trade_date() -> dt.date:
    """最近一个已收盘交易日(含今天)。"""
    try:
        dates = ak.tool_trade_date_hist_sina()["trade_date"]
        today = dt.date.today()
        past = [d for d in dates if d <= today]
        return past[-1] if past else today
    except Exception:
        return dt.date.today()


def fetch_industry() -> pd.DataFrame:
    """申万一级行业最新涨跌幅。"""
    df = ak.index_realtime_sw(symbol="一级行业")
    df["涨跌幅"] = (df["最新价"] / df["昨收盘"] - 1) * 100
    df = df.rename(columns={"指数名称": "板块"})
    return df[["板块", "涨跌幅"]]


def fetch_concept() -> pd.DataFrame:
    """概念板块最新涨跌幅。"""
    return ak.stock_sector_spot(indicator="概念")[["板块", "涨跌幅"]]


def top5(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["涨跌幅"] = pd.to_numeric(df["涨跌幅"], errors="coerce")
    return df.dropna().sort_values("涨跌幅", ascending=False).head(TOP_N)


def draw(ax, df: pd.DataFrame, title: str) -> None:
    df = df.sort_values("涨跌幅")  # barh 自下而上,涨幅最大的在顶部
    colors = [UP_COLOR if v >= 0 else DOWN_COLOR for v in df["涨跌幅"]]
    ax.barh(df["板块"], df["涨跌幅"], color=colors)
    ax.axvline(0, color="#888888", linewidth=0.8)
    ax.set_title(title, fontsize=14, pad=12)
    ax.set_xlabel("涨跌幅 (%)")
    ax.margins(x=0.20)
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    for y, v in enumerate(df["涨跌幅"]):
        ax.text(
            v + (0.06 if v >= 0 else -0.06), y, f"{v:+.2f}%",
            va="center", ha="left" if v >= 0 else "right", fontsize=10,
        )


def main() -> None:
    date = latest_trade_date()
    ind = top5(fetch_industry())
    con = top5(fetch_concept())

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.2))
    draw(axes[0], ind, f"行业板块(申万一级)涨跌幅 TOP{TOP_N}")
    draw(axes[1], con, f"概念板块涨跌幅 TOP{TOP_N}")
    fig.suptitle(
        f"A股 最新交易日({date})板块涨跌幅 TOP{TOP_N}　来源:24K-Claw",
        fontsize=16, fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))

    out = report_image_path(3)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"图表已保存: {out}")
    print("\n[行业 TOP5 · 申万一级]\n" + ind.to_string(index=False))
    print("\n[概念 TOP5 · ]\n" + con.to_string(index=False))


if __name__ == "__main__":
    main()
