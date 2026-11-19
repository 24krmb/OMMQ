# -*- coding: utf-8 -*-

r"""MSCI ACWI 与富时 All-World 近60个交易日累计收益对比
内容:
    主图:两大全球全市场指数近 N(默认60)个交易日累计收益曲线,区间首日统一归一化为 0%
    附图:两者累计收益之差(ACWI - VT),正值=ACWI 跑赢,负值=落后
口径:两只 ETF 均以美元计价、美国收盘定价,
      交易日与估值时点一致,不存在跨时区快照错位;两序列取公共交易日交集后对齐
用法:.\.venv\Scripts\python.exe strategies/global/plot_acwi_ftseaw_60d.py [交易日数]
      (交易日数默认60;复用上游取数链单次最多返回140个交易日,超出则按140天绘制并提示)
输出:reports/YYYYMMDD/28_acwi_ftseaw_60d.png(编号规则见 strategies/plot_paths.py)
依赖:akshare>=1.20  pandas  matplotlib  requests
"""

from __future__ import annotations
import os
import sys
import warnings
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import requests
warnings.filterwarnings("ignore")
# 复用仓库共享模块
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, os.path.join(_ROOT, "strategies"), _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from plot_global_indices_60d import _series, fetch_index, setup_font
from plot_paths import report_image_path
from plot_utils import DOWN_COLOR, UP_COLOR

# ════════════════════════ 可调参数 ════════════════════════
N_DAYS_DEFAULT = 60            # 交易日窗口长度(可用命令行参数覆盖)
OUT_NO         = 28            # 扩展图编号(09 起),见 strategies/plot_paths.py;17–20 属 trend_charts.py
OUT_AUX        = "acwi_ftseaw_60d"
SA_URL         = "https://api.stockanalysis.com/api/symbol/e/{sym}/history"
TEXT_C   = "#27254c"
TEXT_SOFT = "#73718b"
GRID_C   = "#C9C9D6"
SERIES = {                     # 图例名 -> (代理代码, 代理说明, 线色)
    "MSCI ACWI": ("ACWI", "iShares MSCI ACWI ETF", "#99F"),
    "VT(富时全球小型股)": ("VT", "Vanguard Total World ETF,基准含小盘", "#FC3"),
}
# ══════════════════════════════════════════════════════════
def sina_etf(symbol: str) -> pd.Series:
    import akshare as ak
    df = ak.stock_us_hist_sina(symbol=symbol, period="daily")
    return _series(df["date"], df["close"])
