#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
国际金银比近120个交易日走势 + 比值最大回撤
=========================================
主图   : 金银比 = 伦敦金现 ÷ 伦敦银现(同一报价日收盘,均为美元/盎司),取最近 120 个公共交易日
附图   : 比值在窗口内相对滚动前高的回撤——峰日、谷日、最大回撤都只在这 120 日内计算,不是历史全样本
取数   : 按"配对"降级,金/银两条腿必须同源(现货 XAU/XAG 不可用时整对改用 COMEX 主力连续 GC/SI);
         跨源混用会把期货升贴水带进比值,故绝不允许一条现货、一条期货
用法   : .\\.venv\\Scripts\\python.exe strategies/global/plot_gold_silver_ratio_120d.py(仓库根目录运行)
输出   : reports/YYYYMMDD/32_gold_silver_ratio.png(编号规则见 strategies/plot_paths.py)
依赖   : akshare>=1.20  pandas  matplotlib
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

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, os.path.join(_ROOT, "strategies"), _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from gindex_fetch import _series, setup_font
from plot_paths import report_image_path

# ════════════════════════ 可调参数 ════════════════════════
OUT_NO      = 32          # 扩展图编号(09 起),见 strategies/plot_paths.py;1–31 已占用
OUT_AUX     = "gold_silver_ratio"
WINDOW      = 120         # 走势与回撤的交易日窗口长度
MIN_ROWS    = WINDOW + 10 # 单腿最少行数,留冗余以免公共日交集不足
RETRIES     = 2
# (口径说明, 黄金代码, 白银代码) —— 顺序即降级顺序
PAIRS = [
    ("伦敦金银现货", "XAU", "XAG"),
    ("COMEX 金银期货主力连续", "GC", "SI"),
]
# ══════════════════════════════════════════════════════════
TEXT_C    = "#27254c"
TEXT_SOFT = "#73718b"
GRID_C    = "#C9C9D6"
RATIO_C   = "#FC3"   # 金银比主线(金价色系)
DD_C      = "#0C9"   # 回撤为跌幅,按红涨绿跌取绿
MARK_C    = "#9D2D5B"

def _hist_sina(symbol: str) -> pd.Series:
    df = ak.futures_foreign_hist_sina(symbol=symbol)
    return _series(df["date"], df["close"])

def _leg(symbol: str):
    """单腿取数:重试 RETRIES 次,行数不够或全失败返回 None(由调用方整对降级)。"""
    last_err = None
    for attempt in range(RETRIES):
        try:
            s = _hist_sina(symbol)
            if len(s) >= MIN_ROWS:
                return s
            last_err = ValueError(f"仅返回{len(s)}行,不足{MIN_ROWS}")
        except Exception as e:
            last_err = e
        if attempt == 0:
            time.sleep(2)
    print(f"  [失败] {symbol}: {type(last_err).__name__}: {str(last_err)[:70]}")
    return None

def fetch_ratio() -> tuple:
    """返回 (窗口内金银比 Series, 口径说明);所有配对都拿不到同源数据则退出。"""
    for desc, g_sym, s_sym in PAIRS:
        gold, silver = _leg(g_sym), _leg(s_sym)
        if gold is None or silver is None:
            print(f"  [降级] 「{desc}」两条腿不齐,改用下一配对")
            continue
        common = sorted(set(gold.index) & set(silver.index))
        if len(common) < WINDOW:
            print(f"  [降级] 「{desc}」公共交易日仅{len(common)}个(不足{WINDOW}),改用下一配对")
            continue
        ratio = (gold.reindex(common) / silver.reindex(common)).tail(WINDOW)
        print(f"  [取数] {desc}:金 {g_sym} {len(gold)}行 ＋ 银 {s_sym} {len(silver)}行"
              f" → 公共日{len(common)}个,取最近{len(ratio)}个")
        return ratio, desc
    raise SystemExit("金银同源数据不足,无法计算比值,请检查网络或数据源后重试")

def max_drawdown(cur: pd.Series) -> dict:
    """窗口内最大回撤:比值相对其滚动前高的最大跌幅。"""
    dd = cur / cur.cummax() - 1.0
    trough = dd.idxmin()
    peak = cur.loc[:trough].idxmax()
    return {
        "dd": dd,
        "mdd": float(dd.loc[trough]),
        "peak": peak,
        "trough": trough,
        "now_dd": float(dd.iloc[-1]),
        "peak_ratio": float(cur.loc[peak]),
        "trough_ratio": float(cur.loc[trough]),
        "recovered": bool(cur.iloc[-1] >= cur.loc[:trough].max()),
    }

