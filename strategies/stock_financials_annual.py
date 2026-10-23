# -*- coding: utf-8 -*-
"""年度财务概览图：以年为单位的营收 / 净利 / EPS / ROE 等长周期概览

内容（2×2）：
    1. 年度 营业总收入 / 净利润（柱状，亿元）
    2. 年度 每股收益(EPS) / 每股经营现金流（折线，元）
    3. 年度 销售毛利率 / 销售净利率（折线，%）
    4. 年度 营业总收入 / 净利润 同比增长率（%，柱状）

数据源：同花顺 ak.stock_financial_abstract_ths(symbol, indicator="按年度")
        （年报口径，营收/净利为全年累计值）
说明：与 stock_financials.py 的**季度**概览图互补，本图按**年度**呈现长周期趋势。
输出：reports/YYYYMMDD/13_<代码>.png（编号规则见 strategies/plot_paths.py）
运行：uv run python strategies/stock_financials_annual.py [股票代码] [年数]   # 默认 600519 10
"""

from __future__ import annotations

import os
import sys
import warnings

import akshare as ak
import matplotlib
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

YEARS = 10          # 展示最近多少个年度
UP_COLOR = "#F36"
DOWN_COLOR = "#0C9"
BAR2 = "#99F"


def _num(value) -> float | None:
    """解析 '1741.44亿' / '-12.5%' / '35.57' 等为数值（金额单位：亿；百分比为百分数）。"""
    s = str(value).strip()
    if s in ("", "False", "--", "None", "nan"):
        return None
    mult = 1.0
    if s.endswith("万亿"):
        mult, s = 1e4, s[:-2]
    elif s.endswith("亿"):
        mult, s = 1.0, s[:-1]
    elif s.endswith("万"):
        mult, s = 1e-4, s[:-1]
    elif s.endswith("%"):
        s = s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return None


def _series(frame: pd.DataFrame, col: str) -> list[float]:
    if col not in frame.columns:
        return [float("nan")] * len(frame)
    return [float("nan") if v is None else v for v in (_num(v) for v in frame[col])]


def fetch_annual(code: str) -> pd.DataFrame:
    df = ak.stock_financial_abstract_ths(symbol=code, indicator="按年度")
    df["报告期"] = df["报告期"].astype(str)
    df = df.sort_values("报告期").reset_index(drop=True)
    return df


def main() -> None:
    code = sys.argv[1].strip() if len(sys.argv) > 1 else "600519"
    years = int(sys.argv[2]) if len(sys.argv) > 2 else YEARS

    df = fetch_annual(code)
    df = df.tail(years).reset_index(drop=True)
    labels = [p[:4] for p in df["报告期"]]
    x = list(range(len(labels)))

    rev = _series(df, "营业总收入")
    profit = _series(df, "净利润")
    eps = _series(df, "基本每股收益")
    cash = _series(df, "每股经营现金流")
    gm = _series(df, "销售毛利率")
    nm = _series(df, "销售净利率")
    grow_rev = _series(df, "营业总收入同比增长率")
    grow_profit = _series(df, "净利润同比增长率")

    fig, axes = plt.subplots(2, 2, figsize=(15, 9.5))

    # (0,0) 营收 / 净利
    ax = axes[0, 0]
    ax.bar([i - 0.2 for i in x], rev, 0.4, label="营业总收入", color=UP_COLOR)
    ax.bar([i + 0.2 for i in x], profit, 0.4, label="净利润", color=BAR2)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, fontsize=9)
    ax.set_ylabel("亿元")
    ax.set_title("年度 营业总收入 / 净利润", fontsize=13)
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.35)

    # (0,1) EPS / 每股经营现金流
    ax = axes[0, 1]
    ax.plot(labels, eps, marker="o", label="每股收益(EPS)", color=UP_COLOR)
    ax.plot(labels, cash, marker="s", label="每股经营现金流", color="#99F")
    ax.tick_params(axis="x", rotation=45, labelsize=9)
    ax.set_ylabel("元")
    ax.set_title("年度 每股收益 / 每股经营现金流", fontsize=13)
    ax.legend()
    ax.grid(linestyle="--", alpha=0.35)

    # (1,0) 毛利率 / 净利率
    ax = axes[1, 0]
    ax.plot(labels, gm, marker="o", label="销售毛利率", color=UP_COLOR)
    ax.plot(labels, nm, marker="s", label="销售净利率", color="#99F")
    ax.tick_params(axis="x", rotation=45, labelsize=9)
    ax.set_ylabel("%")
    ax.set_title("年度 销售毛利率 / 销售净利率", fontsize=13)
    ax.legend()
    ax.grid(linestyle="--", alpha=0.35)

    # (1,1) 同比增速
    ax = axes[1, 1]
    ax.bar([i - 0.2 for i in x], grow_rev, 0.4, label="营业总收入同比", color=UP_COLOR)
    ax.bar([i + 0.2 for i in x], grow_profit, 0.4, label="净利润同比", color=BAR2)
    ax.axhline(0, color="#888", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, fontsize=9)
    ax.set_ylabel("%")
    ax.set_title("年度 同比增长率", fontsize=13)
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.35)

    fig.suptitle(
        f"{code} 年度财务概览（近 {len(labels)} 个年度）　来源：24K-Claw",
        fontsize=16, fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    out = report_image_path(13, code)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"图表已保存: {out}")

    print(f"\n[{code} 年度主要指标]")
    show = ["报告期", "营业总收入", "净利润", "基本每股收益", "净资产收益率", "销售毛利率"]
    show = [c for c in show if c in df.columns]
    print(df[show].to_string(index=False))


if __name__ == "__main__":
    main()
