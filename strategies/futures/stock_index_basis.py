# -*- coding: utf-8 -*-
"""
股指期货期现基差与升贴水分析(IM / IF / IC)
====================================================================
功能说明:
  1. 通过 AKShare 拉取近 1 年数据:
       - 现货指数日线: IM->中证1000(000852) / IF->沪深300(000300) / IC->中证500(000905)
       - 期货当月连续日线: IM0 / IF0 / IC0 (新浪财经)
       - 四个挂牌合约(当月/次月/当季/次季)最新行情, 用于期限结构截面
  2. 计算指标:
       - 基差     = 现货收盘 - 期货收盘 (单位: 点)
       - 升贴水率 = (期货收盘 - 现货收盘) / 现货收盘 × 100%
                    (负值 = 期货贴水, 正值 = 期货升水, 与主流行情软件口径一致)
  3. 每个品种输出一张 PNG 大图(3 个子图):
       - 左上: 基差(点数)近 1 年走势, 标注零轴与最新值、区间统计
       - 右上: 升贴水率(%)近 1 年走势, 标注零轴、区间均值与最新值
       - 下方: 最新截面期限结构 —— 当月/次月/当季/次季四个合约升贴水率柱状图
      图表配色与字体遵循项目 OMMQ 规范(红#F36/绿#0C9/蓝#99F/黄#FC3/字体色#27254c);
      底部脚注为基于最新数据的自动生成专业解读(升贴水状态/基差分位/期限结构形态)。
依赖: pip install akshare pandas matplotlib
用法: python stock_index_basis.py [可选: 历史天数, 默认366]
输出: 项目根目录 reports/YYYYMMDD/ 文件夹(按运行日期归档)
"""
import datetime as dt
import sys
from pathlib import Path
import akshare as ak
import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
# ==================== 可修改配置 ====================
HISTORY_DAYS = 366 # 历史区间: 近 1 年
# 图表铁律: 所有图表产物归档至 reports/日期/ 目录(与收盘报告同规范)
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "reports" / dt.date.today().strftime("%Y%m%d")
PRODUCTS = {                           # 期货代码 -> (品种名, 现货指数代码)
    "IM": ("中证1000", "000852"),
    "IF": ("沪深300", "000300"),
    "IC": ("中证500", "000905"),
}
# ===================================================
COL_BLUE, COL_YELLOW, COL_RED, COL_GREEN, COL_GRAY = (
    "#99F", "#FC3", "#F36", "#0C9", "#bbb")
matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
matplotlib.rcParams["axes.unicode_minus"] = False
matplotlib.rcParams["text.color"] = "#27254c"
matplotlib.rcParams["axes.labelcolor"] = "#27254c"
matplotlib.rcParams["axes.titlecolor"] = "#27254c"
matplotlib.rcParams["xtick.color"] = "#27254c"
matplotlib.rcParams["ytick.color"] = "#27254c"
# -------------------- 数据获取 --------------------
def _norm_daily(df: pd.DataFrame) -> pd.DataFrame:
    """把不同接口返回的日线数据统一成 [date, close] 两列。"""
    date_col = next((c for c in ("日期", "date", "交易日") if c in df.columns), None)
    close_col = next((c for c in ("收盘价", "收盘", "close") if c in df.columns), None)
    if date_col is None or close_col is None:
        raise ValueError(f"无法识别日期/收盘价列, 实际列: {list(df.columns)}")
    out = pd.DataFrame({
        "date": pd.to_datetime(df[date_col], errors="coerce").dt.date,
        "close": pd.to_numeric(df[close_col], errors="coerce"),
    })
    return out.dropna().sort_values("date").reset_index(drop=True)
def fetch_spot(index_code: str, start: dt.date, end: dt.date) -> pd.DataFrame:
    """现货指数日线: 优先东财 index_zh_a_hist, 失败则退回新浪 stock_zh_index_daily。"""
    start_s, end_s = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    try:
        df = ak.index_zh_a_hist(symbol=index_code, period="daily",
                                start_date=start_s, end_date=end_s)
        return _norm_daily(df)
    except Exception:
        pass
    df = ak.stock_zh_index_daily(symbol="sh" + index_code)
    out = _norm_daily(df)
    return out[(out["date"] >= start) & (out["date"] <= end)].reset_index(drop=True)
