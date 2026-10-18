# -*- coding: utf-8 -*-
"""期货基差 / 跨期价差：期货 vs 现货、近月 vs 远月

内容（2×2）：
    1. 商品期货 · 主力基差率（期货 vs 现货）横截面：基差率 =（期货−现货）/现货
       正 = 期货升水(contango)，负 = 期货贴水(backwardation)
    2. 商品期货 · 跨期价差率（近月 vs 远月）横截面：价差率 =（临近交割合约−主力合约）/主力
    3. 重点品种 · 主力基差率 近 N 个交易日走势
    4. 股指期货 · 基差（现货指数 vs 主力合约）：IF / IH / IC / IM

数据源：
    - 商品现货/近月/主力价格与基差：生意社 AKShare: ak.futures_spot_price(_daily)
    - 股指期货主力合约行情：新浪 AKShare: ak.futures_zh_realtime
    - 现货指数（沪深300/上证50/中证500/中证1000）：中证指数官网 ak.stock_zh_index_hist_csindex
说明：东方财富接口在本机被限流，故全部改用生意社 / 新浪 / 中证指数源。
输出：strategies/output/futures_basis_<日期>.png
运行：uv run python strategies/futures_basis_spread.py [历史交易日数]   # 默认 15
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
N_HIST = 15          # 基差率历史回溯交易日数
N_CROSS = 18         # 横截面展示品种数（按 |基差率| 取前 N）
UP_COLOR = "#F36"   # 正（期货升水 / 近月升水）
DOWN_COLOR = "#0C9"  # 负（期货贴水 / 近月贴水）

# 基差率历史回溯的重点品种
HIST_VARS = ["RB", "I", "CU", "AL", "M", "C"]

# 基差/跨期横截面仅纳入主流活跃品种（剔除现货口径差异过大的品种，如烧碱）
MAIN_VARS = [
    "RB", "HC", "I", "J", "JM", "CU", "AL", "ZN", "NI", "PB", "SN",
    "AU", "AG", "SC", "FU", "BU", "TA", "MA", "PP", "L", "V", "EG",
    "M", "Y", "A", "P", "C", "CS", "CF", "SR", "OI", "RM", "RU",
    "SA", "FG", "UR", "SP", "AP", "LH", "SM", "SF", "AO", "PF", "PK",
]

# 股指期货： (新浪品种名, 现货指数代码, 现货指数名)
INDEX_FUT = [
    ("沪深300指数期货", "000300", "沪深300"),
    ("上证50指数期货", "000016", "上证50"),
    ("中证500指数期货", "000905", "中证500"),
    ("中证1000股指期货", "000852", "中证1000"),
]

# 常见商品中文名（用于图表更易读，缺失则回退代码）
NAME_MAP = {
    "RB": "螺纹钢", "HC": "热卷", "I": "铁矿石", "J": "焦炭", "JM": "焦煤",
    "CU": "铜", "AL": "铝", "ZN": "锌", "NI": "镍", "SN": "锡", "PB": "铅",
    "AU": "黄金", "AG": "白银", "SC": "原油", "FU": "燃料油", "BU": "沥青",
    "TA": "PTA", "MA": "甲醇", "PP": "聚丙烯", "L": "塑料", "V": "PVC", "EG": "乙二醇",
    "M": "豆粕", "Y": "豆油", "A": "豆一", "B": "豆二", "P": "棕榈油",
    "C": "玉米", "CS": "淀粉", "CF": "棉花", "SR": "白糖", "OI": "菜油",
    "RM": "菜粕", "AP": "苹果", "SP": "纸浆", "RU": "橡胶", "SA": "纯碱",
    "FG": "玻璃", "UR": "尿素", "SF": "硅铁", "SM": "锰硅", "LH": "生猪",
}


def latest_trade_date() -> dt.date:
    try:
        dates = ak.tool_trade_date_hist_sina()["trade_date"]
        today = dt.date.today()
        past = [d for d in dates if d <= today]
        return past[-1] if past else today
    except Exception:  # noqa: BLE001
        return dt.date.today()


def label(code: str) -> str:
    return NAME_MAP.get(code, code)


def fetch_cross(date: dt.date) -> pd.DataFrame:
    """单日商品现货/近月/主力价格与基差横截面。"""
    df = ak.futures_spot_price(date=date.strftime("%Y%m%d"))
    df = df[df["symbol"].isin(MAIN_VARS)].reset_index(drop=True)
    df["主力基差率"] = pd.to_numeric(df["dom_basis_rate"], errors="coerce") * 100
    df["跨期价差率"] = (
        (pd.to_numeric(df["near_contract_price"], errors="coerce")
         - pd.to_numeric(df["dominant_contract_price"], errors="coerce"))
        / pd.to_numeric(df["dominant_contract_price"], errors="coerce") * 100
    )
    df["名称"] = df["symbol"].map(label)
    return df


def fetch_hist(n: int) -> pd.DataFrame:
    """重点品种主力基差率近 n 个交易日走势（透视表）。"""
    end = latest_trade_date()
    start = end - dt.timedelta(days=int(n * 1.7) + 10)
    df = ak.futures_spot_price_daily(
        start_day=start.strftime("%Y%m%d"),
        end_day=end.strftime("%Y%m%d"),
        vars_list=HIST_VARS,
    )
    df = df[df["symbol"].isin(HIST_VARS)].copy()
    df["dom_basis_rate"] = pd.to_numeric(df["dom_basis_rate"], errors="coerce") * 100
    df["date"] = pd.to_datetime(df["date"].astype(str))
    pivot = df.pivot_table(index="date", columns="symbol", values="dom_basis_rate")
    pivot = pivot.sort_index().tail(n)
    pivot.columns = [label(c) for c in pivot.columns]
    return pivot


def fetch_index_futures() -> list[dict]:
    """股指期货基差：现货指数 vs 主力合约。"""
    out: list[dict] = []
    end = dt.date.today()
    start = end - dt.timedelta(days=30)
    for nm, code, idx_name in INDEX_FUT:
        try:
            ft = ak.futures_zh_realtime(symbol=nm)
            ft = ft[~ft["name"].str.contains("连续")]
            ft = ft.dropna(subset=["position"])
            main = ft.loc[ft["position"].idxmax()]
            fut_px = float(main["trade"])
            fut_ct = str(main["symbol"])
            spot_df = ak.stock_zh_index_hist_csindex(
                symbol=code, start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"),
            )
            spot_df = spot_df.dropna(subset=["收盘"])
            spot_px = float(spot_df["收盘"].iloc[-1])
            out.append({
                "名称": idx_name, "合约": fut_ct, "现货": spot_px, "期货": fut_px,
                "基差率": (fut_px - spot_px) / spot_px * 100,
            })
        except Exception as e:  # noqa: BLE001
            print(f"  [跳过] {idx_name}: {type(e).__name__} {e}")
    return out


def draw_cross(ax, df: pd.DataFrame, col: str, title: str, xlabel: str) -> None:
    d = df.dropna(subset=[col]).copy()
    d = d.reindex(d[col].abs().sort_values(ascending=False).index).head(N_CROSS)
    d = d.sort_values(col)
    colors = [UP_COLOR if v >= 0 else DOWN_COLOR for v in d[col]]
    ax.barh(d["名称"], d[col], color=colors)
    ax.axvline(0, color="#888", linewidth=0.8)
    ax.set_title(title, fontsize=13, pad=10)
    ax.set_xlabel(xlabel)
    ax.margins(x=0.22)
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    for y, v in enumerate(d[col]):
        ax.text(v + (0.05 if v >= 0 else -0.05) * d[col].abs().max() / 1.0, y, f"{v:+.2f}%",
                va="center", ha="left" if v >= 0 else "right", fontsize=9)


def draw_hist(ax, pivot: pd.DataFrame) -> None:
    x = range(len(pivot))
    for c in pivot.columns:
        ax.plot(x, pivot[c], marker="o", markersize=3, linewidth=1.4, label=c)
    ax.axhline(0, color="#888", linewidth=0.8)
    idx = list(x)
    step = max(1, len(idx) // 8)
    ticks = idx[::step]
    ax.set_xticks(ticks)
    ax.set_xticklabels([pivot.index[i].strftime("%m-%d") for i in ticks], fontsize=9)
    ax.set_ylabel("主力基差率 (%)")
    ax.set_title("重点品种 · 主力基差率走势（正=期货升水）", fontsize=13)
    ax.legend(fontsize=9, ncol=3)
    ax.grid(linestyle="--", alpha=0.35)


def draw_index(ax, rows: list[dict]) -> None:
    if not rows:
        ax.text(0.5, 0.5, "股指期货数据不可用", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("股指期货 · 基差（现货 vs 主力）", fontsize=13)
        return
    names = [f"{r['名称']}\n{r['合约']}\n现{r['现货']:.0f} / 期{r['期货']:.0f}" for r in rows]
    rates = [r["基差率"] for r in rows]
    colors = [UP_COLOR if v >= 0 else DOWN_COLOR for v in rates]
    bars = ax.bar(names, rates, color=colors, width=0.55)
    ax.axhline(0, color="#888", linewidth=0.8)
    ax.set_ylabel("基差率 (%)（期货−现货）/现货")
    ax.set_title("股指期货 · 基差（现货指数 vs 主力合约）", fontsize=13, pad=10)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.tick_params(axis="x", labelsize=9)
    for b, r in zip(bars, rates):
        ax.text(b.get_x() + b.get_width() / 2, r, f"{r:+.2f}%", ha="center",
                va="bottom" if r >= 0 else "top", fontsize=10)


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else N_HIST
    date = latest_trade_date()

    cross = fetch_cross(date)
    hist = fetch_hist(n)
    idx_fut = fetch_index_futures()

    fig, axes = plt.subplots(2, 2, figsize=(16, 11))

    draw_cross(axes[0, 0], cross, "主力基差率",
               f"商品期货 · 主力基差率 TOP{N_CROSS}（期货 vs 现货）",
               "基差率 (%)（期货−现货）/现货")
    draw_cross(axes[0, 1], cross, "跨期价差率",
               f"商品期货 · 跨期价差率 TOP{N_CROSS}（近月 vs 远月）",
               "价差率 (%)（临近合约−主力）/主力")
    draw_hist(axes[1, 0], hist)
    draw_index(axes[1, 1], idx_fut)

    fig.suptitle(
        f"期货基差 / 跨期价差（数据日期 {date}，历史回溯 {n} 个交易日）　来源：24K-Claw",
        fontsize=16, fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"futures_basis_{date:%Y%m%d}.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"图表已保存: {out}")

    print(f"\n[商品期货 · 主力基差率 TOP5 期货升水]")
    print(cross.nlargest(5, "主力基差率")[["symbol", "名称", "spot_price",
          "dominant_contract", "dominant_contract_price", "主力基差率"]]
          .to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    print(f"\n[商品期货 · 主力基差率 TOP5 期货贴水]")
    print(cross.nsmallest(5, "主力基差率")[["symbol", "名称", "spot_price",
          "dominant_contract", "dominant_contract_price", "主力基差率"]]
          .to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    if idx_fut:
        print("\n[股指期货 · 基差]")
        for r in idx_fut:
            print(f"  {r['名称']:6s} {r['合约']:8s} 现货 {r['现货']:9.2f}  期货 {r['期货']:9.2f}  基差率 {r['基差率']:+.2f}%")


if __name__ == "__main__":
    main()
