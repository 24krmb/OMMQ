# -*- coding: utf-8 -*-
"""个股技术面图：日 K + 均线 + 成交量 + MACD + RSI

内容（自上而下四个子图，共享横轴）：
    1. 日 K 蜡烛图（红涨绿跌）叠加 MA5 / MA20 / MA60
    2. 成交量柱（红涨绿跌）
    3. MACD（DIF / DEA 折线 + 红绿柱）
    4. RSI(14) 折线（含 30 / 70 参考线）

数据源：新浪个股日线 ak.stock_zh_a_daily(adjust="qfq")（前复权）
指标计算：ta-lib（MACD 12/26/9，RSI 14）
输出：reports/YYYYMMDD/10_<代码>.png（编号规则见 strategies/plot_paths.py）
运行：uv run python strategies/stock_technical.py [股票代码] [交易日数]   # 默认 600519 120
"""

from __future__ import annotations
import os
import sys
import warnings
import akshare as ak
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle
from plot_paths import report_image_path

warnings.filterwarnings("ignore")
matplotlib.rcParams["font.sans-serif"] = [
    "Microsoft YaHei", "SimHei",           # Windows
    "PingFang SC", "Hiragino Sans GB",     # macOS
    "Arial Unicode MS",
]
matplotlib.rcParams["axes.unicode_minus"] = False
# 统一配色 OMMQ：红 #F36 / 绿 #0C9 / 蓝 #99F / 黄 #FC3；字体色 #27254c
matplotlib.rcParams["text.color"] = "#27254c"
matplotlib.rcParams["axes.labelcolor"] = "#27254c"
matplotlib.rcParams["axes.titlecolor"] = "#27254c"
matplotlib.rcParams["xtick.color"] = "#27254c"
matplotlib.rcParams["ytick.color"] = "#27254c"

DEFAULT_CODE = "600519"
DEFAULT_DAYS = 120
UP_COLOR = "#F36"    # 红涨
DOWN_COLOR = "#0C9"  # 绿跌
MA_COLORS = {"MA5": "#F36", "MA20": "#99F", "MA60": "#FC3"}

def sina_prefix(code: str) -> str:
    c = code.strip()
    if c[0] in "569":
        return "sh" + c
    if c[0] in "03":
        return "sz" + c
    if c[0] in "48":
        return "bj" + c
    return "sh" + c


def fetch_daily(code: str, days: int):
    """前复权日线（近 days 个交易日）。"""
    df = ak.stock_zh_a_daily(symbol=sina_prefix(code), adjust="qfq")
    df["date"] = df["date"].astype(str)
    df = df.sort_values("date").reset_index(drop=True)
    return df.tail(days).reset_index(drop=True)


def add_indicators(df):
    import talib
    close = df["close"].astype(float).to_numpy()
    for w in (5, 20, 60):
        df[f"MA{w}"] = df["close"].rolling(w).mean()
    dif, dea, hist = talib.MACD(close, fastperiod=8.3896, slowperiod=17.5195, signalperiod=9.0503)
    df["DIF"] = dif
    df["DEA"] = dea
    df["MACD"] = (dif - dea) * 2
    df["RSI"] = talib.RSI(close, timeperiod=14)
    return df