def fetch_fut_continuous(product: str, start: dt.date, end: dt.date) -> pd.DataFrame:
    """期货当月连续日线(新浪: IM0/IF0/IC0)。兼容不同 akshare 版本的参数。"""
    try:
        df = ak.futures_main_sina(symbol=product + "0",
                                  start_date=start.strftime("%Y%m%d"),
                                  end_date=end.strftime("%Y%m%d"))
    except TypeError:
        df = ak.futures_main_sina(symbol=product + "0")
    out = _norm_daily(df)
    return out[(out["date"] >= start) & (out["date"] <= end)].reset_index(drop=True)

def third_friday(year: int, month: int) -> dt.date:
    """合约到期日: 当月第三个周五。"""
    d = dt.date(year, month, 1)
    return d + dt.timedelta(days=(4 - d.weekday()) % 7 + 14)   # 周五=4

def cffex_contracts(today: dt.date = None):
    """推导中金所挂牌的四个合约(当月/次月/随后两个季月), 返回 [(角色, (年, 月)), ...]"""
    today = today or dt.date.today()
    months, y, m = [], today.year, today.month
    for i in range(15):
        mm = m + i
        months.append((y + (mm - 1) // 12, (mm - 1) % 12 + 1))
    m1 = next(ym for ym in months if third_friday(*ym) >= today)   # 当月
    m2 = months[months.index(m1) + 1]                              # 次月
    quarters = [ym for ym in months                                # 其后两个季月
                if ym[1] in (3, 6, 9, 12) and third_friday(*ym) > third_friday(*m2)]
    return [("当月", m1), ("次月", m2), ("当季", quarters[0]), ("次季", quarters[1])]

def fetch_contract_snapshot(product: str, spot_last_date: dt.date):
    """四个挂牌合约的最新收盘价, 用于期限结构截面。"""
    rows = []
    for role, (y, m) in cffex_contracts():
        code = f"{product}{y % 100:02d}{m:02d}"
        try:
            nd = _norm_daily(ak.futures_zh_daily_sina(symbol=code))
            if nd.empty:
                raise ValueError("无行情数据")
            row = nd[nd["date"] == spot_last_date]      # 尽量与现货最新交易日对齐
            row = row if not row.empty else nd.tail(1)
            r = row.iloc[-1]
            rows.append({"role": role, "code": code, "date": r["date"],
                         "close": float(r["close"]), "expiry": third_friday(y, m)})
        except Exception as e:
            print(f"  [警告] 合约 {code} 行情获取失败: {e}")
    return rows

# -------------------- 绘图 --------------------
def _fmt_date_axis(ax):
    loc = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(loc)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))
def _professional_comment(name: str, basis: pd.Series, prem: pd.Series,
                          vols: list) -> str:
    """基于最新数据自动生成底部专业解读(升贴水状态/基差分位/期限结构形态)。"""
    p_last = float(prem.iloc[-1])
    state = "贴水" if p_last < 0 else "升水"
    pct_pos = float((basis <= basis.iloc[-1]).mean() * 100)
    pos = "低位" if pct_pos <= 20 else ("高位" if pct_pos >= 80 else "中位")

    if len(vols) >= 2:
        near, far = vols[0], vols[-1]
        if far < near - 0.05:
            term = "期限结构上远月贴水逐级加深，对冲需求偏高、市场对远期偏谨慎"
        elif far > near + 0.05:
            term = "期限结构上远月贴水收敛、近低远高，市场远期情绪偏暖"
        else:
            term = "期限结构近远月贴水接近平坦，暂缺乏方向性预期"
    else:
        term = "期限结构数据缺失，暂不评估"
    if p_last < 0:
        hint = ("贴水结构对多头移仓成本友好" if pct_pos > 20 else
                "深贴水叠加基差低位，空头拥挤度偏高，关注均值回归修复机会")
    else:
        hint = "升水结构下多头占优，但需留意情绪过热后的回吐风险"

    return (f"专业解读: {name}当前{state} {p_last:+.2f}%（基差 {basis.iloc[-1]:+.1f} 点，"
            f"处近1年{pos}、{pct_pos:.0f}% 分位）；{term}；{hint}")