def plot(ratio: pd.Series, st: dict, desc: str):
    dates = ratio.index
    now = float(ratio.iloc[-1])
    hi, lo = float(ratio.max()), float(ratio.min())
    pct_now = float((ratio <= now).mean()) * 100.0

    plt.rcParams.update({
        "figure.facecolor": "#FFFFFF", "axes.facecolor": "#FFFFFF",
        "axes.edgecolor": GRID_C, "axes.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False,
        "xtick.labelsize": 10, "ytick.labelsize": 10,
        "xtick.color": TEXT_SOFT, "ytick.color": TEXT_SOFT,
        "xtick.major.size": 0, "ytick.major.size": 0,
        "axes.labelsize": 11.5, "axes.labelcolor": TEXT_C,
        "axes.titlesize": 11, "text.color": TEXT_C,
        "savefig.facecolor": "#FFFFFF",
    })

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(13.5, 8.4), sharex=True,
        gridspec_kw={"height_ratios": [2.3, 1]},
    )
    fig.subplots_adjust(left=0.075, right=0.985, top=0.855, bottom=0.075, hspace=0.10)

    # ──────────── 主图:金银比 ────────────
    ax1.axvspan(st["peak"], st["trough"], color=GRID_C, alpha=0.28, zorder=0)
    ax1.text(st["peak"] + (st["trough"] - st["peak"]) / 2, lo,
             f"最大回撤区间({st['mdd'] * 100:+.2f}%)",
             ha="center", va="bottom", fontsize=9.5, color=TEXT_SOFT, zorder=2)
    ax1.axhline(float(ratio.mean()), color=TEXT_SOFT, lw=1.0, ls=(0, (5, 4)), alpha=0.6, zorder=1)
    ax1.text(dates[0], float(ratio.mean()), f"  窗口均值 {ratio.mean():.1f}",
             fontsize=9, color=TEXT_SOFT, va="bottom")

    ax1.plot(dates, ratio.values, color=RATIO_C, lw=2.2, solid_capstyle="round", zorder=3)
    ax1.plot(dates[-1], now, "o", ms=6, color=RATIO_C, zorder=5)
    ax1.annotate(f"{now:.1f}", xy=(dates[-1], now), xytext=(-4, 12),
                 textcoords="offset points", ha="right", fontsize=12,
                 fontweight="bold", color=TEXT_C, zorder=6)
    for d, val, dy in ((st["peak"], st["peak_ratio"], 10), (st["trough"], st["trough_ratio"], -16)):
        ax1.plot(d, val, "o", ms=5, color=MARK_C, zorder=5)
        ax1.annotate(f"{val:.1f} {d:%m-%d}", xy=(d, val), xytext=(0, dy),
                     textcoords="offset points", ha="center", fontsize=9.5, color=MARK_C, zorder=6)
    ax1.annotate(f"窗口最低 {lo:.1f}({ratio.idxmin():%m-%d})", xy=(ratio.idxmin(), lo),
                 xytext=(6, -2), textcoords="offset points", fontsize=9.5,
                 color=TEXT_SOFT, va="top")

    pad = (hi - lo) * 0.10
    ax1.set_ylim(lo - pad, hi + pad * 1.6)
    ax1.set_ylabel("金银比(倍)")
    ax1.set_title(f"{desc},比值越高代表黄金相对白银越贵;灰带为窗口内最大回撤区间",
                  fontsize=10.5, color=TEXT_SOFT, loc="left", pad=8)
    ax1.yaxis.grid(True, alpha=0.18, color=GRID_C)
    ax1.set_axisbelow(True)
    plt.setp(ax1.get_xticklabels(), visible=False)

    # ──────────── 附图:比值回撤 ────────────
    dd = st["dd"] * 100.0
    ax2.fill_between(dates, 0, dd.values, color=DD_C, alpha=0.15, zorder=2)
    ax2.plot(dates, dd.values, color=DD_C, lw=1.5, zorder=3)
    ax2.axhline(0, color=TEXT_C, lw=1.0, ls=(0, (4, 4)), alpha=0.35, zorder=1)
    ax2.plot(st["trough"], st["mdd"] * 100, "o", ms=5.5, color=DD_C, zorder=5)
    ax2.annotate(f"最大回撤 {st['mdd'] * 100:.2f}%({st['peak']:%m-%d} 峰 → {st['trough']:%m-%d} 谷)",
                 xy=(st["trough"], st["mdd"] * 100), xytext=(10, 4),
                 textcoords="offset points", fontsize=10, color=DD_C, fontweight="bold", zorder=6)
    ax2.annotate(f"当前 {st['now_dd'] * 100:+.2f}%", xy=(dates[-1], st["now_dd"] * 100),
                 xytext=(-4, 7), textcoords="offset points", ha="right", va="bottom",
                 fontsize=9.5, color=TEXT_SOFT, zorder=6)

    ax2.set_ylim(min(st["mdd"] * 100 * 1.35, -3.0), max(0.5, abs(st["mdd"]) * 100 * 0.12))
    ax2.set_ylabel("回撤(%)")
    ax2.set_title("窗口内比值相对滚动前高的跌幅(回撤只在本 120 日窗口内计算)",
                  fontsize=10.5, color=TEXT_SOFT, loc="left", pad=6)
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax2.yaxis.grid(True, alpha=0.18, color=GRID_C)
    ax2.set_axisbelow(True)

    span_days = (dates[-1] - dates[0]).days
    ax2.set_xlim(dates[0] - pd.Timedelta(days=2), dates[-1] + pd.Timedelta(days=max(2, span_days * 0.02)))
    tick_dates = list(dates[::10])
    if (dates[-1] - tick_dates[-1]).days >= 4:
        tick_dates.append(dates[-1])
    ax2.set_xticks(tick_dates)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))

    if now >= hi - 1e-9:
        head = f"金银比升至 {now:.1f},创近{len(dates)}个交易日新高　区间最大回撤 {st['mdd'] * 100:.2f}%"
    else:
        head = (f"近{len(dates)}个交易日金银比 {now:.1f}(区间 {lo:.1f}~{hi:.1f},"
                f"处于窗口 {pct_now:.0f}% 分位)　区间最大回撤 {st['mdd'] * 100:.2f}%")
    fig.suptitle(f"{head}　数据来源：OMMQ", fontsize=17, fontweight="bold", color=TEXT_C,
                 x=0.0125, ha="left", y=0.965)
    note = (f"区间 {dates[0]:%Y-%m-%d} 至 {dates[-1]:%Y-%m-%d}｜横轴为{len(dates)}个金银共同报价日"
            f"｜口径:{desc},同为美元/盎司同一报价日收盘,计价货币相同故比值不受汇率影响"
            f"｜末点为最新报价(可能为盘中),当前比值处窗口 {pct_now:.0f}% 分位"
            f"｜回撤基线为窗口内滚动前高,窗口外前高不计入")
    fig.text(0.0125, 0.012, note, fontsize=9.5, color=TEXT_SOFT, ha="left")

    out = report_image_path(OUT_NO, OUT_AUX)
    fig.savefig(out, dpi=200, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    print(f"已保存: {out}")
    return out

def main():
    print(f"akshare {ak.__version__} ｜ 窗口: 最近{WINDOW}个共同交易日 ｜ 指标: 国际金银比")
    setup_font()
    ratio, desc = fetch_ratio()
    st = max_drawdown(ratio)
    print(f"  [窗口] {ratio.index[0]:%Y-%m-%d} ~ {ratio.index[-1]:%Y-%m-%d} 共{len(ratio)}个交易日")
    print(f"  [比值] 最新 {ratio.iloc[-1]:.2f} ｜ 窗口最高 {ratio.max():.2f}({ratio.idxmax():%Y-%m-%d})"
          f" ｜ 最低 {ratio.min():.2f}({ratio.idxmin():%Y-%m-%d}) ｜ 均值 {ratio.mean():.2f}")
    print(f"  [回撤] 最大 {st['mdd'] * 100:+.2f}%(峰 {st['peak']:%Y-%m-%d} {st['peak_ratio']:.2f}"
          f" → 谷 {st['trough']:%Y-%m-%d} {st['trough_ratio']:.2f}) ｜ 当前 {st['now_dd'] * 100:+.2f}%"
          f" ｜ {'已修复至窗口前高' if st['recovered'] else '尚未修复'}")
    chg = ratio.iloc[-1] / ratio.iloc[0] * 100 - 100
    print(f"  [涨跌] 比值 {ratio.iloc[0]:.2f} → {ratio.iloc[-1]:.2f}({chg:+.2f}%),"
          f"走高即黄金相对白银走强")
    plot(ratio, st, desc)

if __name__ == "__main__":
    main()
