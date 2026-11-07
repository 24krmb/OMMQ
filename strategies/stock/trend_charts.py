#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
近三年“费半”、“七姐妹”走势对比图 · akshare 一键生成脚本
====================================================================
输出 4 张 300DPI 白底归一化对比图(起点=100),配色遵循项目 OMMQ 规范
(红 #F36 / 绿 #0C9 / 蓝 #99F / 黄 #FC3,字体色 #27254c,来源标注 OMMQ):
  1. 美股七巨头:苹果 / 英伟达 / 微软 / 亚马逊 / 谷歌-A / Meta / 特斯拉(前复权)
  2. 费城半导体指数(SOX,圈内简称"费半")
  3. 创业板指 vs 纳斯达克综合指数
  4. 沪深300 vs 标普500

用法:
  python strategies/stock/trend_charts.py
  本脚本在 akshare 1.20.35 / Python 3.12 实测通过):

输出:
  reports/YYYYMMDD/17_美股七巨头.png
  reports/YYYYMMDD/18_费半SOX.png
  reports/YYYYMMDD/19_创业板指vs纳指.png
  reports/YYYYMMDD/20_沪深300vs标普500.png
  (编号规则见 strategies/stock/plot_paths.py,01–16 已被现有脚本占用)

数据源(自动重试 + 自动降级):
  美股个股:东方财富 stock_us_hist(前复权) → 失败自动切新浪 stock_us_daily(前复权)
  美股指数:新浪 index_us_stock_sina(.SOX 费半 / .IXIC 纳指 / .INX 标普500)
  A股指数:东方财富 index_zh_a_hist → 失败自动切新浪 stock_zh_index_daily

可选环境变量:
  AK_PREFER_SINA=1   跳过东方财富，直接使用新浪数据源(东财限流时使用)
