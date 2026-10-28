# -*- coding: utf-8 -*-
"""同业杜邦分析 / 财务估值横向对比

内容(2×2):
    1. 主标的近 N 年 ROE 与销售净利率趋势
    2. 主标的近 N 年 总资产周转率 与 权益乘数(杜邦拆解因子,双轴)
    3. 同业 ROE(%) 与 销售净利率(%) 对比
    4. 同业 估值对比(PE-TTM / PB,双轴)
杜邦恒等式:ROE = 销售净利率 × 总资产周转率 × 权益乘数

数据源:
    - 财务指标(净利率 / 周转率 / 权益乘数 / ROE): ak.stock_financial_analysis_indicator
      (权益乘数 = 100 / 股东权益比率(%) = 总资产 / 股东权益)
    - 估值(PE-TTM / PB / 名称):腾讯 ak.stock_zh_a_spot_tx 全A快照
说明:东方财富接口在本机被限流,故财务走、估值走腾讯源。
输出:reports/YYYYMMDD/14_<主代码>.png(编号规则见 strategies/plot_paths.py)
运行:uv run python strategies/peer_dupond.py [主代码] [同业代码,逗号分隔]
      默认:600519 000858,000568,600809,002304,000596
"""

from __future__ import annotations

import os
import sys
import warnings

import akshare as ak
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from plot_paths import report_image_path

warnings.filterwarnings("ignore")
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC","Noto Sans SC","Microsoft YaHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False

matplotlib.rcParams["text.color"] = "#27254c"
matplotlib.rcParams["axes.labelcolor"] = "#27254c"
matplotlib.rcParams["axes.titlecolor"] = "#27254c"
matplotlib.rcParams["xtick.color"] = "#27254c"
matplotlib.rcParams["ytick.color"] = "#27254c"

DEFAULT_MAIN = "600519"
DEFAULT_PEERS = ["000858", "000568", "600809", "002304", "000596"]
YEARS = 8

MAIN_COLOR = "#F36"   # 主标的高亮色
PEER_COLOR = "#99F"
ROE_COLOR = "#F36"
MARGIN_COLOR = "#99F"
TURN_COLOR = "#0C9"
LEV_COLOR = "#FC3"


def sina_prefix(code: str) -> str:
    c = code.strip()
    if c[0] in "569":
        return "sh" + c
    if c[0] in "03":
        return "sz" + c
    if c[0] in "48":
        return "bj" + c
    return "sh" + c


def fetch_dupont(code: str, years: int = YEARS) -> pd.DataFrame:
    """年报口径的杜邦拆解因子。"""
    df = ak.stock_financial_analysis_indicator(symbol=code, start_year="2014")
    df["日期"] = pd.to_datetime(df["日期"])
    ann = df[df["日期"].dt.strftime("%m-%d") == "12-31"].copy()
    ann = ann.sort_values("日期")
    cols = ["净资产收益率(%)", "销售净利率(%)", "总资产周转率(次)", "股东权益比率(%)", "资产负债率(%)"]
    for c in cols:
        ann[c] = pd.to_numeric(ann[c], errors="coerce")
    ann["权益乘数"] = 100 / ann["股东权益比率(%)"].replace(0, pd.NA)
    ann = ann.dropna(subset=["净资产收益率(%)", "销售净利率(%)", "总资产周转率(次)", "权益乘数"])
    ann["年"] = ann["日期"].dt.strftime("%Y")
    return ann.tail(years).reset_index(drop=True)


def fetch_valuation() -> dict[str, dict]:
    """腾讯全A快照 -> {带前缀代码: {name, pe, pb}}。"""
    df = ak.stock_zh_a_spot_tx()
    out: dict[str, dict] = {}
    for _, row in df.iterrows():
        out[str(row["code"])] = {
            "name": str(row["name"]),
            "pe": pd.to_numeric(row["pe_ttm"], errors="coerce"),
            "pb": pd.to_numeric(row["pn"], errors="coerce"),
        }
    return out


def latest_row(df: pd.DataFrame) -> pd.Series:
    return df.iloc[-1]


