# -*- coding: utf-8 -*-
"""最新行情 国内商品期货主力合约 涨幅 TOP5 / 跌幅 TOP5 中文图表

数据源：新浪财经期货实时行情（hq.sinajs.cn，nf_ 前缀）
    合约清单：AKShare ak.futures_display_main_sina()（主力连续合约一览）
    涨跌幅 = 最新价 / 昨结算 - 1
说明：
    - 仅取商品期货（dce/czce/shfe/gfex/ine），剔除中金所金融期货（字段布局不同）。
    - 东方财富 clist 接口在本机被限流，故直接走新浪行情接口并按字段索引解析。
输出：reports/YYYYMMDD/06.png（编号规则见 strategies/plot_paths.py）
运行：uv run python strategies/futures_top5_chart.py
"""

from __future__ import annotations

import datetime as dt
import os
import time

import akshare as ak
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from plot_paths import report_image_path
import requests

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

TOP_N = 5
UP_COLOR = "#F36"    # 红涨
DOWN_COLOR = "#0C9"  # 绿跌
EXCLUDE_EXCHANGE = {"cffex"}  # 剔除金融期货

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://vip.stock.finance.sina.com.cn/",
}

# 商品期货 nf_ 字段索引：0=名称, 8=最新价, 10=昨结算
IDX_NAME, IDX_CURRENT, IDX_SETTLE = 0, 8, 10


def main_contracts() -> pd.DataFrame:
    """国内商品期货主力连续合约清单。"""
    df = ak.futures_display_main_sina()
    return df[~df["exchange"].isin(EXCLUDE_EXCHANGE)].reset_index(drop=True)


def fetch_quotes(symbols: list[str]) -> pd.DataFrame:
    """批量拉取新浪 nf_ 实时行情，按字段索引解析。"""
    subs = ",".join(f"nf_{s}" for s in symbols)
    url = f"https://hq.sinajs.cn/rn={int(time.time())}&list={subs}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.encoding = "gbk"

    rows: list[dict] = []
    for line in r.text.split(";"):
        if "hq_str_nf_" not in line:
            continue
        head, _, payload = line.partition("=")
        symbol = head.split("hq_str_nf_")[1].strip()
        parts = payload.strip().strip('"').split(",")
        if len(parts) < 11:
            continue
        try:
            current = float(parts[IDX_CURRENT])
            settle = float(parts[IDX_SETTLE])
        except ValueError:
            continue
        if current <= 0 or settle <= 0:
            continue
        rows.append({
            "合约": parts[IDX_NAME],
            "代码": symbol,
            "涨跌幅": (current / settle - 1) * 100,
        })
    return pd.DataFrame(rows)


def draw(ax, df: pd.DataFrame, title: str, color: str) -> None:
    # df 已按需排好序：barh 自下而上，列表最后一个显示在最上方
    ax.barh(df["合约"], df["涨跌幅"], color=color)
    ax.axvline(0, color="#888888", linewidth=0.8)
    ax.set_title(title, fontsize=14, pad=12)
    ax.set_xlabel("涨跌幅 (%)")
    ax.margins(x=0.22)
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    for y, v in enumerate(df["涨跌幅"]):
        ax.text(
            v + (0.1 if v >= 0 else -0.1), y, f"{v:+.2f}%",
            va="center", ha="left" if v >= 0 else "right", fontsize=10,
        )


def main() -> None:
    df = fetch_quotes(main_contracts()["symbol"].tolist())
    # 涨幅：升序（数值最大者排最后 -> 显示在最上方）
    top = df.nlargest(TOP_N, "涨跌幅").sort_values("涨跌幅").reset_index(drop=True)
    # 跌幅：降序（跌幅最大者排最后 -> 显示在最上方）
    bot = df.nsmallest(TOP_N, "涨跌幅").sort_values("涨跌幅", ascending=False).reset_index(drop=True)

    date = dt.date.today()
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.2))
    draw(axes[0], top, f"商品期货主力 · 涨幅 TOP{TOP_N}", UP_COLOR)
    draw(axes[1], bot, f"商品期货主力 · 跌幅 TOP{TOP_N}", DOWN_COLOR)
    fig.suptitle(f"国内商品期货主力合约 涨跌幅 TOP{TOP_N}（{date}）　来源：24K-Claw",
                 fontsize=16, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))

    out = report_image_path(6)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"图表已保存: {out}")
    print(f"\n[涨幅 TOP{TOP_N}]\n" + top[["合约", "代码", "涨跌幅"]].to_string(index=False))
    print(f"\n[跌幅 TOP{TOP_N}]\n" + bot[["合约", "代码", "涨跌幅"]].to_string(index=False))


if __name__ == "__main__":
    main()
