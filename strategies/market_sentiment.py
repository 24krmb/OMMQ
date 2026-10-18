# -*- coding: utf-8 -*-
"""A股市场情绪图：涨跌家数 / 涨跌停 / 连板梯队 / 涨停行业分布

内容（2×2）：
    1. 近 N 个交易日 涨停 / 跌停 家数趋势
    2. 当日 全市场 上涨 / 平盘 / 下跌 家数
    3. 当日 涨停梯队：按连板数统计家数分布（最高板标注）
    4. 当日 涨停个股 所属行业 TOP10

数据源：
    - 全市场涨跌家数：乐咕乐股 ak.stock_market_activity_legu
    - 涨停池 / 炸板池 / 跌停池：东方财富 ak.stock_zt_pool_em /
      stock_zt_pool_zbgc_em / stock_zt_pool_dtgc_em（push2ex 接口本机可用）
    - 涨停家数历史：按交易日逐日调用涨停池 / 跌停池
说明：东方财富 push2/push2his 资金流接口在本机被限流，故资金流类指标改由其他源提供；
      涨停/跌停池走 push2ex 接口，本机可正常返回。
输出：strategies/output/market_sentiment_<日期>.png
运行：uv run python strategies/market_sentiment.py [交易日数]   # 默认 15
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

warnings.filterwarnings("ignore")
matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
matplotlib.rcParams["axes.unicode_minus"] = False
# 统一配色 24K-Claw：红 #F36 / 绿 #0C9 / 蓝 #99F / 黄 #FC3；字体色 #27254c
matplotlib.rcParams["text.color"] = "#27254c"
matplotlib.rcParams["axes.labelcolor"] = "#27254c"
matplotlib.rcParams["axes.titlecolor"] = "#27254c"
matplotlib.rcParams["xtick.color"] = "#27254c"
matplotlib.rcParams["ytick.color"] = "#27254c"

OUT_DIR = "strategies/output"
HIST_N = 15          # 涨停/跌停家数趋势回溯交易日数
UP_COLOR = "#F36"   # 红涨
DOWN_COLOR = "#0C9"  # 绿跌
FLAT_COLOR = "#99F"  # 平盘


def latest_trade_date() -> dt.date:
    try:
        dates = ak.tool_trade_date_hist_sina()["trade_date"]
        today = dt.date.today()
        past = [d for d in dates if d <= today]
        return past[-1] if past else today
    except Exception:  # noqa: BLE001
        return dt.date.today()


def trade_dates(n: int) -> list[dt.date]:
    dates = ak.tool_trade_date_hist_sina()["trade_date"]
    today = dt.date.today()
    past = [d for d in dates if d <= today]
    return past[-n:] if past else []


def fetch_breadth() -> dict[str, object]:
    """乐咕乐股 全市场活跃度（上涨/平盘/下跌/涨停/跌停/真实涨跌停 家数）。"""
    df = ak.stock_market_activity_legu()
    out: dict[str, object] = {}
    for _, row in df.iterrows():
        key = str(row["item"]).strip()
        val = row["value"]
        try:
            out[key] = float(val)
        except (TypeError, ValueError):
            out[key] = str(val)
    return out


def fetch_pool(date: dt.date, kind: str) -> pd.DataFrame:
    """涨停池 / 炸板池 / 跌停池。kind in {zt, zb, dtgc}。"""
    d = date.strftime("%Y%m%d")
    if kind == "zt":
        return ak.stock_zt_pool_em(date=d)
    if kind == "zb":
        return ak.stock_zt_pool_zbgc_em(date=d)
    return ak.stock_zt_pool_dtgc_em(date=d)


def fetch_limit_history(n: int) -> tuple[list[dt.date], list[float], list[float]]:
    """近 n 个交易日 涨停 / 跌停 家数。"""
    dates, zts, dts = [], [], []
    for d in trade_dates(n):
        try:
            zt = fetch_pool(d, "zt")
            n_zt = len(zt)
        except Exception:  # noqa: BLE001
            continue
        try:
            n_dt = len(fetch_pool(d, "dtgc"))
        except Exception:  # noqa: BLE001
            n_dt = 0
        dates.append(d)
        zts.append(n_zt)
        dts.append(n_dt)
    return dates, zts, dts


def plot_limit_trend(ax, dates: list[dt.date], zts: list[float], dts: list[float]) -> None:
    x = list(range(len(dates)))
    ax.bar([i - 0.2 for i in x], zts, 0.4, label="涨停家数", color=UP_COLOR)
    ax.bar([i + 0.2 for i in x], dts, 0.4, label="跌停家数", color=DOWN_COLOR)
    ax.set_xticks(x)
    ax.set_xticklabels([d.strftime("%m-%d") for d in dates], rotation=45, fontsize=8)
    ax.set_ylabel("家数")
    ax.set_title(f"近 {len(dates)} 个交易日 涨停 / 跌停 家数", fontsize=13)
    ax.legend(fontsize=9)
    ax.grid(axis="y", linestyle="--", alpha=0.35)


def plot_breadth(ax, breadth: dict[str, object]) -> None:
    keys = ["上涨", "平盘", "下跌"]
    vals = [float(breadth.get(k, 0) or 0) for k in keys]
    bars = ax.bar(keys, vals, color=[UP_COLOR, FLAT_COLOR, DOWN_COLOR], width=0.6)
    ax.set_title("当日 全市场涨跌家数", fontsize=13)
    ax.set_ylabel("家数")
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{int(v)}", ha="center", va="bottom", fontsize=11)


def plot_ladder(ax, zt: pd.DataFrame) -> int:
    """涨停梯队：按连板数统计家数。"""
    if "连板数" not in zt.columns or zt.empty:
        ax.text(0.5, 0.5, "涨停池数据不可用", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("当日 涨停梯队（连板数分布）", fontsize=13)
        return 0
    lv = pd.to_numeric(zt["连板数"], errors="coerce").fillna(1).astype(int)
    max_lv = int(lv.max())
    levels = list(range(1, max_lv + 1))
    counts = [int((lv == k).sum()) for k in levels]
    colors = ["#F36"] * len(levels)
    colors[-1] = UP_COLOR
    bars = ax.bar([str(k) for k in levels], counts, color=colors, width=0.6)
    ax.set_xlabel("连板数（板）")
    ax.set_ylabel("家数")
    ax.set_title(f"当日 涨停梯队（最高 {max_lv} 板）", fontsize=13)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    for b, v in zip(bars, counts):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{int(v)}", ha="center", va="bottom", fontsize=10)
    return max_lv


def plot_industry(ax, zt: pd.DataFrame) -> None:
    if "所属行业" not in zt.columns or zt.empty:
        ax.text(0.5, 0.5, "涨停池数据不可用", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("当日 涨停个股 行业 TOP10", fontsize=13)
        return
    cnt = zt["所属行业"].astype(str).value_counts().head(10)
    d = cnt.sort_values()
    ax.barh(d.index, d.values, color=UP_COLOR)
    ax.set_xlabel("涨停家数")
    ax.set_title("当日 涨停个股 所属行业 TOP10", fontsize=13)
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    for y, v in enumerate(d.values):
        ax.text(v, y, f" {int(v)}", va="center", fontsize=10)


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else HIST_N
    date = latest_trade_date()

    breadth = fetch_breadth()
    try:
        zt = fetch_pool(date, "zt")
    except Exception as e:  # noqa: BLE001
        print(f"[警告] 涨停池获取失败: {type(e).__name__} {e}")
        zt = pd.DataFrame()
    try:
        zb_n = len(fetch_pool(date, "zb"))
    except Exception:  # noqa: BLE001
        zb_n = 0

    dates, zts, dts = fetch_limit_history(n)

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    plot_limit_trend(axes[0, 0], dates, zts, dts)
    plot_breadth(axes[0, 1], breadth)
    max_lv = plot_ladder(axes[1, 0], zt)
    plot_industry(axes[1, 1], zt)

    n_zt = len(zt)
    n_dt = int(float(breadth.get("跌停", 0) or 0))
    seal_rate = n_zt / (n_zt + zb_n) * 100 if (n_zt + zb_n) else 0.0
    stat = breadth.get("统计日期", "")
    fig.suptitle(
        f"A股市场情绪图（数据日期 {date}，活跃度统计 {stat}）｜"
        f"涨停 {n_zt} · 跌停 {n_dt} · 最高 {max_lv} 板 · 封板率 {seal_rate:.1f}%　来源：24K-Claw",
        fontsize=15, fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"market_sentiment_{date:%Y%m%d}.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"图表已保存: {out}")

    print(f"\n[市场情绪汇总] 涨停 {n_zt} · 跌停 {n_dt} · 炸板 {zb_n} · 最高 {max_lv} 板 · 封板率 {seal_rate:.1f}%")
    print("\n[涨跌家数]")
    for k in ["上涨", "平盘", "下跌", "涨停", "跌停", "真实涨停", "真实跌停", "停牌"]:
        if k in breadth:
            try:
                print(f"  {k:6s} {int(float(breadth[k] or 0))}")
            except (TypeError, ValueError):
                print(f"  {k:6s} {breadth[k]}")


if __name__ == "__main__":
    main()
