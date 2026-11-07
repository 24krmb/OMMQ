# -*- coding: utf-8 -*-
"""标普500 vs 沪深300:近5年累计收益与最大回撤对比
内容:
    复用 global_index_week_curve.py 的取数与累计收益逻辑(fetch_index_close / window_cum_return),
    在 5 年长窗口下重绘(x 轴按年刻度;日线脚本为短窗口逐日刻度,长窗口下不可用),并计算窗口内最大回撤:
        - 沪深300:ak.stock_zh_index_daily("sh000300")
        - 标普500:ak.index_us_stock_sina(".INX")
    口径说明:
        - 累计收益:基准 = 窗口前一交易日收盘(与 global_index_week_curve.py 同口径)
        - 最大回撤:窗口内收盘价相对其滚动前高的最大跌幅(均为价格指数口径,不含分红)
输出:reports/YYYYMMDD/15_global_index_5y.png(编号规则见 strategies/plot_paths.py)
运行:.\\.venv\\Scripts\\python.exe strategies/stock/global_index_5y_mdd.py [起始日 YYYYMMDD] [结束日 YYYYMMDD]
"""

from __future__ import annotations

import sys

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
# 将 strategies/ 目录加入 sys.path,确保能导入共享模块 plot_paths
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plot_paths import report_image_path
from global_index_week_curve import LINE_COLORS, fetch_index_close, window_cum_return

FOCUS: dict[str, str] = {
    "沪深300": "sh000300",
    "标普500": ".INX",
}

def max_drawdown(close: pd.Series) -> dict:
    """窗口内最大回撤:收盘价相对滚动前高的最大跌幅,返回峰/谷日与修复状态。"""
    run_max = close.cummax()
    dd = close / run_max - 1.0
    trough = dd.idxmin()
    peak = close.loc[:trough].idxmax()
    recovered = bool(close.iloc[-1] >= close.loc[:trough].max())
    return {
        "mdd": float(dd.loc[trough]),
        "peak": peak,
        "trough": trough,
        "now_dd": float(dd.iloc[-1]),
        "recovered": recovered,
        "peak_close": float(close.loc[peak]),
        "trough_close": float(close.loc[trough]),
    }

def year_end_cum(cum: pd.Series, year: int) -> float | None:
    """某年窗口内最后交易日(或年末)的累计收益;该年无数据返回 None。"""
    part = cum.loc[str(year)]
    return part.iloc[-1] / 100.0 if len(part) else None

def main() -> None:
    end = pd.Timestamp(sys.argv[2]) if len(sys.argv) > 2 else pd.Timestamp.today().normalize()
    start = pd.Timestamp(sys.argv[1]) if len(sys.argv) > 1 else end - pd.DateOffset(years=5)

    curves: dict[str, pd.Series] = {}
    drawdowns: dict[str, pd.Series] = {}
    stats_rows: list[dict] = []
    milestones: dict[str, dict[str, float]] = {name: {} for name in FOCUS}

    for name, sym in FOCUS.items():
        df = fetch_index_close(sym)
        base, cum = window_cum_return(df, start, end)
        close = df.loc[(df.index >= start) & (df.index <= end), "Close"]
        mdd = max_drawdown(close)

        curves[name] = cum
        drawdowns[name] = (close / close.cummax() - 1.0) * 100.0

        years = (close.index[-1] - (close.index[0] - pd.Timedelta(days=1))).days / 365.25
        cagr = (1.0 + cum.iloc[-1] / 100.0) ** (1.0 / years) - 1.0
        stats_rows.append({
            "指数": name,
            "累计收益": cum.iloc[-1] / 100.0,
            "年化收益": cagr,
            "最大回撤": mdd["mdd"],
            "峰值日": f"{mdd['peak']:%Y-%m-%d}",
            "谷底日": f"{mdd['trough']:%Y-%m-%d}",
            "当前回撤": mdd["now_dd"],
            "已修复": "是" if mdd["recovered"] else "否",
        })
        for y in range(start.year, end.year + 1):
            val = year_end_cum(cum, y)
            if val is not None:
                milestones[name][f"{y}年末"] = val
        print(f"[{name}] 基准日({close.index[0] - pd.Timedelta(days=1):%Y-%m-%d}前收盘) {base:.2f}"
              f"  窗口累计 {cum.iloc[-1]:+.2f}%  最大回撤 {mdd['mdd'] * 100:+.2f}%"
              f"(峰 {mdd['peak']:%Y-%m-%d} → 谷 {mdd['trough']:%Y-%m-%d})")

    stat_df = pd.DataFrame(stats_rows).set_index("指数")
    msdf = pd.DataFrame(milestones)
    print("\n[近5年收益与回撤汇总](价格指数口径,不含分红)")
    with pd.option_context("float_format", "{:+.2%}".format):
        print(stat_df.to_string())
    print("\n[各年末时点累计收益]")
    with pd.option_context("float_format", "{:+.2%}".format):
        print(msdf.to_string())

    # ---------------- 出图:上=累计收益,下=回撤 ----------------
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 8), sharex=True,
        gridspec_kw={"height_ratios": [2.2, 1], "hspace": 0.10},
    )

    for name, cum in curves.items():
        color = LINE_COLORS.get(name)
        ax1.plot(cum.index, cum.values, linewidth=1.8,
                 color=color, label=f"{name}(最大回撤 {min(drawdowns[name]):+.1f}%)")
        ax1.annotate(f"{cum.iloc[-1]:+.1f}%", xy=(cum.index[-1], cum.iloc[-1]),
                     xytext=(8, 6), textcoords="offset points", color=color,
                     fontsize=10, fontweight="bold")

    ax1.axhline(0, color="#bbb", linewidth=0.8, linestyle="--")
    ax1.set_ylabel("累计收益(%)", fontsize=11)
    ax1.set_title("累计收益(基准=窗口前一交易日收盘)", fontsize=11)
    ax1.legend(loc="upper left", fontsize=10)
    ax1.grid(linestyle="--", alpha=0.3)

    for name, dd in drawdowns.items():
        color = LINE_COLORS.get(name)
        ax2.plot(dd.index, dd.values, linewidth=1.4, color=color, label=name)
        ax2.fill_between(dd.index, 0, dd.values, color=color, alpha=0.12)
        trough = dd.idxmin()
        ax2.scatter([trough], [dd.loc[trough]], color=color, s=28, zorder=5)
        ax2.annotate(f"谷 {trough:%Y-%m-%d} {dd.loc[trough]:+.1f}%",
                     xy=(trough, dd.loc[trough]), xytext=(8, 10),
                     textcoords="offset points", color=color, fontsize=9,
                     bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.75))

    ax2.set_ylabel("回撤(%)", fontsize=11)
    ax2.set_title("回撤(收盘价相对滚动前高的跌幅)", fontsize=11)
    ax2.grid(linestyle="--", alpha=0.3)
    ax2.xaxis.set_major_locator(mdates.YearLocator())
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax2.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=(4, 7, 10)))

    fig.suptitle(
        f"标普500 vs 沪深300 · 近5年累计收益与最大回撤({start:%Y-%m-%d} ~ {end:%Y-%m-%d})"
        f"　来源:OMMQ",
        fontsize=15, fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))

    out = report_image_path(15, "global_index_5y")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n图表已保存: {out}")

if __name__ == "__main__":
    main()