def main() -> None:
    main_code = sys.argv[1].strip() if len(sys.argv) > 1 else DEFAULT_MAIN
    if len(sys.argv) > 2:
        peers = [c.strip() for c in sys.argv[2].split(",") if c.strip()]
    else:
        peers = list(DEFAULT_PEERS)
    codes = [main_code] + [c for c in peers if c != main_code]
    prefix = {c: sina_prefix(c) for c in codes}

    valuation = fetch_valuation()
    dupont: dict[str, pd.DataFrame] = {}
    names: dict[str, str] = {}
    for c in codes:
        try:
            dupont[c] = fetch_dupont(c)
        except Exception as e:  # noqa: BLE001
            print(f"[跳过] {c} 财务: {type(e).__name__} {e}")
            continue
        names[c] = valuation.get(prefix[c], {}).get("name") or c
        print(f"[OK] {c} {names[c]}: {len(dupont[c])} 年")

    codes = [c for c in codes if c in dupont]
    md = dupont[main_code]

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    # (0,0) 主标的 ROE 与 销售净利率 趋势
    ax = axes[0, 0]
    x = range(len(md))
    ax.plot(x, md["净资产收益率(%)"], marker="o", color=ROE_COLOR, label="ROE(%)")
    ax.plot(x, md["销售净利率(%)"], marker="s", color=MARGIN_COLOR, label="销售净利率(%)")
    ax.set_xticks(list(x))
    ax.set_xticklabels(md["年"], fontsize=9)
    ax.set_ylabel("(%)")
    ax.set_title(f"{main_code} {names.get(main_code,'')} ROE / 销售净利率", fontsize=13)
    ax.legend()
    ax.grid(linestyle="--", alpha=0.3)

    # (0,1) 主标的 总资产周转率 & 权益乘数
    ax = axes[0, 1]
    ax.plot(x, md["总资产周转率(次)"], marker="o", color=TURN_COLOR, label="总资产周转率(次)")
    ax.set_ylabel("总资产周转率(次)", color=TURN_COLOR)
    ax.tick_params(axis="y", labelcolor=TURN_COLOR)
    ax2 = ax.twinx()
    ax2.plot(x, md["权益乘数"], marker="^", color=LEV_COLOR, label="权益乘数")
    ax2.set_ylabel("权益乘数", color=LEV_COLOR)
    ax2.tick_params(axis="y", labelcolor=LEV_COLOR)
    ax.set_xticks(list(x))
    ax.set_xticklabels(md["年"], fontsize=9)
    ax.set_title(f"{main_code} {names.get(main_code,'')} 杜邦拆解因子(周转率 / 权益乘数)", fontsize=13)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="best")
    ax.grid(linestyle="--", alpha=0.3)

    # (1,0) 同业 ROE / 净利率 对比
    ax = axes[1, 0]
    labels, roes, marg = [], [], []
    for c in codes:
        r = latest_row(dupont[c])
        labels.append(f"{names.get(c,c)}\n{c}")
        roes.append(r["净资产收益率(%)"])
        marg.append(r["销售净利率(%)"])
    xi = range(len(codes))
    w = 0.38
    b1 = ax.bar([i - w / 2 for i in xi], roes, w, color=ROE_COLOR, label="ROE(%)")
    b2 = ax.bar([i + w / 2 for i in xi], marg, w, color=MARGIN_COLOR, label="销售净利率(%)")
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height(),
                    f"{b.get_height():.1f}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(list(xi))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_title("同业 ROE / 销售净利率 对比(最新年报)", fontsize=13)
    ax.set_ylabel("(%)")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.3)

    # (1,1) 同业 估值 PE-TTM / PB 对比
    ax = axes[1, 1]
    pe, pb, xl = [], [], []
    for c in codes:
        v = valuation.get(prefix[c], {})
        pe.append(v.get("pe", float("nan")))
        pb.append(v.get("pb", float("nan")))
        xl.append(f"{names.get(c,c)}\n{c}")
    xi = list(range(len(codes)))
    ax.bar([i - w / 2 for i in xi], pe, w, color="#FC3", label="PE-TTM(左轴)")
    ax.set_ylabel("PE-TTM", color="#27254c")
    ax.tick_params(axis="y", labelcolor="#27254c")
    ax3 = ax.twinx()
    ax3.bar([i + w / 2 for i in xi], pb, w, color="#0C9", label="PB(右轴)")
    ax3.set_ylabel("PB", color="#27254c")
    ax3.tick_params(axis="y", labelcolor="#27254c")
    ax.set_xticks(xi)
    ax.set_xticklabels(xl, fontsize=8)
    ax.set_title("同业估值对比(PE-TTM / PB)", fontsize=13)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax3.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="best")
    ax.grid(axis="y", linestyle="--", alpha=0.3)

    fig.suptitle(
        f"{main_code} {names.get(main_code,'')} 杜邦分析 / 同业财务估值对比　来源:24K-Claw",
        fontsize=16, fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    out = report_image_path(14, main_code)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n图表已保存: {out}")

    print(f"\n[{main_code} {names.get(main_code,'')} 最新年报杜邦拆解]")
    r = latest_row(md)
    print(f"  ROE {r['净资产收益率(%)']:.2f}% = 净利率 {r['销售净利率(%)']:.2f}% "
          f"× 周转率 {r['总资产周转率(次)']:.3f} × 权益乘数 {r['权益乘数']:.3f} "
          f"= {r['销售净利率(%)']/100*r['总资产周转率(次)']*r['权益乘数']*100:.2f}%")
    print(f"\n[同业估值对比]")
    for c in codes:
        v = valuation.get(prefix[c], {})
        print(f"  {c} {names.get(c,''):6s}  PE-TTM {v.get('pe', float('nan')):>7.2f}   PB {v.get('pb', float('nan')):>6.2f}")


if __name__ == "__main__":
    main()