def _annotate_latest(ax, x, y, text, color):
    """在序列末端标注最新值。"""
    ax.scatter([x], [y], s=26, color=color, zorder=5)
    ax.annotate(text, xy=(x, y), xytext=(8, 10), textcoords="offset points",
                fontsize=9, color=color, fontweight="bold")
def plot_product(product: str, name: str, merged: pd.DataFrame,
                 contracts: list, spot_last_date: dt.date, out_path: Path):
    """单个品种一张大图: 基差走势 + 升贴水率走势 + 期限结构。"""
    basis = merged["basis"]
    prem = merged["prem"]
    dates = merged["date"]
    spot_last = float(merged["close_spot"].iloc[-1])
    fig = plt.figure(figsize=(14, 10), constrained_layout=True)
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.05])
    ax1 = fig.add_subplot(gs[0, 0])     # 基差(点数)
    ax2 = fig.add_subplot(gs[0, 1])     # 升贴水率(%)
    ax3 = fig.add_subplot(gs[1, :])     # 期限结构
    # ---- 子图1: 基差走势(点数) ----
    ax1.fill_between(dates, basis, 0, color=COL_BLUE, alpha=0.10)
    ax1.plot(dates, basis, color=COL_BLUE, lw=1.5)
    ax1.axhline(0, color=COL_GRAY, lw=1, ls="--")
    ax1.set_title("基差走势(现货 - 期货, 点数)", fontsize=12, loc="left")
    ax1.set_ylabel("基差(点)")
    stats = (f"均值 {basis.mean():+.1f} 点   最大 {basis.max():+.1f}   最小 {basis.min():+.1f}\n"
             f"最新 {basis.iloc[-1]:+.1f} 点   近1年分位 {(basis <= basis.iloc[-1]).mean() * 100:.0f}%")
    ax1.text(0.02, 0.96, stats, transform=ax1.transAxes, va="top", fontsize=9,
             bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#bbb", alpha=0.9))
    _annotate_latest(ax1, dates.iloc[-1], basis.iloc[-1],
                     f"{basis.iloc[-1]:+.1f}", COL_BLUE)
    ax1.grid(axis="y", alpha=0.25)
    _fmt_date_axis(ax1)
    # ---- 子图2: 升贴水率走势(%) ----
    ax2.plot(dates, prem, color=COL_YELLOW, lw=1.5)
    ax2.axhline(0, color=COL_GRAY, lw=1)
    mean_v = prem.mean()
    ax2.axhline(mean_v, color=COL_YELLOW, lw=1, ls="--", alpha=0.8)
    ax2.text(dates.iloc[0], mean_v, f"  均值 {mean_v:+.2f}%", fontsize=8.5,
             color=COL_YELLOW, va="bottom",
             bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75))
    ax2.set_title("升贴水率走势((期货-现货)/现货, %)  负值=贴水 / 正值=升水",
                  fontsize=12, loc="left")
    ax2.set_ylabel("升贴水率(%)")
    _annotate_latest(ax2, dates.iloc[-1], prem.iloc[-1],
                     f"{prem.iloc[-1]:+.2f}%", COL_YELLOW)
    ax2.grid(axis="y", alpha=0.25)
    _fmt_date_axis(ax2)

    # ---- 子图3: 期限结构(最新截面) ----
    if contracts:
        vols = [(c["close"] - spot_last) / spot_last * 100 for c in contracts]
        bases = [spot_last - c["close"] for c in contracts]
        colors = [COL_RED if v >= 0 else COL_GREEN for v in vols]
        x = list(range(len(contracts)))
        ax3.bar(x, vols, width=0.52, color=colors, alpha=0.85)
        ax3.axhline(0, color=COL_GRAY, lw=1)
        span = max(vols + [0]) - min(vols + [0])
        pad = max(span, 0.2) * 0.045
        for i, (v, bp, col) in enumerate(zip(vols, bases, colors)):
            ax3.text(i, v + (pad if v >= 0 else -pad),
                     f"{v:+.2f}%\n({bp:+.0f}点)", ha="center",
                     va="bottom" if v >= 0 else "top",
                     fontsize=9.5, color=col, fontweight="bold")
        ax3.set_ylim(min(vols + [0]) - span * 0.4, max(vols + [0]) + span * 0.4)
        labels = [f"{c['role']} {c['code']}\n剩余{(c['expiry'] - spot_last_date).days}天"
                  for c in contracts]
        ax3.set_xticks(x)
        ax3.set_xticklabels(labels, fontsize=9.5)
        ax3.set_ylabel("升贴水率(%)")
        ax3.set_title(f"期限结构(最新截面, 现货收盘 {spot_last:.2f} @ {spot_last_date})",
                      fontsize=12, loc="left")
        ax3.grid(axis="y", alpha=0.25)

    # ---- 总标题与脚注(自动专业解读) ----
    fig.suptitle(f"{name}股指期货({product}) 期现基差与升贴水分析   "
                 f"区间 {dates.iloc[0]} ~ {dates.iloc[-1]}   来源：OMMQ",
                 fontsize=15, fontweight="bold")
    vols = [(c["close"] - spot_last) / spot_last * 100 for c in contracts] \
        if contracts else []
    fig.supxlabel(_professional_comment(name, basis, prem, vols),
                  fontsize=9, color="#27254c")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# -------------------- 主流程 --------------------
