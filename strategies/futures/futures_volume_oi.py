# -*- coding: utf-8 -*-
"""期货量仓图:主力连续合约 成交量 + 持仓量

内容(2×2):
    1. 主力合约 收盘价 + 成交量(双轴,近 N 个交易日)
    2. 主力合约 持仓量(柱)+ 日增仓(线)
    3. 多品种 持仓量 近 N 日 归一化对比(起点=100)
    4. 多品种 最新 成交/持仓 比(换手活跃度)

数据源:主力连续 ak.futures_main_sina(symbol="RB0"/"I0"/…)
口径:取国内商品期货主力连续合约；持仓量 = 未平仓合约量,日增仓 = 持仓量日变化。
输出:reports/YYYYMMDD/07.png(编号规则见 strategies/plot_paths.py)
运行:uv run python strategies/futures_volume_oi.py [品种代码] [交易日数]   # 默认 RB0 120
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
from plot_paths import report_image_path

warnings.filterwarnings("ignore")
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC","Noto Sans SC","Microsoft YaHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False

matplotlib.rcParams["text.color"] = "#27254c"
matplotlib.rcParams["axes.labelcolor"] = "#27254c"
matplotlib.rcParams["axes.titlecolor"] = "#27254c"
matplotlib.rcParams["xtick.color"] = "#27254c"
matplotlib.rcParams["ytick.color"] = "#27254c"

MAIN_SYM = "RB0"      # 主图品种(主力连续)
N = 120               # 主图展示交易日数
UP_COLOR = "#F36"
DOWN_COLOR = "#0C9"

# 多品种对比(主力连续代码)
MULTI = ["RB0", "I0", "CU0", "M0", "TA0", "SR0", "AU0", "AG0", "MA0", "P0"]
NAME_MAP = {
    "RB": "螺纹钢", "I": "铁矿石", "CU": "铜", "M": "豆粕", "TA": "PTA",
    "SR": "白糖", "AU": "黄金", "AG": "白银", "MA": "甲醇", "P": "棕榈油",
    "HC": "热卷", "AL": "铝", "ZN": "锌", "C": "玉米", "Y": "豆油", "SC": "原油",
}


def label(sym: str) -> str:
    return NAME_MAP.get(sym.rstrip("0123456789"), sym)


def latest_trade_date() -> dt.date:
    try:
        dates = ak.tool_trade_date_hist_sina()["trade_date"]
        today = dt.date.today()
        past = [d for d in dates if d <= today]
        return past[-1] if past else today
    except Exception:  # noqa: BLE001
        return dt.date.today()


def fetch_main(sym: str) -> pd.DataFrame:
    df = ak.futures_main_sina(symbol=sym)
    df = df.rename(columns={
        "日期": "日期", "收盘价": "收盘", "成交量": "成交量", "持仓量": "持仓量",
    })
    df["日期"] = pd.to_datetime(df["日期"])
    for c in ["收盘", "成交量", "持仓量"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["收盘"]).reset_index(drop=True)


def plot_price_vol(ax, df: pd.DataFrame, sym: str) -> None:
    d = df.tail(N)
    ax.plot(d["日期"], d["收盘"], color=UP_COLOR, linewidth=1.6, label="收盘价")
    ax.set_ylabel("收盘价", color=UP_COLOR)
    ax.tick_params(axis="y", labelcolor=UP_COLOR)
    ax2 = ax.twinx()
    ax2.bar(d["日期"], d["成交量"], width=1.0, color="#99F", alpha=0.7, label="成交量")
    ax2.set_ylabel("成交量(手)", color="#27254c")
    ax2.tick_params(axis="y", labelcolor="#27254c")
    ax.set_title(f"{label(sym)} 主力连续 · 收盘价 / 成交量(近 {len(d)} 交易日)", fontsize=13)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=9, loc="upper left")
    ax.grid(linestyle="--", alpha=0.3)
    ax.tick_params(axis="x", rotation=30, labelsize=8)


def plot_oi(ax, df: pd.DataFrame, sym: str) -> None:
    d = df.tail(N).copy()
    d["日增仓"] = d["持仓量"].diff()
    ax.bar(d["日期"], d["持仓量"], width=1.0, color="#99F", label="持仓量")
    ax.set_ylabel("持仓量(手)", color="#27254c")
    ax.tick_params(axis="y", labelcolor="#27254c")
    ax2 = ax.twinx()
    colors = [UP_COLOR if v >= 0 else DOWN_COLOR for v in d["日增仓"].fillna(0)]
    ax2.bar(d["日期"], d["日增仓"], width=1.0, color=colors, alpha=0.9, label="日增仓")
    ax2.axhline(0, color="#888", linewidth=0.8)
    ax2.set_ylabel("日增仓(手)", color="#27254c")
    ax.set_title(f"{label(sym)} 主力连续 · 持仓量 / 日增仓", fontsize=13)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=9, loc="upper left")
    ax.grid(linestyle="--", alpha=0.3)
    ax.tick_params(axis="x", rotation=30, labelsize=8)


def plot_multi_oi(ax, series: dict[str, pd.Series]) -> None:
    for nm, s in series.items():
        if len(s) < 2:
            continue
        rebased = s / s.iloc[0] * 100
        ax.plot(s.index, rebased.values, linewidth=1.3, label=nm)
    ax.axhline(100, color="#bbb", linewidth=0.8, linestyle="--")
    ax.set_ylabel("持仓量 归一化(起点=100)")
    ax.set_title("多品种 · 持仓量走势对比(归一化)", fontsize=13)
    ax.legend(fontsize=8, ncol=3)
    ax.grid(linestyle="--", alpha=0.3)
    ax.tick_params(axis="x", rotation=30, labelsize=8)


def plot_turnover(ax, rows: list[dict]) -> None:
    if not rows:
        ax.text(0.5, 0.5, "多品种数据不可用", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("多品种 · 成交/持仓比", fontsize=13)
        return
    rows = sorted(rows, key=lambda r: r["比"], reverse=True)
    names = [r["名称"] for r in rows]
    vals = [r["比"] for r in rows]
    bars = ax.bar(names, vals, color="#99F", width=0.6)
    ax.set_ylabel("成交量 / 持仓量")
    ax.set_title("多品种 · 最新 成交/持仓 比(活跃度)", fontsize=13)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.tick_params(axis="x", rotation=30, labelsize=9)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.1f}", ha="center", va="bottom", fontsize=9)


def main() -> None:
    sym = sys.argv[1].strip() if len(sys.argv) > 1 else MAIN_SYM
    if not sym.endswith("0"):
        sym += "0"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else N

    main_df = fetch_main(sym)

    oi_series: dict[str, pd.Series] = {}
    turnover_rows: list[dict] = []
    for s in MULTI:
        try:
            df = fetch_main(s).tail(n).set_index("日期")
            if len(df) < 2:
                continue
            oi_series[label(s)] = df["持仓量"]
            vol = df["成交量"].iloc[-1]
            oi = df["持仓量"].iloc[-1]
            if oi:
                turnover_rows.append({"名称": label(s), "比": float(vol) / float(oi)})
        except Exception as e:  # noqa: BLE001
            print(f"  [跳过] {s}: {type(e).__name__}")

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    plot_price_vol(axes[0, 0], main_df, sym)
    plot_oi(axes[0, 1], main_df, sym)
    plot_multi_oi(axes[1, 0], oi_series)
    plot_turnover(axes[1, 1], turnover_rows)

    date = latest_trade_date()
    fig.suptitle(
        f"{label(sym)} 期货量仓图(主力连续,近 {n} 交易日)　来源:24K-Claw",
        fontsize=16, fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    out = report_image_path(7)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"图表已保存: {out}")

    last = main_df.iloc[-1]
    prev = main_df.iloc[-2] if len(main_df) > 1 else last
    print(f"\n[{label(sym)} 主力连续] 最新 {last['日期']:%Y-%m-%d}")
    print(f"  收盘 {last['收盘']:.1f}  成交量 {last['成交量']:.0f} 手  持仓量 {last['持仓量']:.0f} 手"
          f"  日增仓 {last['持仓量'] - prev['持仓量']:+.0f} 手")


if __name__ == "__main__":
    main()
