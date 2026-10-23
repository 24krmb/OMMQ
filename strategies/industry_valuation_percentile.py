# -*- coding: utf-8 -*-
"""行业估值分位：申万一级行业 PE / PB 当前值与历史分位

内容（2×2）：
    1. 申万一级行业 PE（市盈率）当前值 横截面
    2. 申万一级行业 PE 近 5 年历史分位（红=高估 / 绿=低估）
    3. 申万一级行业 PB（市净率）当前值 横截面
    4. 重点行业 PE 近 5 年月频走势

数据源（申万宏源研究，口径与 Wind 一致）：
    - 月频截面：ak.index_analysis_monthly_sw(symbol="一级行业", date=月末)
    - 有效月末日期：ak.index_analysis_week_month_sw(symbol="month")
口径：历史分位 = 该行业当前 PE/PB 在其近 5 年月频序列中的分位数（0~100，越高越贵）。
输出：reports/YYYYMMDD/09_industry_valuation.png（编号规则见 strategies/plot_paths.py）
运行：uv run python strategies/industry_valuation_percentile.py [历史年数]   # 默认 5
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

YEARS = 5                      # 历史回溯年数（月频）
HIGH_COLOR = "#F36"         # 高估
LOW_COLOR = "#0C9"          # 低估
MID_COLOR = "#FC3"
FOCUS = ["食品饮料", "电子", "医药生物", "电力设备", "银行", "有色金属"]


def latest_trade_date() -> dt.date:
    try:
        dates = ak.tool_trade_date_hist_sina()["trade_date"]
        today = dt.date.today()
        past = [d for d in dates if d <= today]
        return past[-1] if past else today
    except Exception:  # noqa: BLE001
        return dt.date.today()


def month_end_dates(years: int) -> list[dt.date]:
    """申万有效的月末日期（近 years 年）。"""
    df = ak.index_analysis_week_month_sw(symbol="month")
    col = "date" if "date" in df.columns else df.columns[0]
    dates = pd.to_datetime(df[col]).dt.date.tolist()
    cutoff = dt.date.today() - dt.timedelta(days=int(years * 365.25))
    return [d for d in dates if d >= cutoff]


def fetch_panel(years: int) -> pd.DataFrame:
    """逐月末抓取申万一级行业 PE/PB，合并为长表。"""
    frames = []
    dates = month_end_dates(years)
    for i, d in enumerate(dates, 1):
        try:
            df = ak.index_analysis_monthly_sw(symbol="一级行业", date=d.strftime("%Y%m%d"))
            df["月份"] = pd.to_datetime(d)
            frames.append(df[["指数名称", "月份", "市盈率", "市净率"]])
        except Exception as e:  # noqa: BLE001
            print(f"  [跳过] {d}: {type(e).__name__}")
        if i % 12 == 0:
            print(f"  已抓取 {i}/{len(dates)} 个月末")
    return pd.concat(frames, ignore_index=True)


def _bar(ax, names: list[str], values: list[float], title: str, xlabel: str,
         colors: list[str] | None = None) -> None:
    d = pd.DataFrame({"名称": names, "值": values}).dropna().sort_values("值")
    ax.barh(d["名称"], d["值"], color=colors or "#99F")
    ax.set_title(title, fontsize=13)
    ax.set_xlabel(xlabel)
    ax.grid(axis="x", linestyle="--", alpha=0.3)
    ax.margins(x=0.15)
    for y, v in enumerate(d["值"]):
        ax.text(v, y, f" {v:.1f}", va="center", fontsize=8)


def main() -> None:
    years = int(sys.argv[1]) if len(sys.argv) > 1 else YEARS
    date = latest_trade_date()

    print(f"抓取申万一级行业近 {years} 年月频估值数据……")
    panel = fetch_panel(years)
    panel = panel.pivot_table(index="月份", columns="指数名称", values=["市盈率", "市净率"])
    panel = panel.sort_index()
    pe = panel["市盈率"]
    pb = panel["市净率"]

    cur = panel.iloc[-1]
    pe_cur = cur["市盈率"].dropna()
    pb_cur = cur["市净率"].dropna()
    pe_pct = {n: (pe[n] <= pe_cur[n]).mean() * 100 for n in pe_cur.index}
    pb_pct = {n: (pb[n] <= pb_cur[n]).mean() * 100 for n in pb_cur.index}

    def _col(v: float) -> str:
        return HIGH_COLOR if v >= 80 else (LOW_COLOR if v <= 20 else MID_COLOR)

    fig, axes = plt.subplots(2, 2, figsize=(16, 11))

    _bar(axes[0, 0], list(pe_cur.index), list(pe_cur.values),
         "申万一级行业 · 市盈率(PE) 当前值", "PE（倍）")
    _bar(axes[0, 1], list(pe_pct.keys()), list(pe_pct.values()),
         f"申万一级行业 · PE 历史分位（近 {years} 年月频）", "分位（%）",
         colors=[_col(v) for v in pe_pct.values()])
    _bar(axes[1, 0], list(pb_cur.index), list(pb_cur.values),
         "申万一级行业 · 市净率(PB) 当前值", "PB（倍）")

    ax = axes[1, 1]
    last_month = panel.index[-1]
    for nm in FOCUS:
        if nm in pe.columns and pe[nm].notna().any():
            ax.plot(pe.index, pe[nm], marker="o", markersize=2.5, linewidth=1.3, label=nm)
    ax.set_ylabel("PE（倍）")
    ax.set_title(f"重点行业 · PE 近 {years} 年月频走势（截至 {last_month:%Y-%m}）", fontsize=13)
    ax.legend(fontsize=9, ncol=3)
    ax.grid(linestyle="--", alpha=0.3)
    ax.tick_params(axis="x", rotation=30, labelsize=8)

    fig.suptitle(
        f"申万一级行业估值分位（数据截至 {last_month:%Y-%m}，历史窗口近 {years} 年）　来源：24K-Claw",
        fontsize=16, fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    out = report_image_path(9, "industry_valuation")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"图表已保存: {out}")

    pct_s = pd.Series(pe_pct).sort_values(ascending=False)
    print(f"\n[PE 历史分位 最高 TOP5]（近 {years} 年）")
    for nm, v in pct_s.head(5).items():
        print(f"  {nm:8s} PE {pe_cur[nm]:7.1f}  分位 {v:5.1f}%")
    print(f"\n[PE 历史分位 最低 TOP5]")
    for nm, v in pct_s.tail(5).items():
        print(f"  {nm:8s} PE {pe_cur[nm]:7.1f}  分位 {v:5.1f}%")


if __name__ == "__main__":
    main()
