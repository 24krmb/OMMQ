# -*- coding: utf-8 -*-
"""全球三大指数周度累计收益曲线：沪深300 / 恒生指数 / 标普500

内容：
    取指定日期区间内三大指数的日收盘，以区间前一交易日收盘为基准，
    绘制逐日累计收益曲线（基准日 = 0%），区间内每个交易日均已计入。

数据源（新浪，避免东方财富限流）：
    - 沪深300：ak.stock_zh_index_daily("sh000300")
    - 恒生指数：ak.stock_hk_index_daily_sina("HSI")
    - 标普500：ak.index_us_stock_sina(".INX")
    说明：恒指/标普停市日无数据（如节假日），曲线自动跳过该日。

输出：reports/YYYYMMDD/15_global_index_week.png（编号规则见 strategies/plot_paths.py）
运行：uv run python strategies/global_index_week_curve.py [起始日 YYYYMMDD] [结束日 YYYYMMDD]
"""

from __future__ import annotations

import os
import sys
import warnings

import akshare as ak
import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from plot_paths import report_image_path

warnings.filterwarnings("ignore")
matplotlib.rcParams["font.sans-serif"] = [
    "Microsoft YaHei", "SimHei",           # Windows
    "PingFang SC", "Hiragino Sans GB",     # macOS
    "Arial Unicode MS",
]
matplotlib.rcParams["axes.unicode_minus"] = False
# 统一配色 24K-Claw：红 #F36 / 绿 #0C9 / 蓝 #99F / 黄 #FC3；字体色 #27254c
matplotlib.rcParams["text.color"] = "#27254c"
matplotlib.rcParams["axes.labelcolor"] = "#27254c"
matplotlib.rcParams["axes.titlecolor"] = "#27254c"
matplotlib.rcParams["xtick.color"] = "#27254c"
matplotlib.rcParams["ytick.color"] = "#27254c"

DEFAULT_START = "20261012"
DEFAULT_END = "20261023"

# 名称 -> 新浪代码
INDICES: dict[str, str] = {
    "沪深300": "sh000300",
    "恒生指数": "HSI",
    "标普500": ".INX",
}
LINE_COLORS = {
    "沪深300": "#F36",   # 红
    "恒生指数": "#FC3",  # 黄
    "标普500": "#99F",   # 蓝
}


def fetch_index_close(symbol: str) -> pd.DataFrame:
    """指数历史日线收盘（新浪）。返回 Date(index)/Close。"""
    if symbol == "sh000300":
        df = ak.stock_zh_index_daily(symbol=symbol)
    elif symbol == "HSI":
        df = ak.stock_hk_index_daily_sina(symbol=symbol)
    else:
        df = ak.index_us_stock_sina(symbol=symbol)
    df["date"] = pd.to_datetime(df["date"])
    df = df.rename(columns={"close": "Close"}).set_index("date")
    return df[["Close"]]


def window_cum_return(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp
                      ) -> tuple[float, pd.Series]:
    """区间累计收益：基准 = 区间前一交易日收盘，返回 (基准日收盘, 区间累计收益%)。"""
    base = float(df.loc[df.index < start, "Close"].iloc[-1])
    part = df.loc[(df.index >= start) & (df.index <= end), "Close"]
    cum = part / base - 1.0
    return base, cum * 100.0


def plot_curve(ax: plt.Axes, curves: dict[str, pd.Series],
               base_label: str) -> None:
    """三大指数累计收益曲线，终点标注最终收益%）。"""
    for name, s in curves.items():
        ax.plot(
            s.index, s.values, marker="o", markersize=4, linewidth=1.8,
            color=LINE_COLORS.get(name), label=name,
        )
        ax.annotate(
            f"{s.iloc[-1]:+.2f}%",
            xy=(s.index[-1], s.iloc[-1]),
            xytext=(6, 0), textcoords="offset points",
            color=LINE_COLORS.get(name), fontsize=10, va="center",
            fontweight="bold",
        )

    ax.axhline(0, color="#bbb", linewidth=0.8, linestyle="--")
    ax.set_ylabel("累计收益（%）", fontsize=11)
    ax.set_title("沪深300 / 恒生指数 / 标普500 累计收益", fontsize=12)
    ax.grid(linestyle="--", alpha=0.3)
    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.tick_params(axis="x", labelsize=9)
    ax.legend(loc="best", fontsize=10)


def main() -> None:
    start = pd.Timestamp(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_START)
    end = pd.Timestamp(sys.argv[2] if len(sys.argv) > 2 else DEFAULT_END)

    curves: dict[str, pd.Series] = {}
    for name, sym in INDICES.items():
        df = fetch_index_close(sym)
        base, cum = window_cum_return(df, start, end)
        curves[name] = cum
        print(f"[{name}] 基准日收盘 {base:.2f}  区间最终累计 {cum.iloc[-1]:+.2f}%")

    fig, ax = plt.subplots(figsize=(12, 7))
    plot_curve(ax, curves, base_label="窗口前一交易日")

    fig.suptitle(
        f"全球三大指数累计收益曲线（{start:%Y-%m-%d} ~ {end:%Y-%m-%d}）"
        f"　基准=区间前一交易日收盘　来源：24K-Claw",
        fontsize=15, fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))

    out = report_image_path(15, "global_index_week")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n图表已保存: {out}")

    print("\n[逐日累计收益明细]（基准=区间前一交易日收盘）")
    header = f"  {'日期':<12}" + "".join(f"{n:>10}" for n in INDICES)
    print(header)
    all_dates = sorted({d for s in curves.values() for d in s.index})
    for d in all_dates:
        row = f"  {d:%Y-%m-%d}"
        for name in INDICES:
            s = curves[name]
            val = s.loc[d] if d in s.index else float("nan")
            row += f"{val:>10.2f}" if pd.notna(val) else f"{'--':>10}"
        print(row)


if __name__ == "__main__":
    main()
