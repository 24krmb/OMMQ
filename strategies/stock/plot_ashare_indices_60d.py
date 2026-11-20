#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股主要宽基指数近60个交易日累计收益率对比图
=============================================
指数范围 : 上证指数 / 深证成指 / 创业板指 / 上证50 / 中证500 / 中证1000 / 国证2000
           (覆盖大盘→小盘的规模梯度:上证50 大盘、中证500 中盘、中证1000 小盘、国证2000 偏微盘)
对齐口径 : A股统一交易日对齐——取所有指数共同有行情的最近 60 个交易日,
           各指数统一在区间首日归一化为 0%,起点一致、可直接对比。
口径提醒 : 均为人民币计价价格指数(不含分红);上证指数是综合指数,与其余成分指数口径不同,横向对比时注意。
用法     : python strategies/stock/plot_ashare_indices_60d.py
取数     : 复用 strategies/global/gindex_fetch.py
输出     : reports/YYYYMMDD/31_ashare_index_60d.png
"""

import os
import sys
import time
import warnings
warnings.filterwarnings("ignore")
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
import akshare as ak

_HERE = os.path.dirname(os.path.abspath(__file__))          # strategies/stock
_ROOT = os.path.dirname(os.path.dirname(_HERE))             # 仓库根目录
for _p in (os.path.join(_ROOT, "strategies", "global"),
           os.path.join(_ROOT, "strategies"), _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from gindex_fetch import (EM_CALL_PAUSE, N_DAYS, cni_a, csindex_a, fetch_index,
                          setup_font, sina_a)
from plot_paths import report_image_path

# ════════════════════════ 可调参数 ════════════════════════
OUT_NO         = 31          # 扩展图编号(09 起),见 strategies/plot_paths.py;1–30 已占用
OUT_AUX        = "ashare_index_60d"
COLOR_MODE     = "classic"   # "classic"=经典多色；"sign"=红涨绿跌按盈亏着色
LOOKBACK_ROWS  = 120         # 每条指数回看最近120个交易日参与公共日求交集(同市场,交集即日历)
MAX_STALE_DAYS = 10          # 序列最新收盘落后全场超过此天数即剔除,见 main 中的说明
# ══════════════════════════════════════════════════════════
TEXT_C    = "#27254c"
TEXT_SOFT = "#73718b"
POS_C     = "#F36"
NEG_C     = "#0C9"
CLASSIC_PALETTE = ["#F36", "#0C9", "#99F", "#FC3",
                   "#9D2D5B", "#108679", "#6969B4", "#A48628",
                   "#F38FAB", "#73E3C7"]
WARM_FAMILY  = ["#F36", "#FC3", "#9D2D5B", "#A48628", "#F38FAB"]
COOL_FAMILY  = ["#0C9", "#99F", "#108679", "#6969B4", "#73E3C7"]

# ─── 指数清单:新浪优先,官网兜底(官网列名与代码前缀按系列分)───
INDEXES = [
    ("上证指数",
     [("新浪", lambda: sina_a("sh000001")),
      ("中证官网", lambda: csindex_a("000001"))]),
    ("深证成指",
     [("新浪", lambda: sina_a("sz399001")),
      ("国证官网", lambda: cni_a("399001"))]),
    ("创业板指",
     [("新浪", lambda: sina_a("sz399006")),
      ("国证官网", lambda: cni_a("399006"))]),
    ("上证50",
     [("新浪", lambda: sina_a("sh000016")),
      ("中证官网", lambda: csindex_a("000016"))]),
    ("中证500",
     [("新浪", lambda: sina_a("sh000905")),
      ("中证官网", lambda: csindex_a("000905"))]),
    ("中证1000",
     [("新浪", lambda: sina_a("sh000852")),
      ("中证官网", lambda: csindex_a("000852"))]),
    ("国证2000",
     [("新浪", lambda: sina_a("sz399303")),
      ("国证官网", lambda: cni_a("399303"))]),
]

def plot(cur: dict, missing: list):
    dates = cur["__dates__"]
    names = [n for n in cur if n != "__dates__"]
    finals = {n: cur[n].iloc[-1] for n in names}
    best_name = max(names, key=lambda n: finals[n])
    best_val = finals[best_name]
    if COLOR_MODE == "sign":
        pos = [n for n in names if finals[n] >= 0]
        neg = [n for n in names if finals[n] < 0]
        colors = {}
        for i, n in enumerate(pos):
            colors[n] = WARM_FAMILY[i % len(WARM_FAMILY)]
        for i, n in enumerate(neg):
            colors[n] = COOL_FAMILY[i % len(COOL_FAMILY)]
    else:
        colors = {n: CLASSIC_PALETTE[i % len(CLASSIC_PALETTE)] for i, n in enumerate(names)}
    plt.rcParams.update({
        "figure.facecolor": "#FFFFFF", "axes.facecolor": "#FFFFFF",
        "axes.edgecolor": "#C9C9D6", "axes.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False,
        "xtick.major.size": 0, "ytick.major.size": 0,
        "xtick.labelsize": 10, "ytick.labelsize": 10, "xtick.color": TEXT_SOFT,
        "ytick.color": TEXT_SOFT,
        "axes.labelsize": 11.5, "axes.labelcolor": TEXT_C,
        "axes.titlesize": 11, "legend.frameon": False, "legend.fontsize": 10,
        "savefig.facecolor": "#FFFFFF",
    })

    fig, ax = plt.subplots(figsize=(14, 8.2), constrained_layout=True)
    ax.axhline(0, color=TEXT_C, lw=1, ls=(0, (4, 4)), alpha=0.35, zorder=1)
    ax.yaxis.grid(True, alpha=0.15, color="#C9C9D6", zorder=0)
    ax.set_axisbelow(True)
    for n in names:
        ax.plot(dates, cur[n], color=colors[n], lw=2.0, alpha=0.95,
                solid_capstyle="round", zorder=3)
        ax.plot(dates[-1], finals[n], "o", ms=4.5, color=colors[n], zorder=4)
    span_days = (dates[-1] - dates[0]).days
    ax.set_xlim(dates[0] - pd.Timedelta(days=2), dates[-1] + pd.Timedelta(days=max(2, span_days * 0.02)))
    tick_dates = list(dates[::6])
    if (dates[-1] - tick_dates[-1]).days >= 4:
        tick_dates.append(dates[-1])
    ax.set_xticks(tick_dates)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    lo, hi = ax.get_ylim()
    pad = (hi - lo) * 0.08
    ax.set_ylim(lo - pad, hi + pad)
    ax.set_ylabel("累计收益率(%)")
    ax.set_xlabel("交易日(A股统一交易日)")

    order = sorted(names, key=lambda n: finals[n], reverse=True)
    from matplotlib.lines import Line2D
    handles, labels, lab_colors = [], [], []
    for n in order:
        handles.append(Line2D([0], [0], color=colors[n], lw=2.2))
        labels.append(f"{n}({finals[n]:+.2f}%)")
        lab_colors.append(POS_C if finals[n] >= 0 else NEG_C)
    leg = ax.legend(handles, labels, loc="upper left", bbox_to_anchor=(1.02, 1.0),
                    handlelength=1.6, labelspacing=0.62, borderaxespad=0)
    for t, c in zip(leg.get_texts(), lab_colors):
        t.set_color(c)

    if best_val >= 0:
        head = f"近{len(dates)}个交易日A股主要宽基指数累计收益：{best_name}领涨({best_val:+.2f}%)"
    else:
        head = f"近{len(dates)}个交易日A股主要宽基指数普遍回调：{best_name}相对抗跌({best_val:+.2f}%)"

    fig.suptitle(f"{head}　数据来源：OMMQ",
                 fontsize=17, fontweight="bold", color=TEXT_C, x=0.01, ha="left")
    d0, d1 = dates[0], dates[-1]
    note = (f"区间 {d0:%Y-%m-%d} 至 {d1:%Y-%m-%d}"
            f"｜{len(dates)}个A股交易日，起点统一归一化为0%"
            "｜人民币计价价格指数(不含分红)，上证指数为综合指数、口径与成分指数不同")
    if missing:
        note += "｜未纳入: " + "、".join(missing)
    ax.set_title(note, fontsize=10.5, color=TEXT_SOFT, loc="left", pad=12)

    out = report_image_path(OUT_NO, OUT_AUX)
    fig.savefig(out, dpi=200, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    print(f"已保存: {out}")
    return out

def main():
    print(f"akshare {ak.__version__} ｜ 窗口: 最近{N_DAYS}个A股交易日(统一日历对齐)")
    setup_font()
    closes, missing = {}, []
    for label, steps in INDEXES:
        s, src = fetch_index(label, steps, rows=LOOKBACK_ROWS)
        if s is None:
            missing.append(label)
        else:
            closes[label] = s
            print(f"  [取数] {label} <- {src}({len(s)}个交易日，最新 {s.index[-1]:%Y-%m-%d})")
        time.sleep(EM_CALL_PAUSE)
    if len(closes) < 2:
        raise SystemExit("可用指数不足2个，请检查网络或数据源后重试")

    freshest = max(s.index[-1] for s in closes.values())
    for label in list(closes):
        lag = (freshest - closes[label].index[-1]).days
        if lag > MAX_STALE_DAYS:
            print(f"  [剔除] {label} 最新收盘 {closes[label].index[-1]:%Y-%m-%d} 落后{lag}天，数据疑似停更")
            missing.append(f"{label}(停更)")
            del closes[label]

    common = None
    for s in closes.values():
        common = set(s.index) if common is None else (common & set(s.index))
    common = sorted(common)[-N_DAYS:]
    if len(common) < N_DAYS:
        print(f"警告: 公共交易日仅{len(common)}个(不足{N_DAYS})，将按实际天数绘制")
    elif common[-1] != freshest:
        print(f"提示: 区间末位 {common[-1]:%Y-%m-%d} 晚于全场最新收盘 {freshest:%Y-%m-%d}"
              f"——有指数当日缺行(多为官网源晚一个交易日)，全图窗口整体前移一天")
    print(f"  [窗口] {common[0]:%Y-%m-%d} ~ {common[-1]:%Y-%m-%d} 共{len(common)}个交易日")
    cur = {"__dates__": pd.DatetimeIndex(common)}
    for label, s in closes.items():
        sub = s.reindex(common)
        cur[label] = (sub / sub.iloc[0] - 1) * 100
    plot(cur, missing)

if __name__ == "__main__":
    main()