def analyze_product(product: str, name: str, index_code: str,
                    start: dt.date, end: dt.date) -> dict:
    print(f"\n>>> 正在处理 {product}({name}, 现货 {index_code}) ...")
    spot = fetch_spot(index_code, start, end)
    fut = fetch_fut_continuous(product, start, end)
    if spot.empty or fut.empty:
        raise RuntimeError("现货或期货数据为空, 请检查网络连接")

    merged = pd.merge(spot.rename(columns={"close": "close_spot"}),
                      fut.rename(columns={"close": "close_fut"}), on="date")
    merged = merged.dropna().sort_values("date").reset_index(drop=True)
    merged["basis"] = merged["close_spot"] - merged["close_fut"]                # 基差(点)
    merged["prem"] = (merged["close_fut"] - merged["close_spot"]) \
        / merged["close_spot"] * 100                                            # 升贴水率(%)

    contracts = fetch_contract_snapshot(product, merged["date"].iloc[-1])

    out_path = OUTPUT_DIR / f"{product}_{name}_基差分析.png"
    plot_product(product, name, merged, contracts,
                 merged["date"].iloc[-1], out_path)
    print(f"    已保存: {out_path}")

    return {"品种": product, "现货指数": name,
            "最新交易日": merged["date"].iloc[-1],
            "现货收盘": round(float(merged["close_spot"].iloc[-1]), 2),
            "期货收盘": round(float(merged["close_fut"].iloc[-1]), 2),
            "基差(点)": round(float(merged["basis"].iloc[-1]), 1),
            "升贴水率(%)": round(float(merged["prem"].iloc[-1]), 3),
            "近1年基差均值": round(float(merged["basis"].mean()), 1),
            "近1年基差最小": round(float(merged["basis"].min()), 1),
            "近1年基差最大": round(float(merged["basis"].max()), 1)}


def main():
    global HISTORY_DAYS
    if len(sys.argv) > 1:                       # 可选参数: 历史天数
        HISTORY_DAYS = int(sys.argv[1])
    end, start = dt.date.today(), dt.date.today() - dt.timedelta(days=HISTORY_DAYS)

    print(f"数据区间: {start} ~ {end}(共 {HISTORY_DAYS} 天)")

    summaries = []
    for product, (name, index_code) in PRODUCTS.items():
        try:
            summaries.append(analyze_product(product, name, index_code, start, end))
        except Exception as e:
            print(f"[错误] {product} 分析失败: {e}")

    if summaries:
        print("\n========== 基差分析汇总(升贴水率=期货-现货/现货, 负=贴水、正=升水) ==========")
        print(pd.DataFrame(summaries).to_string(index=False))
    print(f"\n全部图表已输出至: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
