# -*- coding: utf-8 -*-
"""个股资金流：单只个股多周期资金净额 + 全市场资金流排行

内容（2×2）：
    1. 目标个股 · 各周期资金净额（当日 / 3日 / 5日 / 10日 / 20日）
    2. 目标个股 · 当日资金 流入 vs 流出（净额）
    3. 当日 全市场 资金净流入 TOP10 个股
    4. 当日 全市场 资金净流出 TOP10 个股

数据源：同花顺 ak.stock_fund_flow_individual（symbol="即时"/"3日排行"/…）
口径说明 / 数据限制：
    - 东方财富 个股主力资金流向历史接口（push2his）在本机被限流，无法取数；
    - 本图采用「同花顺 资金流」口径：以资金流入/流出净额刻画个股资金动向，
      并给出全市场横向排行，替代主力资金历史曲线。
输出：reports/YYYYMMDD/11_<代码>.png（编号规则见 strategies/plot_paths.py）
运行：uv run python strategies/stock_money_flow.py [股票代码]   # 默认 600519
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

UP_COLOR = "#F36"
DOWN_COLOR = "#0C9"
WINDOWS = [("即时", "当日"), ("3日排行", "3日"), ("5日排行", "5日"),
           ("10日排行", "10日"), ("20日排行", "20日")]


def _to_yi(value) -> float | None:
    """'3.16亿' / '-6448.25万' / '4185.00'(元) -> 亿元。"""
    s = str(value).strip().replace(",", "")
    if s in ("", "--", "None", "nan", "False"):
        return None
    if s.endswith("亿"):
        mult, s = 1.0, s[:-1]
    elif s.endswith("万"):
        mult, s = 1e-4, s[:-1]
    elif s.endswith("元"):
        mult, s = 1e-8, s[:-1]
    else:               # 无单位 -> 同花顺按「元」输出
        mult = 1e-8
    try:
        return float(s) * mult
    except ValueError:
        return None


def fetch_instant() -> pd.DataFrame:
    df = ak.stock_fund_flow_individual(symbol="即时")
    df = df.copy()
    df["股票代码"] = pd.to_numeric(df["股票代码"], errors="coerce").astype("Int64")
    df["净额亿"] = df["净额"].map(_to_yi)
    df["流入亿"] = df["流入资金"].map(_to_yi)
    df["流出亿"] = df["流出资金"].map(_to_yi)
    return df


def fetch_window(symbol: str) -> pd.DataFrame:
    df = ak.stock_fund_flow_individual(symbol=symbol)
    df = df.copy()
    df["股票代码"] = pd.to_numeric(df["股票代码"], errors="coerce").astype("Int64")
    df["净额亿"] = df["资金流入净额"].map(_to_yi)
    return df


def plot_windows(ax, code: int, nets: dict[str, float | None]) -> None:
    labels = list(nets.keys())
    vals = [0 if v is None else v for v in nets.values()]
    colors = [UP_COLOR if v >= 0 else DOWN_COLOR for v in vals]
    bars = ax.bar(labels, vals, color=colors, width=0.55)
    ax.axhline(0, color="#888", linewidth=0.8)
    ax.set_ylabel("资金净额（亿元）")
    ax.set_title(f"{code} · 各周期资金净额", fontsize=13)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:+.2f}", ha="center",
                va="bottom" if v >= 0 else "top", fontsize=10)


def plot_inout(ax, code: int, inst: pd.Series | None) -> None:
    if inst is None:
        ax.text(0.5, 0.5, "个股即时资金流数据不可用", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(f"{code} · 当日资金流", fontsize=13)
        return
    infl = inst.get("流入亿") or 0
    outfl = inst.get("流出亿") or 0
    net = inst.get("净额亿") or 0
    bars = ax.bar(["流入资金", "流出资金", "净额"], [infl, outfl, net],
                  color=[UP_COLOR, DOWN_COLOR, UP_COLOR if net >= 0 else DOWN_COLOR], width=0.55)
    ax.axhline(0, color="#888", linewidth=0.8)
    ax.set_ylabel("金额（亿元）")
    ax.set_title(f"{code} · 当日资金 流入 / 流出 / 净额", fontsize=13)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    for b, v in zip(bars, [infl, outfl, net]):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:+.2f}", ha="center",
                va="bottom" if v >= 0 else "top", fontsize=10)


def plot_rank(ax, df: pd.DataFrame, top: bool) -> None:
    d = df.dropna(subset=["净额亿"]).copy()
    d = d.nlargest(10, "净额亿") if top else d.nsmallest(10, "净额亿")
    d = d.sort_values("净额亿")
    labels = [f"{n}（{c}）" for n, c in zip(d["股票简称"], d["股票代码"])]
    colors = [UP_COLOR if v >= 0 else DOWN_COLOR for v in d["净额亿"]]
    ax.barh(labels, d["净额亿"], color=colors)
    ax.axvline(0, color="#888", linewidth=0.8)
    ax.set_xlabel("资金净额（亿元）")
    ax.set_title("当日 全市场 资金净流入 TOP10" if top else "当日 全市场 资金净流出 TOP10", fontsize=13)
    ax.grid(axis="x", linestyle="--", alpha=0.3)
    ax.margins(x=0.18)
    for y, v in enumerate(d["净额亿"]):
        ax.text(v, y, f" {v:+.1f}", va="center", ha="left" if v >= 0 else "right", fontsize=9)


def main() -> None:
    code = sys.argv[1].strip() if len(sys.argv) > 1 else "600519"
    code_i = int(code)

    inst = fetch_instant()
    cur = inst[inst["股票代码"] == code_i]
    inst_row = cur.iloc[0] if not cur.empty else None
    name = str(inst_row["股票简称"]) if inst_row is not None else code

    nets: dict[str, float | None] = {}
    for sym, lab in WINDOWS:
        if sym == "即时":
            nets[lab] = float(inst_row["净额亿"]) if inst_row is not None else None
            continue
        try:
            wdf = fetch_window(sym)
            r = wdf[wdf["股票代码"] == code_i]
            nets[lab] = float(r.iloc[0]["净额亿"]) if not r.empty else None
        except Exception as e:  # noqa: BLE001
            print(f"  [跳过] {lab}: {type(e).__name__}")
            nets[lab] = None

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    plot_windows(axes[0, 0], code_i, nets)
    plot_inout(axes[0, 1], code_i, inst_row)
    plot_rank(axes[1, 0], inst, top=True)
    plot_rank(axes[1, 1], inst, top=False)

    fig.suptitle(
        f"{name}（{code}）个股资金流（同花顺口径）　来源：24K-Claw",
        fontsize=16, fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    out = report_image_path(11, code)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"图表已保存: {out}")

    print(f"\n[{name}（{code}）各周期资金净额]")
    for k, v in nets.items():
        print(f"  {k:4s} {('%.2f' % v) if v is not None else '不可用':>9s} 亿元")
    if inst_row is not None:
        print(f"  当日 流入 {inst_row['流入亿']:.2f} 亿 / 流出 {inst_row['流出亿']:.2f} 亿")
    print(f"\n[全市场当日净流入 TOP5]")
    print(inst.dropna(subset=['净额亿']).nlargest(5, "净额亿")[["股票代码", "股票简称", "净额亿"]]
          .to_string(index=False, float_format=lambda v: f"{v:+.2f}"))


if __name__ == "__main__":
    main()
