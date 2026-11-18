#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全球主要股指近60个交易日累计收益率对比图
=========================================
指数范围 : 标普500 / 道琼斯 / 纳斯达克100 / 日经225 / 恒生指数 / 沪深300
           德国DAX40 / 富时100 / 法国CAC40 / MSCI新兴市场
对齐口径 : 全球公共交易日对齐——取所有指数共同有行情的最近 60 个交易日，
           各指数统一在区间首日归一化为 0%，起点一致、可直接对比。
用法     : python plot_global_indices_60d.py
输出     : reports/YYYYMMDD/16_global_index_60d.png(编号遵循 strategies/plot_paths.py)
依赖     : akshare>=1.20  pandas  matplotlib  requests
"""

import os
import sys
import time
import warnings
from datetime import datetime
warnings.filterwarnings("ignore")
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # 只出图不弹窗；如需交互窗口可注释本行
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
from matplotlib import font_manager
import akshare as ak
# 产物统一落盘 reports/<当天日期>/,复用仓库统一编号规则
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from plot_paths import report_image_path

# ════════════════════════ 可调参数 ════════════════════════
N_DAYS        = 60          # 公共交易日窗口长度
WINDOW_ROWS   = 140         # 每个指数取最近140个交易日参与公共日求交集
OUT_NO        = 16          # 扩展图编号(09 起),见 strategies/plot_paths.py
OUT_AUX       = "global_index_60d"
COLOR_MODE    = "classic"   # "classic"=经典多色；"sign"=红涨绿跌按盈亏着色
EM_CALL_PAUSE = 1.0
# ══════════════════════════════════════════════════════════
TEXT_C   = "#27254c"
TEXT_SOFT = "#73718b"
POS_C    = "#F36"
NEG_C    = "#0C9" 
CLASSIC_PALETTE = ["#F36", "#0C9", "#99F", "#FC3",
                   "#9D2D5B", "#108679", "#6969B4", "#A48628",
                   "#F38FAB", "#73E3C7"]
WARM_FAMILY  = ["#F36", "#FC3", "#9D2D5B", "#A48628", "#F38FAB"]
COOL_FAMILY  = ["#0C9", "#99F", "#108679", "#6969B4", "#73E3C7"]

# ─── 指数清单 依次降级尝试 ───
INDEXES = [
    ("标普500",
     [("东财", lambda: em_global("标普500")),
      ("新浪", lambda: sina_us(".INX"))]),
    ("道琼斯",
     [("东财", lambda: em_global("道琼斯")),
      ("新浪", lambda: sina_us(".DJI"))]),
    ("纳斯达克100",
     [("新浪", lambda: sina_us(".NDX")),
      ("东财", lambda: em_global("纳斯达克"))]),
    ("日经225",
     [("东财", lambda: em_global("日经225")),
      ("新浪", lambda: sina_global("日经225指数"))]),
    ("恒生指数",
     [("东财", lambda: em_global("恒生指数")),
      ("新浪", lambda: sina_hk("HSI"))]),
    ("沪深300",
     [("东财", lambda: em_global("沪深300")),
      ("新浪", lambda: sina_a("sh000300"))]),
    ("德国DAX40",
     [("东财", lambda: em_global("德国DAX30")),
      ("新浪", lambda: sina_global("德国DAX 30种股价指数"))]),
    ("富时100",
     [("东财", lambda: em_global("英国富时100")),
      ("新浪", lambda: sina_global("英国富时100指数"))]),
    ("法国CAC40",
     [("东财", lambda: em_global("法国CAC40")),
      ("新浪", lambda: sina_global("法CAC40指数"))]),
    ("MSCI新兴市场",
     [("雅虎", lambda: yahoo_chart("^MXEF")),
      ("新浪EEM代理", lambda: sina_eem())]), 
]

# ════════════════════════ 数据获取 ════════════════════════
def em_global(symbol: str) -> pd.Series:
    df = ak.index_global_hist_em(symbol=symbol)
    return _series(df["日期"], df["最新价"])
def sina_us(symbol: str) -> pd.Series:
    df = ak.index_us_daily_sina(symbol=symbol)
    return _series(df["date"], df["close"])
def sina_global(name: str) -> pd.Series:
    df = ak.index_global_hist_sina(symbol=name)
    return _series(df["date"], df["close"])
def sina_hk(symbol: str) -> pd.Series:
    df = ak.index_hk_daily_sina(symbol=symbol)
    return _series(df["date"], df["close"])
def sina_a(symbol: str) -> pd.Series:
    df = ak.index_zh_daily_sina(symbol=symbol)
    return _series(df["date"], df["close"])
def sina_eem() -> pd.Series:
    df = ak.stock_us_hist_sina(symbol="EEM", period="daily")
    return _series(df["date"], df["close"])
def yahoo_chart(ticker: str) -> pd.Series:
    import requests
    last_err = None
    for host in ("query1", "query2"):
        try:
            url = f"https://{host}.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(ticker)}"
            r = requests.get(url, params={"range": "6mo", "interval": "1d"},
                             headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            res = r.json()["chart"]["result"][0]
            ts = res["timestamp"]
            closes = res["indicators"]["quote"][0]["close"]
            idx = pd.to_datetime(ts, unit="s", utc=True).tz_convert(None)
            return _series(pd.Series(idx), pd.Series(closes))
        except Exception as e:
            last_err = e
    raise last_err


def _series(dates, closes) -> pd.Series:
    s = pd.Series(pd.to_numeric(pd.Series(closes), errors="coerce").values,
                  index=pd.to_datetime(pd.Series(dates), errors="coerce"))
    s.index = s.index.normalize()
    s = s.replace([float("inf"), float("-inf")], pd.NA).dropna()
    s = s[s > 0]
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s.astype(float)

def fetch_index(label: str, steps) -> tuple:
    last_err = None
    for desc, fn in steps:
        for attempt in range(2):
            try:
                s = fn()
                if len(s) >= N_DAYS + 10:
                    return s.tail(WINDOW_ROWS), desc
                raise ValueError(f"返回数据不足({len(s)}行)")
            except Exception as e:
                last_err = e
                if attempt == 0:
                    time.sleep(2)
        print(f"  [降级] {label} <- {desc} 失败: {type(last_err).__name__}: {str(last_err)[:70]}")
    print(f"  [失败] {label}: 全部来源均不可用，本图将不含该指数")
    return None, ""
# ════════════════════════ 中文字体(跨平台) ════════════════════════
def setup_font():
    preferred = ["Microsoft YaHei", "SimHei", "PingFang SC", "Hiragino Sans GB",
                 "Noto Sans CJK SC", "Source Han Sans SC", "Source Han Sans CN",
                 "WenQuanYi Micro Hei", "WenQuanYi Zen Hei", "Arial Unicode MS"]
    installed = {f.name for f in font_manager.fontManager.ttflist}
    chosen = [n for n in preferred if n in installed]
    if not chosen:  # 常见字体文件路径兜底注册
        for path in ("/usr/share/fonts/truetype/chinese/NotoSansSC-Regular.ttf",
                     "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                     "C:/Windows/Fonts/msyh.ttc",
                     "/System/Library/Fonts/PingFang.ttc"):
            try:
                if os.path.exists(path):
                    font_manager.fontManager.addfont(path)
                    chosen = [font_manager.FontProperties(fname=path).get_name()]
                    break
            except Exception:                                 # noqa: BLE001
                pass
    if chosen:
        plt.rcParams["font.sans-serif"] = chosen + ["DejaVu Sans"]
    else:
        print("警告: 未找到中文字体，图中中文可能显示为方块(可安装微软雅黑/思源黑体后重试)")
    plt.rcParams["axes.unicode_minus"] = False

# ════════════════════════ 绘图 ════════════════════════
def plot(cur: dict, sources: dict, failed: list):
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
    ax.set_xlabel("交易日(全球公共交易日对齐)")

    order = sorted(names, key=lambda n: finals[n], reverse=True)
    from matplotlib.lines import Line2D
    handles, labels, lab_colors = [], [], []
    for n in order:
        handles.append(Line2D([0], [0], color=colors[n], lw=2.2))
        labels.append(f"{n}({finals[n]:+.2f}%)")
        lab_colors.append(POS_C if finals[n] >= 0 else NEG_C)
    leg = ax.legend(handles, labels, loc="upper left", bbox_to_anchor=(1.02, 1.0),
                    handlelength=1.6, labelspacing=0.9, borderaxespad=0)
    for t, c in zip(leg.get_texts(), lab_colors):
        t.set_color(c)

    if best_val >= 0:
        head = f"近60个交易日全球主要股指累计收益：{best_name}领涨({best_val:+.2f}%)"
    else:
        head = f"近60个交易日全球主要股指普遍回调：{best_name}相对抗跌({best_val:+.2f}%)"
    # ── 标题与来源标注(一律标注 OMMQ)：来源与标题同字号同行，接在标题之后 ──
    fig.suptitle(f"{head}　数据来源：OMMQ",
                 fontsize=17, fontweight="bold", color=TEXT_C, x=0.01, ha="left")
    d0, d1 = dates[0], dates[-1]
    msci_note = "，MSCI新兴市场取EEM ETF价格近似" if sources.get("MSCI新兴市场", "").startswith("新浪EEM") else ""
    note = (f"区间 {d0:%Y-%m-%d} 至 {d1:%Y-%m-%d}"
            f"｜60个全球公共交易日，起点统一归一化为0%{msci_note}")
    if failed:  # 取数缺失提示较长，放在标题下方说明行，避免撑破标题行
        note += "｜未获取到: " + "、".join(failed)
    ax.set_title(note, fontsize=10.5, color=TEXT_SOFT, loc="left", pad=12)

    out = report_image_path(OUT_NO, OUT_AUX)
    fig.savefig(out, dpi=200, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    print(f"已保存: {out}")
    return out

def main():
    print(f"akshare {ak.__version__} ｜ 窗口: 最近{N_DAYS}个全球公共交易日(公共日对齐)")
    setup_font()
    closes, sources, failed = {}, {}, []
    for label, steps in INDEXES:
        s, src = fetch_index(label, steps)
        if s is None:
            failed.append(label)
        else:
            closes[label] = s
            sources[label] = src
            print(f"  [取数] {label} <- {src}({len(s)}个交易日，最新 {s.index[-1]:%Y-%m-%d})")
        time.sleep(EM_CALL_PAUSE)
    if len(closes) < 2:
        raise SystemExit("可用指数不足2个，请检查网络或数据源后重试")
    # ── 公共交易日求交集，取最近N_DAYS天 ──
    common = None
    for s in closes.values():
        common = set(s.index) if common is None else (common & set(s.index))
    common = sorted(common)[-N_DAYS:]
    if len(common) < N_DAYS:
        print(f"警告: 公共交易日仅{len(common)}个(不足{N_DAYS})，将按实际天数绘制")
    print(f"  [窗口] {common[0]:%Y-%m-%d} ~ {common[-1]:%Y-%m-%d} 共{len(common)}个公共交易日")
    cur = {"__dates__": pd.DatetimeIndex(common)}
    for label, s in closes.items():
        sub = s.reindex(common)
        cur[label] = (sub / sub.iloc[0] - 1) * 100
    plot(cur, sources, failed)
if __name__ == "__main__":
    main()
