# -*- coding: utf-8 -*-
"""申万一级行业板块轮动热力图

内容:近 N 个交易日 申万一级行业(31 个)每日涨跌幅热力图
     行 = 行业(按区间累计涨幅从高到低排序),列 = 交易日,颜色 红涨绿跌

数据源:申万宏源研究-指数历史行情 AKShare: ak.index_hist_sw(逐行业)
    行业清单:申万一级行业 ak.sw_index_first_info()
    涨跌幅 = 当日收盘 / 前一日收盘 - 1
说明:口径为申万一级行业(与 Wind 一致)；东方财富接口在本机被限流,故走申万源。
输出:reports/YYYYMMDD/04.png(编号规则见 strategies/plot_paths.py)
运行:uv run python strategies/sector_rotation_heatmap.py [交易日数]   # 默认 20
"""

from __future__ import annotations

import datetime as dt
import os
import sys
import warnings

import akshare as ak
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from plot_paths import report_image_path
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

warnings.filterwarnings("ignore")
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC","Noto Sans SC","Microsoft YaHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False

matplotlib.rcParams["text.color"] = "#27254c"
matplotlib.rcParams["axes.labelcolor"] = "#27254c"
matplotlib.rcParams["axes.titlecolor"] = "#27254c"
matplotlib.rcParams["xtick.color"] = "#27254c"
matplotlib.rcParams["ytick.color"] = "#27254c"

N = 20  # 展示最近多少个交易日
# 统一配色热力图:绿 #0C9(跌)→ 白 → 红 #F36(涨)
CLaw_CMAP = LinearSegmentedColormap.from_list("claw", ["#0C9", "#FFFFFF", "#F36"])


def latest_trade_date() -> dt.date:
    try:
        dates = ak.tool_trade_date_hist_sina()["trade_date"]
        today = dt.date.today()
        past = [d for d in dates if d <= today]
        return past[-1] if past else today
    except Exception:  # noqa: BLE001
        return dt.date.today()


def industry_list() -> list[tuple[str, str]]:
    """申万一级行业 (代码, 名称)。"""
    df = ak.sw_index_first_info()
    out = []
    for _, row in df.iterrows():
        code = str(row["行业代码"]).split(".")[0]
        out.append((code, str(row["行业名称"])))
    return out


def fetch_pct(code: str, n: int) -> pd.Series:
    """某申万行业近 n 个日度涨跌幅(%)。"""
    df = ak.index_hist_sw(symbol=code, period="day")
    df["日期"] = pd.to_datetime(df["日期"])
    s = df.sort_values("日期").set_index("日期")["收盘"].astype(float)
    pct = s.pct_change() * 100
    return pct.dropna().tail(n)


def build_matrix(n: int) -> tuple[pd.DataFrame, list[str]]:
    inds = industry_list()
    series: dict[str, pd.Series] = {}
    for i, (code, name) in enumerate(inds, 1):
        try:
            series[name] = fetch_pct(code, n)
            print(f"\r  拉取行业行情 {i}/{len(inds)}: {name}      ", end="")
        except Exception as e:  # noqa: BLE001
            print(f"\n  [跳过] {name}: {type(e).__name__} {e}")
    print()
    mat = pd.DataFrame(series).T  # 行=行业, 列=日期
    dates = [d.strftime("%m-%d") for d in mat.columns]
    cum = mat.sum(axis=1)  # 区间累计涨幅(近似,求和日收益)
    mat = mat.loc[cum.sort_values(ascending=False).index]
    return mat, dates


def draw_heatmap(mat: pd.DataFrame, dates: list[str], out: str) -> None:
    vals = mat.to_numpy(float)
    m = np.nanmax(np.abs(vals))
    norm = TwoSlopeNorm(vcenter=0, vmin=-m, vmax=m)

    fig, ax = plt.subplots(figsize=(1.0 + 0.55 * len(dates), 0.42 * len(mat) + 2.4))
    im = ax.imshow(vals, cmap=CLaw_CMAP, norm=norm, aspect="auto")

    ax.set_xticks(range(len(dates)))
    ax.set_xticklabels(dates, rotation=90, fontsize=9)
    ax.set_yticks(range(len(mat.index)))
    ax.set_yticklabels(mat.index, fontsize=10)
    ax.set_xlabel("交易日", fontsize=11)

    for i in range(vals.shape[0]):
        for j in range(vals.shape[1]):
            v = vals[i, j]
            if np.isnan(v):
                continue
            ax.text(j, i, f"{v:.1f}", ha="center", va="center",
                    fontsize=7, color="#222222" if abs(v) < m * 0.55 else "#ffffff")

    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.015)
    cbar.set_label("日涨跌幅 (%)", fontsize=10)

    first, last = mat.columns[0], mat.columns[-1]
    fig.suptitle(
        f"申万一级行业轮动热力图({first:%Y-%m-%d} ~ {last:%Y-%m-%d},共 {len(dates)} 个交易日)"
        f"　来源:24K-Claw",
        fontsize=15, fontweight="bold",
    )
    # rect 不传:让 tight_layout 走自然路径自动预留 suptitle 空间(传 rect 会双重预留,
    # 反而把内容压低——实测顶部多出约 4% 空白)
    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else N
    date = latest_trade_date()
    mat, dates = build_matrix(n)

    out = report_image_path(4)
    draw_heatmap(mat, dates, out)
    print(f"图表已保存: {out}")

    cum = mat.sum(axis=1).sort_values(ascending=False)
    print(f"\n[区间累计涨幅 TOP5]\n" + cum.head(5).to_string(float_format=lambda v: f"{v:+.2f}%"))
    print(f"\n[区间累计涨幅 BOTTOM5]\n" + cum.tail(5).to_string(float_format=lambda v: f"{v:+.2f}%"))


if __name__ == "__main__":
    main()