def _xticks(ax, dates) -> None:
    n = len(dates)
    idx = list(range(0, n, max(1, n // 8)))
    if idx[-1] != n - 1:
        idx.append(n - 1)
    ax.set_xticks(idx)
    ax.set_xticklabels([str(dates[i])[2:] for i in idx], rotation=0, fontsize=9)


def draw_candles(ax, df) -> None:
    x = np.arange(len(df))
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    up = c >= o
    colors = np.where(up, UP_COLOR, DOWN_COLOR)
    rng = h.max() - l.min()
    ax.vlines(x, l, h, color=colors, linewidth=0.7)
    body_h = np.abs(c - o)
    body_h = np.where(body_h < rng * 1e-3, rng * 2e-3, body_h)
    for xi, bottom, bh, col in zip(x, np.minimum(o, c), body_h, colors):
        ax.add_patch(Rectangle((xi - 0.32, bottom), 0.64, bh, facecolor=col,
                               edgecolor=col, linewidth=0.3))
    for w in (5, 20, 60):
        ax.plot(x, df[f"MA{w}"], linewidth=1.1, color=MA_COLORS[f"MA{w}"], label=f"MA{w}")
    ax.legend(loc="upper left", fontsize=9, ncol=3)
    ax.grid(linestyle="--", alpha=0.3)


def draw_volume(ax, df) -> None:
    x = np.arange(len(df))
    up = df["close"].to_numpy() >= df["open"].to_numpy()
    colors = np.where(up, UP_COLOR, DOWN_COLOR)
    ax.bar(x, df["volume"] / 1e4, width=0.64, color=colors)
    ax.set_ylabel("成交量\n(万股)", fontsize=9)
    ax.grid(axis="y", linestyle="--", alpha=0.3)


def draw_macd(ax, df) -> None:
    x = np.arange(len(df))
    ax.bar(x, df["MACD"], width=0.64,
           color=np.where(df["MACD"] >= 0, UP_COLOR, DOWN_COLOR))
    ax.plot(x, df["DIF"], linewidth=1.1, color="#99F", label="DIF")
    ax.plot(x, df["DEA"], linewidth=1.1, color="#FC3", label="DEA")
    ax.axhline(0, color="#888", linewidth=0.8)
    ax.legend(loc="upper left", fontsize=9, ncol=2)
    ax.set_ylabel("MACD", fontsize=9)
    ax.grid(linestyle="--", alpha=0.3)


def draw_rsi(ax, df) -> None:
    x = np.arange(len(df))
    ax.plot(x, df["RSI"], linewidth=1.2, color="#99F")
    ax.axhline(70, color=UP_COLOR, linewidth=0.8, linestyle="--")
    ax.axhline(30, color=DOWN_COLOR, linewidth=0.8, linestyle="--")
    ax.set_ylim(0, 100)
    ax.set_ylabel("RSI(14)", fontsize=9)
    ax.grid(linestyle="--", alpha=0.3)


def main() -> None:
    code = sys.argv[1].strip() if len(sys.argv) > 1 else DEFAULT_CODE
    days = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_DAYS

    df = add_indicators(fetch_daily(code, days))
    name = ""
    try:
        info = ak.stock_individual_info_em(symbol=code)
        name = str(info.loc[info["item"] == "股票简称", "value"].iloc[0])
    except Exception:  # noqa: BLE001
        pass
    label = f"{code} {name}".strip()

    fig, axes = plt.subplots(
        4, 1, figsize=(14, 12), sharex=True,
        gridspec_kw={"height_ratios": [3.2, 1.0, 1.4, 1.0]},
    )
    # hspace 不能写进 gridspec_kw：matplotlib 3.11 会判定 Axes 与 tight_layout
    # 不兼容并静默跳过布局，导致 suptitle 与子图间留出大片空白，因此在 Figure 层设置
    fig.subplots_adjust(hspace=0.06)
    draw_candles(axes[0], df)
    draw_volume(axes[1], df)
    draw_macd(axes[2], df)
    draw_rsi(axes[3], df)
    _xticks(axes[3], df["date"].tolist())

    last = df.iloc[-1]
    prev = df.iloc[-2]
    axes[0].set_title(
        f"{label} 技术面（{df['date'].iloc[0]} ~ {df['date'].iloc[-1]}）", fontsize=13, pad=8,
    )
    fig.suptitle(
        f"{label} 日K/均线/成交量/MACD/RSI　最新收盘 {last['close']:.2f} "
        f"（{(last['close']/prev['close']-1)*100:+.2f}%）　来源：OMMQ",
        fontsize=16, fontweight="bold", y=0.995,
    )
    fig.tight_layout()

    out = report_image_path(10, code)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"图表已保存: {out}")
    print(f"\n最新交易日 {last['date']}")
    print(f"  收盘 {last['close']:.2f}  MA5 {last['MA5']:.2f}  MA20 {last['MA20']:.2f}  MA60 {last['MA60']:.2f}")
    print(f"  MACD DIF {last['DIF']:.3f}  DEA {last['DEA']:.3f}  柱 {last['MACD']:.3f}  RSI {last['RSI']:.1f}")

if __name__ == "__main__":
    main()