def stockanalysis(symbol: str, rng: str = "5Y") -> pd.Series:
    r = requests.get(SA_URL.format(sym=symbol), params={"range": rng},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    r.raise_for_status()
    rows = r.json().get("data") or []
    if not rows:
        raise ValueError(f"{symbol} 返回空数据")
    dates = [row["t"] for row in rows]
    closes = [row["c"] for row in rows]
    return _series(dates, closes)

def steps_for(symbol: str) -> list:
    return [("新浪", lambda s=symbol: sina_etf(s)),
            ("StockAnalysis", lambda s=symbol: stockanalysis(s))]

def mdd(cum: pd.Series) -> tuple[float, pd.Timestamp]:
    dd = cum - cum.cummax()
    return float(dd.min()), dd.idxmin()

def plot(cur: dict[str, pd.Series], span: pd.Series | None) -> str:
    dates = next(iter(cur.values())).index
    finals = {n: float(s.iloc[-1]) for n, s in cur.items()}
    names = list(cur)
    plt.rcParams.update({
        "figure.facecolor": "#FFFFFF", "axes.facecolor": "#FFFFFF",
        "axes.edgecolor": GRID_C, "axes.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False,
        "xtick.color": TEXT_SOFT, "ytick.color": TEXT_SOFT,
        "xtick.labelsize": 9.5, "ytick.labelsize": 10,
        "axes.labelcolor": TEXT_C, "axes.labelsize": 11,
        "text.color": TEXT_C, "legend.frameon": False, "legend.fontsize": 10,
        "savefig.facecolor": "#FFFFFF",
    })
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(13, 8.6), sharex=True,
        gridspec_kw={"height_ratios": [2.4, 1], "hspace": 0.12},
    )
    fig.subplots_adjust(left=0.055, right=0.995)
    hi = max(float(s.max()) for s in cur.values())
    lo = min(float(s.min()) for s in cur.values())
    pad = (hi - lo) * 0.14 or 0.5
    ax1.axhline(0, color=TEXT_C, lw=1, ls=(0, (4, 4)), alpha=0.35, zorder=2)
    ranked = sorted(names, key=lambda n: finals[n])
    too_close = len(ranked) == 2 and (finals[ranked[1]] - finals[ranked[0]]) < (hi - lo) * 0.25
    for n in names:
        s = cur[n]
        ax1.plot(s.index, s.values, color=SERIES[n][2], lw=2.2,
                 solid_capstyle="round", zorder=3,
                 label=f"{n} {finals[n]:+.2f}%")
        ax1.scatter([s.index[-1]], [finals[n]], s=26, color=SERIES[n][2], zorder=4)
        dy = 8 if (not too_close or n == ranked[-1]) else -16
        ax1.annotate(f"{finals[n]:+.2f}%", xy=(s.index[-1], finals[n]), xytext=(9, dy),
                     textcoords="offset points", fontsize=11, fontweight="bold",
                     color=SERIES[n][2])
    ax1.set_ylim(lo - pad, hi + pad)
    ax1.set_ylabel("累计收益(%)")
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax1.grid(axis="y", ls="--", alpha=0.25, color=GRID_C)
    ax1.set_axisbelow(True)
    ax1.legend(loc="upper left")

    if span is None:
        ax2.set_yticks([])  # 无数据时不显示 0~1 的空刻度,避免误读
        ax2.text(0.5, 0.5, "收益差需两条序列均获取成功(本图不含附图)", ha="center",
                 va="center", fontsize=13, color=TEXT_SOFT, transform=ax2.transAxes)
        ax2.set_ylabel("收益差(pct)")
    else:
        last = float(span.iloc[-1])
        c_last = UP_COLOR if last >= 0 else DOWN_COLOR
        ax2.fill_between(span.index, 0, span.values, where=span.values >= 0,
                         color=UP_COLOR, alpha=0.12, interpolate=True, zorder=1)
        ax2.fill_between(span.index, 0, span.values, where=span.values < 0,
                         color=DOWN_COLOR, alpha=0.12, interpolate=True, zorder=1)
        ax2.plot(span.index, span.values, color=TEXT_C, lw=1.8,
                 solid_capstyle="round", zorder=3,
                 label=f"ACWI − VT {last:+.2f}pct")
        ax2.axhline(0, color=TEXT_C, lw=1, ls=(0, (4, 4)), alpha=0.35, zorder=2)
        ax2.annotate(f"{last:+.2f}", xy=(span.index[-1], last), xytext=(9, 4),
                     textcoords="offset points", fontsize=11, fontweight="bold",
                     color=c_last)
        ax2.set_ylabel("收益差(pct)")
        ax2.grid(axis="y", ls="--", alpha=0.25, color=GRID_C)
        ax2.set_axisbelow(True)
        ax2.legend(loc="upper left")
        s_lo, s_hi = float(span.min()), float(span.max())
        s_pad = (s_hi - s_lo) * 0.22 or 0.3
        ax2.set_ylim(min(s_lo, 0.0) - s_pad, max(s_hi, 0.0) + s_pad)

    ax2.xaxis.set_major_locator(mdates.DayLocator(interval=6))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    span_days = (dates[-1] - dates[0]).days
    ax2.set_xlim(dates[0] - pd.Timedelta(days=2),
                 dates[-1] + pd.Timedelta(days=max(6, span_days * 0.03)))
    ax2.set_xlabel("交易日(两序列公共交易日对齐)")

    best = max(names, key=lambda n: finals[n])
    best_code = SERIES[best][0]  # 标题用代理代码简称,免得图例全名把标题撑爆
    if min(finals.values()) >= 0:
        tail = f"{best_code}领涨({finals[best]:+.2f}%)"
    elif max(finals.values()) < 0:
        tail = f"全球权益普遍回调,{best_code}相对抗跌({finals[best]:+.2f}%)"
    else:
        tail = f"{best_code}领先({finals[best]:+.2f}%)"
    fig.suptitle(f"MSCI ACWI 与富时All-World(ETF 代理) 近{len(dates)}个交易日累计收益"
                 f"　{tail}　来源：OMMQ",
                 fontsize=17, fontweight="bold", color=TEXT_C, x=0.01, ha="left")
    note = (f"区间 {dates[0]:%Y-%m-%d} 至 {dates[-1]:%Y-%m-%d}"
            f"｜起点统一归一化为0%,ETF 未复权收盘价即价格指数口径,不含分红"
            f"｜图例为代理代码:ACWI→MSCI ACWI,VT→富时全球小型股(All-World大中盘+小盘)")
    if len(names) < 2:
        note += "｜未获取到: " + "、".join(n for n in SERIES if n not in cur)
    ax1.set_title(note, fontsize=10.5, color=TEXT_SOFT, loc="left", pad=12)
    out = report_image_path(OUT_NO, OUT_AUX)
    fig.savefig(out, dpi=200, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    return out

def main() -> None:
    n_days = int(sys.argv[1]) if len(sys.argv) > 1 else N_DAYS_DEFAULT
    print(f"窗口: MSCI ACWI 与富时All-World 最近{n_days}个公共交易日累计收益(ETF 代理口径)")
    setup_font() 
    closes: dict[str, pd.Series] = {}
    for name, (code, proxy, _) in SERIES.items():
        s, src = fetch_index(name, steps_for(code))
        if s is None:
            continue
        if len(s) < n_days:
            print(f"  [警告] 上游仅返回{len(s)}个交易日,窗口按实际{len(s)}天绘制")
        closes[name] = s
        print(f"  [取数] {name} <- {code} via {src}({len(s)}个交易日，"
              f"最新 {s.index[-1]:%Y-%m-%d}，代理：{proxy})")

    if not closes:
        raise SystemExit("两条序列均不可用,请检查网络后重试(不编造数据)")

    # ── 公共交易日求交集,取最近 n_days 天 ──
    common = None
    for s in closes.values():
        common = set(s.index) if common is None else (common & set(s.index))
    common = pd.DatetimeIndex(sorted(common)[-n_days:])
    if len(common) < n_days:
        print(f"  [警告] 公共交易日仅{len(common)}个,按实际天数绘制")
    if len(common) < 2:
        raise SystemExit("公共交易日不足2个,无法计算累计收益(不编造数据)")
    cur = {n: (s.reindex(common) / s.reindex(common).iloc[0] - 1.0) * 100.0
           for n, s in closes.items()}
    pair = [cur[n] for n in SERIES if n in cur]
    span = pair[0] - pair[1] if len(pair) == 2 else None

    out = plot(cur, span)
    print(f"已保存: {out}")
    print(f"\n[区间] {common[0]:%Y-%m-%d} ~ {common[-1]:%Y-%m-%d}({len(common)}个公共交易日)")
    for n in cur:
        s = cur[n]
        vol = float(s.diff().std() * 252 ** 0.5)
        m, md = mdd(s)
        print(f"  {n} 累计 {s.iloc[-1]:+.2f}%  峰值 {s.max():+.2f}%"
              f"  谷值 {s.min():+.2f}%  最大回撤 {m:.2f}pct(谷 {md:%m-%d})  年化波动 {vol:.1f}%")
    if span is not None:
        lead, lag = float(span.max()), float(span.min())
        corr = float(pair[0].diff().corr(pair[1].diff()))
        print(f"[附图] ACWI − VT 期末 {span.iloc[-1]:+.2f}pct"
              f"  区间最大领先 {lead:+.2f}pct({span.idxmax():%m-%d})"
              f"  区间最大落后 {lag:+.2f}pct({span.idxmin():%m-%d})")
        print(f"  两者日收益相关系数 {corr:+.3f}(接近1=全球大盘股走势高度一致,"
              f"差值主要落在小盘敞口与费用/跟踪误差)")

if __name__ == "__main__":
    main()
