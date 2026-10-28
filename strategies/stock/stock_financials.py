# -*- coding: utf-8 -*-
"""获取个股各项财务数据:主要财务指标 + 三大报表

数据源:
    - 主要财务指标:同花顺 ak.stock_financial_abstract_ths(symbol, indicator="按报告期")
    - 三大报表(利润表 / 资产负债表 / 现金流量表):
      ak.stock_financial_report_sina(stock="sh600519", symbol="利润表")

说明:东方财富接口在本机被限流,故采用同花顺 + 源。
输出:strategies/output/financials/<代码>/*.csv(utf-8-sig,Excel 可直接打开)
      reports/YYYYMMDD/12_<代码>.png(中文图表；CSV 数据仍存 strategies/output/)
运行:uv run python strategies/stock_financials.py [股票代码]   # 默认 600519
"""

from __future__ import annotations

import os
import sys

import akshare as ak
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from plot_paths import report_image_path

matplotlib.rcParams["font.sans-serif"] = ["PingFang SC","Noto Sans SC","Microsoft YaHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False

matplotlib.rcParams["text.color"] = "#27254c"
matplotlib.rcParams["axes.labelcolor"] = "#27254c"
matplotlib.rcParams["axes.titlecolor"] = "#27254c"
matplotlib.rcParams["xtick.color"] = "#27254c"
matplotlib.rcParams["ytick.color"] = "#27254c"

OUT_DIR = "strategies/output/financials"

REPORTS = ("利润表", "资产负债表", "现金流量表")
QUARTERS = 12  # 图表展示最近多少个季度


def sina_prefix(code: str) -> str:
    """把 6 位代码转成需要的带市场前缀代码。"""
    c = code.strip()
    if c[0] in "569":
        return "sh" + c
    if c[0] in "03":
        return "sz" + c
    if c[0] in "48":
        return "bj" + c
    return "sh" + c


def fetch_main_indicators(code: str) -> pd.DataFrame:
    """主要财务指标(按报告期)。"""
    return ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")


def fetch_report(stock: str, name: str) -> pd.DataFrame:
    """三大报表之一。"""
    return ak.stock_financial_report_sina(stock=stock, symbol=name)


def _num(value) -> float | None:
    """解析 '922.78亿' / '16.75%' / '35.57' 等为数值(金额单位:亿；百分比为百分数)。"""
    s = str(value).strip()
    if s in ("", "False", "--", "None", "nan"):
        return None
    mult = 1.0
    if s.endswith("万亿"):
        mult, s = 1e4, s[:-2]
    elif s.endswith("亿"):
        mult, s = 1.0, s[:-1]
    elif s.endswith("万"):
        mult, s = 1e-4, s[:-1]
    elif s.endswith("%"):
        s = s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return None


def _series(frame: pd.DataFrame, col: str) -> list[float]:
    """取某列并转成浮点序列,缺失填 NaN。"""
    if col not in frame.columns:
        return [float("nan")] * len(frame)
    vals = [_num(v) for v in frame[col]]
    return [float("nan") if v is None else v for v in vals]


def _q_label(period: str) -> str:
    """报告期 -> 季度标签,如 '2026-06-30' -> '2026Q2'。"""
    y, m = period[:4], int(period[5:7])
    return f"{y}Q{(m + 2) // 3}"


def _single_quarter(values: list[float], years: list[str]) -> list[float]:
    """把累计值(年初至今)折算为单季值:同年内与前季相减,跨年(Q1)取原值。"""
    out: list[float] = []
    prev, prev_year = None, None
    for v, y in zip(values, years):
        if y != prev_year or prev is None:
            out.append(v)  # 当年首季
        elif v != v or prev != prev:
            out.append(float("nan"))
        else:
            out.append(v - prev)
        prev, prev_year = v, y
    return out


def plot_overview(code: str, ind: pd.DataFrame, out_dir: str) -> str | None:
    """按季度绘制中文财务概览图表(营收/净利/EPS 为单季口径)。"""
    df = ind.copy()
    df["报告期"] = df["报告期"].astype(str)
    q = df[df["报告期"].str.endswith(("03-31", "06-30", "09-30", "12-31"))]
    q = q.sort_values("报告期").reset_index(drop=True)
    if len(q) < 4:
        return None
    q["年"] = q["报告期"].str[:4]

    # 累计 -> 单季(先在全序列上折算,再截取最近 N 个季度)
    q["单季营收"] = _single_quarter(_series(q, "营业总收入"), q["年"].tolist())
    q["单季净利"] = _single_quarter(_series(q, "净利润"), q["年"].tolist())
    q["单季EPS"] = _single_quarter(_series(q, "基本每股收益"), q["年"].tolist())
    q["单季现金流"] = _single_quarter(_series(q, "每股经营现金流"), q["年"].tolist())

    q = q.tail(QUARTERS).reset_index(drop=True)
    labels = [_q_label(p) for p in q["报告期"]]
    gm = _series(q, "销售毛利率")
    debt = _series(q, "资产负债率")
    grow_rev = _series(q, "营业总收入同比增长率")
    grow_profit = _series(q, "净利润同比增长率")

    fig, axes = plt.subplots(2, 2, figsize=(14, 9.5))
    x = list(range(len(labels)))

    # (0,0) 单季营业总收入 / 单季净利润(柱状)
    ax = axes[0, 0]
    ax.bar([i - 0.2 for i in x], q["单季营收"], 0.4, label="单季营业总收入", color="#F36")
    ax.bar([i + 0.2 for i in x], q["单季净利"], 0.4, label="单季净利润", color="#0C9")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, fontsize=9)
    ax.set_ylabel("亿元")
    ax.set_title("单季营业总收入 / 单季净利润", fontsize=13)
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.35)

    # (0,1) 单季每股收益 / 每股经营现金流(折线)
    ax = axes[0, 1]
    ax.plot(labels, q["单季EPS"], marker="o", label="单季每股收益", color="#F36")
    ax.plot(labels, q["单季现金流"], marker="s", label="单季每股经营现金流", color="#99F")
    ax.tick_params(axis="x", rotation=45, labelsize=9)
    ax.set_ylabel("元")
    ax.set_title("单季每股收益 / 每股经营现金流", fontsize=13)
    ax.legend()
    ax.grid(linestyle="--", alpha=0.35)

    # (1,0) 毛利率 / 资产负债率(左右双轴折线)
    ax = axes[1, 0]
    ax.plot(labels, gm, marker="o", label="销售毛利率", color="#F36")
    ax.set_ylabel("销售毛利率 (%)", color="#27254c")
    ax.tick_params(axis="y", labelcolor="#27254c")
    ax2 = ax.twinx()
    ax2.plot(labels, debt, marker="s", label="资产负债率", color="#99F")
    ax2.set_ylabel("资产负债率 (%)", color="#27254c")
    ax2.tick_params(axis="y", labelcolor="#27254c")
    ax.tick_params(axis="x", rotation=45, labelsize=9)
    ax.set_title("销售毛利率 / 资产负债率 (%)", fontsize=13)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="best")
    ax.grid(linestyle="--", alpha=0.35)

    # (1,1) 同比增长率(折线)
    ax = axes[1, 1]
    ax.plot(labels, grow_rev, marker="o", label="营业总收入同比增长率", color="#F36")
    ax.plot(labels, grow_profit, marker="s", label="净利润同比增长率", color="#99F")
    ax.tick_params(axis="x", rotation=45, labelsize=9)
    ax.set_title("同比增长率 (%)", fontsize=13)
    ax.legend()
    ax.grid(linestyle="--", alpha=0.35)

    fig.suptitle(
        f"{code} 财务概览(近 {len(labels)} 个季度)　来源:24K-Claw",
        fontsize=16,
        fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))

    out = report_image_path(12, code)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    code = sys.argv[1].strip() if len(sys.argv) > 1 else "600519"
    stock = sina_prefix(code)
    out_dir = os.path.join(OUT_DIR, code)
    os.makedirs(out_dir, exist_ok=True)
    print(f"标的:{code} (代码 {stock})\n")

    # 1) 主要财务指标
    try:
        ind = fetch_main_indicators(code)
        path = os.path.join(out_dir, "主要财务指标.csv")
        ind.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"[OK] 主要财务指标: {ind.shape[0]} 期 x {ind.shape[1]} 指标 -> {path}")
        latest = ind.sort_values("报告期", ascending=False).head(3)
        show = ["报告期", "营业总收入", "净利润", "基本每股收益", "净资产收益率", "销售毛利率", "资产负债率"]
        show = [c for c in show if c in latest.columns]
        print("\n最近 3 期主要指标:")
        print(latest[show].to_string(index=False))

        chart = plot_overview(code, ind, out_dir)
        if chart:
            print(f"[OK] 财务概览图表 -> {chart}")
    except Exception as e:  # noqa: BLE001
        print(f"[失败] 主要财务指标: {type(e).__name__} {e}")

    # 2) 三大报表
    print()
    for name in REPORTS:
        try:
            df = fetch_report(stock, name)
            path = os.path.join(out_dir, f"{name}.csv")
            df.to_csv(path, index=False, encoding="utf-8-sig")
            periods = df.shape[0]
            print(f"[OK] {name}: {periods} 期 x {df.shape[1]} 项 -> {path}")
        except Exception as e:  # noqa: BLE001
            print(f"[失败] {name}: {type(e).__name__} {e}")

    print(f"\n全部数据已保存至:{out_dir}")


if __name__ == "__main__":
    main()