"""

import os
import sys
import time

import pandas as pd

from plot_paths import report_dir, report_image_path

try:
    import akshare as ak
except ImportError:
    raise SystemExit("未检测到 akshare，请先执行:pip install akshare")

import matplotlib

# 无显示环境(SSH/服务器)自动切换无界面后端
if not sys.platform.startswith(("win", "darwin")) and not os.environ.get("DISPLAY"):
    matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

# ==================== 可按需修改的配置 ====================
YEARS = 3            # 统计近几年
ADJUST = "qfq"       # 美股复权方式:qfq 前复权 / "" 不复权 / hfq 后复权
FIG_SIZE = (14, 7.5) # 画布尺寸(英寸)
DPI = 300            # 输出分辨率
RETRY_TIMES = 3      # 单接口重试次数
RETRY_PAUSE = 4      # 重试基础间隔(秒，逐次加倍)

PREFER_SINA = os.environ.get("AK_PREFER_SINA", "0") == "1"

# ==================== 项目统一配色(24K-Claw) ====================
TEXT = "#27254c"      # 标题 / 副标题 / 轴标签 / 刻度 / 图例
MUTED = "#27254c"     # 脚注(同字体色)
SPINE = "#bbb"        # 坐标轴 / 基准线
UP = "#F36"           # 红(涨 / A股)
DOWN = "#0C9"         # 绿(跌)
BLUE = "#99F"         # 蓝(海外 / 基准)
YELLOW = "#FC3"       # 黄
# 七巨头:4 个主色 + 3 个同色系加深变体
PALETTE_7 = [UP, BLUE, YELLOW, DOWN, "#A61E4D", "#4C4CC2", "#008A66"]
US_STOCKS = [
    ("苹果",     "105.AAPL",  "AAPL"),
    ("英伟达",   "105.NVDA",  "NVDA"),
    ("微软",     "105.MSFT",  "MSFT"),
    ("亚马逊",   "105.AMZN",  "AMZN"),
    ("谷歌-A",   "105.GOOGL", "GOOGL"),
    ("Meta",     "105.META",  "META"),
    ("特斯拉",   "105.TSLA",  "TSLA"),
]
# 按标的锁定颜色:个别标的取数失败时,其余线条颜色不会漂移
STOCK_COLORS = {f"{name} {ticker}": color
                for (name, _em, ticker), color in zip(US_STOCKS, PALETTE_7)}

plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", "Noto Sans SC",
    "Source Han Sans CN", "SimHei", "WenQuanYi Micro Hei", "Arial Unicode MS", "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["font.size"] = 11.5
plt.rcParams["text.color"] = TEXT
plt.rcParams["axes.labelcolor"] = TEXT
plt.rcParams["axes.titlecolor"] = TEXT
plt.rcParams["xtick.color"] = TEXT
plt.rcParams["ytick.color"] = TEXT
SUMMARY = []  # 汇总:(组名, 标的, 交易日数, 组内区间涨跌幅%, 数据源)
def _retry(fn, what):
    """带重试的接口调用，重试间隔逐次加倍"""
    last = None
    for i in range(RETRY_TIMES):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"    · {what} 第 {i + 1} 次尝试失败:{type(e).__name__}")
            time.sleep(RETRY_PAUSE * (i + 1))
    raise last

def _to_series(dates, closes):
    """任意日期/收盘列 → 干净的以日期为索引的 Series"""
    s = pd.Series(pd.to_numeric(pd.Series(closes), errors="coerce").values,
                  index=pd.to_datetime(pd.Series(dates)))
    s = s.dropna()
    return s[~s.index.duplicated(keep="last")].sort_index()

def fetch_us_stock(name, em_symbol, sina_symbol, start, end):
    """美股个股(前复权):东方财富 → 新浪 自动降级"""
    if not PREFER_SINA:
        try:
            df = _retry(lambda: ak.stock_us_hist(
                symbol=em_symbol, period="daily",
                start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"),
                adjust=ADJUST), f"{name}[东财]")
            if df is not None and len(df) > 10:
                return _to_series(df["日期"], df["收盘"]), "东方财富·前复权"
        except Exception as e:  # noqa: BLE001
            print(f"    · {name} 东方财富不可用({type(e).__name__})，自动切换新浪源")
    df = _retry(lambda: ak.stock_us_daily(symbol=sina_symbol, adjust=ADJUST), f"{name}[新浪]")
    s = _to_series(df["date"], df["close"]).loc[start:end]
    if s.empty:
        raise ValueError("区间内无数据")
    return s, "新浪财经·前复权"


def fetch_us_index(sina_symbol, start, end):
    """美股指数(新浪):.SOX / .IXIC / .INX / .NDX"""
    df = _retry(lambda: ak.index_us_stock_sina(symbol=sina_symbol), f"美股指数{sina_symbol}")
    s = _to_series(df["date"], df["close"]).loc[start:end]
    if s.empty:
        raise ValueError("区间内无数据")
    return s, "新浪财经"


def fetch_cn_index(code, sina_symbol, start, end):
    """A股指数:东方财富 → 新浪 自动降级"""
    if not PREFER_SINA:
        try:
            df = _retry(lambda: ak.index_zh_a_hist(
                symbol=code, period="daily",
                start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d")),
                f"{code}[东财]")
            if df is not None and len(df) > 10:
                return _to_series(df["日期"], df["收盘"]), "东方财富"
        except Exception as e:  # noqa: BLE001
            print(f"    · {code} 东方财富不可用({type(e).__name__})，自动切换新浪源")
    df = _retry(lambda: ak.stock_zh_index_daily(symbol=sina_symbol), f"{code}[新浪]")
    s = _to_series(df["date"], df["close"]).loc[start:end]
    if s.empty:
        raise ValueError("区间内无数据")
    return s, "新浪财经"

def normalize(raw_map, start, end):
    """裁剪到统计区间 → 组内对齐至最晚的共同起始交易日 → 归一化(起点=100)"""
    trimmed = {k: s.loc[start:end].dropna() for k, s in raw_map.items()}
    common_start = max(s.index[0] for s in trimmed.values())
    return {k: (s.loc[common_start:] / s.loc[common_start:].iloc[0] * 100.0)
            for k, s in trimmed.items()}

def _style_axes(ax):
    ax.set_facecolor("white")
    ax.set_axisbelow(True)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(SPINE)
    ax.tick_params(labelsize=10.5, colors=TEXT, length=3)
    ax.tick_params(which="minor", length=2, colors=SPINE)
    ax.margins(x=0.015, y=0.08)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=(1, 4, 7, 10)))
    ax.set_ylabel("归一化净值(起点 = 100)", fontsize=11.5, color=TEXT)

def _add_legend(fig, ax, n_items):
    """图例置于绘图区右侧外部，保证零遮挡"""
    handles, labels = ax.get_legend_handles_labels()
    ver = tuple(int(x) for x in matplotlib.__version__.split(".")[:2])
    if ver >= (3, 7):  # constrained_layout 自动为图例留白
        fig.legend(handles, labels, loc="outside upper right",
                   frameon=False, fontsize=11, handlelength=1.8,
                   borderaxespad=0.4, alignment="left")
    else:  # 旧版 matplotlib:手动留出右侧空间
        ax.legend(handles, labels, loc="upper left", bbox_to_anchor=(1.02, 1),
                  frameon=False, fontsize=11, handlelength=1.8)
        fig.subplots_adjust(right=max(0.70, 1 - 0.155 * (n_items > 2)))

def plot_group(main_title, sub_title, data, colors, out, footer):
    fig, ax = plt.subplots(figsize=FIG_SIZE, constrained_layout=True)
    for label, s in data.items():
        color = colors[label]
        ret = s.iloc[-1] / s.iloc[0] - 1.0
        ax.plot(s.index, s.values, lw=2.0, color=color,
                label=f"{label}  {ret:+.1%}", solid_capstyle="round")
        if len(data) == 1:  # 单标的图加淡色面积填充，增强可读性
            ax.fill_between(s.index, 100.0, s.values, color=color, alpha=0.08, lw=0)
    ax.axhline(100, color=SPINE, lw=0.8, ls="--")

    _style_axes(ax)
    fig.suptitle(main_title, fontsize=17, fontweight="bold", color=TEXT)
    ax.set_title(sub_title, fontsize=11, color=TEXT, pad=12)
    _add_legend(fig, ax, len(data))
    # 脚注用 xlabel 承载:constrained_layout 会自动为其留白，避免与 x 轴刻度文字重叠
    ax.set_xlabel(footer, fontsize=9, color=MUTED, labelpad=10, loc="left")

    fig.savefig(out, dpi=DPI, facecolor="white")
    plt.close(fig)
    print(f"  [OK] 已保存:{out}")

def build_subtitle(kind, raw, norm):
    """按组类型组装带结论的副标题"""
    if kind == "giants":
        rets = {k: v.iloc[-1] / v.iloc[0] - 1.0 for k, v in norm.items()}
        best, worst = max(rets, key=rets.get), min(rets, key=rets.get)
        return (f"前复权收盘价归一化(起点=100)· 期间最强:{best} {rets[best]:+.1%}　"
                f"最弱:{worst} {rets[worst]:+.1%}")
    if kind == "single":
        s = list(raw.values())[0]
        n = list(norm.values())[0]
        return (f"归一化(起点=100)· 期初 {s.iloc[0]:,.0f} 点 → 最新 {s.iloc[-1]:,.0f} 点，"
                f"累计 {n.iloc[-1] - 100:+.1f}%")
    if kind == "growth":
        return "收盘价归一化(起点=100)· 中美成长板块对比"
    return "收盘价归一化(起点=100)· 中美大盘核心资产对比"

def main():
    end = pd.Timestamp.today().normalize()
    start = end - pd.DateOffset(years=YEARS)
    print(f"统计区间:{start:%Y-%m-%d} ~ {end:%Y-%m-%d}(近 {YEARS} 年)")
    print(f"数据源:{'新浪财经(AK_PREFER_SINA=1)' if PREFER_SINA else '东方财富优先，失败自动切换新浪'}")
    footer = "来源：OMMQ"

    # 组定义:kind 用于副标题,no/aux 为 reports/YYYYMMDD/ 下的编号与文件名后缀
    groups = [
        dict(kind="giants", colors=STOCK_COLORS, no=17, aux="美股七巨头",
             title="美股七巨头近三年走势对比",
             items=[(f"{name} {ticker}", lambda n=name, e=em, t=ticker: fetch_us_stock(n, e, t, start, end))
                    for name, em, ticker in US_STOCKS]),
        dict(kind="single", colors={"费城半导体指数": BLUE}, no=18, aux="费半SOX",
             title="费城半导体指数(SOX)近三年走势",
             items=[("费城半导体指数", lambda: fetch_us_index(".SOX", start, end))]),
        dict(kind="growth", colors={"创业板指": UP, "纳斯达克综合指数": BLUE},
             no=19, aux="创业板指vs纳指",
             title="创业板指 vs 纳斯达克综合指数:近三年走势对比",
             items=[("创业板指", lambda: fetch_cn_index("399006", "sz399006", start, end)),
                    ("纳斯达克综合指数", lambda: fetch_us_index(".IXIC", start, end))]),
        dict(kind="core", colors={"沪深300": UP, "标普500": BLUE},
             no=20, aux="沪深300vs标普500",
             title="沪深300 vs 标普500:近三年走势对比",
             items=[("沪深300", lambda: fetch_cn_index("000300", "sh000300", start, end)),
                    ("标普500", lambda: fetch_us_index(".INX", start, end))]),
    ]

    failed = []
    for gi, g in enumerate(groups, 1):
        print(f"\n== 第 {gi} 组:{g['title']}")
        raw = {}
        days, srcs = {}, {}
        for label, fetcher in g["items"]:
            try:
                s, src = fetcher()
                if len(s) < 60:
                    raise ValueError(f"有效数据过少({len(s)} 行)")
                raw[label] = s
                days[label], srcs[label] = len(s), src
                print(f"  [OK] {label}:{s.index[0]:%Y-%m-%d} ~ {s.index[-1]:%Y-%m-%d}"
                      f"({len(s)} 个交易日，{src})")
            except Exception as e:  # noqa: BLE001
                print(f"  [失败] {label} 获取失败:{e}")
                failed.append(f"{g['title']} · {label}")
        if not raw:
            print("  该组数据全部获取失败，跳过出图")
            continue
        norm = normalize(raw, start, end)
        for label, s in norm.items():
            SUMMARY.append((g["title"], label, days[label], s.iloc[-1] - 100.0, srcs[label]))
        out = report_image_path(g["no"], g["aux"])
        plot_group(g["title"], build_subtitle(g["kind"], raw, norm),
                   norm, g["colors"], out, footer)

    # ---- 汇总 ----
    print("\n" + "=" * 72)
    print("区间涨跌幅汇总(组内归一化口径，与图例一致)")
    for title, label, n, ret, src in SUMMARY:
        print(f"  {title} | {label:<12} | {n:>5} 个交易日 | {ret:+7.1f}% | {src}")
    if failed:
        print("\n[注意] 以下标的获取失败(不影响其余图表):")
        for f in failed:
            print(f"  - {f}")
        print("提示:东财限流时可在等待 5~40 分钟后重跑，或设置环境变量 AK_PREFER_SINA=1 直接使用新浪源。")
    print(f"\n全部图片输出目录:{report_dir()}")


if __name__ == "__main__":
    main()
