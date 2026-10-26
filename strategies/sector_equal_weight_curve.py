# -*- coding: utf-8 -*-
"""自定义板块等权收益曲线与最大回撤（近 N 年）

做什么：
    1. 读取通达信自定义板块成分（默认 XFLT 细分龙头）；
    2. 批量拉取成分股近 N 年日线后复权收盘价；
    3. 按“每日等权再平衡”合成板块等权净值，并计算最大回撤；
    4. 输出净值/回撤 CSV、收益-回撤双面板图与 Markdown 简报。

口径：
    - 个股收益 = 后复权收盘价日收益率，已包含分红送转；
    - 组合日收益 = 当日所有可交易成分股日收益的算术平均（等权、每日再平衡）；
    - 另附“等权静态持有”曲线作对照；
    - 基准 = 中证全指（000985.CSI）；
    - 不计交易成本、印花税、冲击成本；
    - 按“当前”板块成分回溯，存在幸存者偏差，结果偏乐观。

用法：
    python strategies/sector_equal_weight_curve.py
    python strategies/sector_equal_weight_curve.py --block XFLT --name 细分龙头 --years 5
    python strategies/sector_equal_weight_curve.py --end 20261026 --refresh
"""

from __future__ import annotations

import argparse
import os
import pickle
import sys
import time
import warnings

import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter
from plot_paths import report_dir, report_image_path

warnings.filterwarnings("ignore")

matplotlib.rcParams["font.sans-serif"] = [
    "Microsoft YaHei", "SimHei",           # Windows
    "PingFang SC", "Hiragino Sans GB",     # macOS
    "Arial Unicode MS",
]
matplotlib.rcParams["axes.unicode_minus"] = False
matplotlib.rcParams["text.color"] = "#27254c"
matplotlib.rcParams["axes.labelcolor"] = "#27254c"
matplotlib.rcParams["axes.titlecolor"] = "#27254c"
matplotlib.rcParams["xtick.color"] = "#27254c"
matplotlib.rcParams["ytick.color"] = "#27254c"

UP_COLOR = "#F36"      # 涨 / 组合
DOWN_COLOR = "#0C9"    # 跌 / 回撤
BENCH_COLOR = "#99F"   # 基准
BUYHOLD_COLOR = "#F2A93B"

CACHE_DIR = ".cache"
BENCH_CODE = "000985.CSI"
BENCH_NAME = "中证全指"


# ---------------------------------------------------------------------------
# 通达信环境
# ---------------------------------------------------------------------------
def _tdx_user_path() -> str:
    """定位 tqcenter.py 所在目录：注册表 → 常见安装路径。"""
    try:
        import winreg

        keys = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\通达信金融终端64",
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\通达信专业版",
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\通达信金融终端(量化模拟)",
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\通达信金融终端(测试)",
        ]
        for key in keys:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as k:
                    root, _ = winreg.QueryValueEx(k, "InstallLocation")
                p = os.path.join(root, "PYPlugins", "user")
                if os.path.exists(os.path.join(p, "tqcenter.py")):
                    return p
            except FileNotFoundError:
                continue
    except Exception:
        pass

    for root in (r"C:\new_tdxqh", r"C:\new_tdx", r"D:\new_tdx", r"E:\new_tdx"):
        p = os.path.join(root, "PYPlugins", "user")
        if os.path.exists(os.path.join(p, "tqcenter.py")):
            return p
    raise FileNotFoundError("未找到通达信 PYPlugins/user/tqcenter.py，请检查安装目录。")


sys.path.insert(0, _tdx_user_path())
from tqcenter import tq  # noqa: E402


# ---------------------------------------------------------------------------
# 数据拉取
# ---------------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="自定义板块等权收益曲线与最大回撤")
    p.add_argument("--block", default="XFLT", help="自定义板块简称，默认 XFLT")
    p.add_argument("--name", default="细分龙头", help="板块中文名，用于图表标题")
    p.add_argument("--years", type=float, default=5.0, help="回溯年数，默认 5")
    p.add_argument("--end", default="", help="结束日 YYYYMMDD，默认今天")
    p.add_argument("--refresh", action="store_true", help="忽略本地缓存，重新拉数")
    p.add_argument("--batch", type=int, default=100, help="单次请求股票数，默认 100")
    return p.parse_args()


def _get_members(block: str) -> tuple[list[str], dict[str, str]]:
    """返回 (代码列表, 代码->名称)。"""
    try:
        raw = tq.get_stock_list_in_sector(block, block_type=1, list_type=1)
        names = {x["Code"]: x["Name"] for x in raw if isinstance(x, dict)}
        codes = list(names)
    except Exception:
        codes = tq.get_stock_list_in_sector(block, block_type=1)
        names = {}
    codes = list(dict.fromkeys(codes))
    return codes, names


def _fetch_close(codes: list[str], start: str, end: str,
                 batch: int = 100) -> tuple[pd.DataFrame, list[str]]:
    """批量拉取后复权日收盘，返回 (日期×代码 矩阵, 失败代码)。"""
    frames: list[pd.DataFrame] = []
    failed: list[str] = []
    total = len(codes)
    t0 = time.time()

    for i in range(0, total, batch):
        part = codes[i:i + batch]
        df = None
        for attempt in range(3):
            try:
                data = tq.get_market_data(
                    field_list=["Close"], stock_list=part, period="1d",
                    start_time=start, end_time=end,
                    dividend_type="back", fill_data=True,
                )
                df = data.get("Close")
                if df is not None and not df.empty:
                    break
            except Exception as exc:  # 网络/接口抖动
                if attempt == 2:
                    print(f"  [警告] 批次 {i}-{i + len(part)} 失败: {exc}")
            time.sleep(0.5)

        if df is None or df.empty:
            failed.extend(part)
        else:
            df.index = pd.to_datetime(df.index)
            frames.append(df)
            got = set(df.columns)
            failed.extend([c for c in part if c not in got])

        done = min(i + batch, total)
        elapsed = time.time() - t0
        print(f"  拉取进度 {done}/{total}  ({elapsed:.0f}s)", flush=True)

    if not frames:
        raise RuntimeError("全部行情拉取失败，请检查通达信客户端与数据下载状态。")

    close = pd.concat(frames, axis=1).sort_index()
    close = close.loc[:, ~close.columns.duplicated()]
    return close.astype(float), failed


def _load_data(block: str, name: str, codes: list[str], names: dict[str, str],
               fetch_start: str, end: str, batch: int,
               refresh: bool) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """带缓存地拉取成分股与基准收盘价。"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    tag = f"{block}_{fetch_start}_{end}"
    cache = os.path.join(CACHE_DIR, f"{tag}.pkl")

    if not refresh:
        candidates = []
        if os.path.exists(cache):
            candidates.append(cache)
        # 复用区间更长的同板块缓存（旧缓存起点更早、终点不早于本次即可）
        for fn in os.listdir(CACHE_DIR):
            if not (fn.startswith(f"{block}_") and fn.endswith(".pkl")):
                continue
            stem = fn[len(block) + 1:-4]
            try:
                c_start, c_end = stem.split("_")
            except ValueError:
                continue
            if c_start <= fetch_start and c_end >= end:
                candidates.append(os.path.join(CACHE_DIR, fn))

        for path in dict.fromkeys(candidates):
            with open(path, "rb") as f:
                obj = pickle.load(f)
            if obj.get("codes") == codes:
                print(f"[缓存] {path}  （{obj['close'].shape[1]} 只股票）")
                return obj["close"], obj["bench"], obj["failed"]

    print(f"[拉取] {name}（{block}）成分股 {len(codes)} 只，"
          f"区间 {fetch_start} ~ {end} ...")
    close, failed = _fetch_close(codes, fetch_start, end, batch=batch)

    print(f"[拉取] 基准 {BENCH_NAME}（{BENCH_CODE}）...")
    bench = _fetch_close([BENCH_CODE], fetch_start, end, batch=1)[0]

    with open(cache, "wb") as f:
        pickle.dump({"codes": codes, "names": names, "close": close,
                     "bench": bench, "failed": failed}, f)
    print(f"[缓存] 已写入 {cache}")
    return close, bench, failed


# ---------------------------------------------------------------------------
# 组合与指标
# ---------------------------------------------------------------------------
def _stats(nav: pd.Series) -> dict:
    nav = nav.dropna()
    ret = nav.pct_change(fill_method=None).dropna()
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    total = nav.iloc[-1] / nav.iloc[0] - 1.0
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1 / years) - 1.0 if years > 0 else np.nan
    vol = ret.std() * np.sqrt(252)
    sharpe = ret.mean() * 252 / vol if vol > 0 else np.nan

    dd = nav / nav.cummax() - 1.0
    trough = dd.idxmin()
    mdd = float(dd.loc[trough])
    peak_val = nav.loc[:trough].max()
    peak = nav.loc[:trough][nav.loc[:trough] == peak_val].index[-1]
    after = nav.loc[trough:]
    recovered = after[after >= peak_val]
    recovery = recovered.index[0] if len(recovered) else pd.NaT

    return {
        "total": total, "cagr": cagr, "vol": vol, "sharpe": sharpe,
        "mdd": mdd, "peak": peak, "trough": trough, "recovery": recovery,
        "current_dd": float(dd.iloc[-1]), "dd": dd,
        "win_rate": float((ret > 0).mean()),
        "best": float(ret.max()), "worst": float(ret.min()),
        "years": years,
    }


def _annual_returns(nav: pd.Series) -> pd.Series:
    out = {}
    for year in sorted(set(nav.index.year)):
        end_val = nav.loc[nav.index.year == year].iloc[-1]
        prev = nav.loc[nav.index < pd.Timestamp(year=year, month=1, day=1)]
        start_val = prev.iloc[-1] if len(prev) else 1.0
        out[year] = end_val / start_val - 1.0
    return pd.Series(out, dtype=float)


def _build_portfolio(close: pd.DataFrame, bench: pd.DataFrame,
                     base_date: pd.Timestamp, end: pd.Timestamp) -> dict:
    px = close.sort_index().apply(pd.to_numeric, errors="coerce")
    px = px.mask(px <= 0)
    px = px.loc[:, px.notna().sum() >= 5]

    cal = px.index.union(bench.index).sort_values()
    cal = cal[(cal >= base_date) & (cal <= end)]
    px = px.reindex(cal)

    # 前向填充停牌日；最后有效日之后置空，视为退出组合
    px_ff = px.ffill()
    last_valid = px.apply(lambda s: s.last_valid_index())
    for c in px.columns:
        if pd.notna(last_valid[c]):
            px_ff.loc[px_ff.index > last_valid[c], c] = np.nan

    ret = px_ff.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    ret = ret.mask(ret.abs() > 5.0)  # >500%/日 视为异常数据

    coverage = ret.notna().sum(axis=1)
    port_ret = ret.mean(axis=1).where(coverage >= 50)

    nav = pd.concat([
        pd.Series(1.0, index=[base_date]),
        (1.0 + port_ret.fillna(0.0)).cumprod(),
    ])
    nav = nav[~nav.index.duplicated(keep="first")]

    # 等权静态持有对照：老股以基准日收盘为成本，新股以上市首日为成本
    base_px = px.loc[base_date].copy()
    for c in px.columns:
        if pd.isna(base_px[c]):
            fv = px[c].first_valid_index()
            if fv is not None:
                base_px[c] = px[c].loc[fv]
    norm = px.divide(base_px, axis=1) - 1.0
    bh_nav = (1.0 + norm.mean(axis=1)).reindex(nav.index)

    bench_px = bench.reindex(cal).ffill()[BENCH_CODE]
    bench_nav = (bench_px / bench_px.loc[base_date]).reindex(nav.index)

    return {
        "nav": nav, "bh_nav": bh_nav, "bench_nav": bench_nav,
        "ret": port_ret.reindex(nav.index[1:]),
        "coverage": coverage.reindex(nav.index[1:]),
        "px": px,
    }


# ---------------------------------------------------------------------------
# 图表
# ---------------------------------------------------------------------------
def _plot(result: dict, stats: dict, block: str, name: str,
          n_members: int, n_used: int, path: str) -> None:
    nav = result["nav"] * 100 - 100
    bh = result["bh_nav"] * 100 - 100
    bench = result["bench_nav"] * 100 - 100
    dd = stats["dd"] * 100

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 9.2), sharex=True,
        gridspec_kw={"height_ratios": [3.1, 1.5], "hspace": 0.08},
    )

    # 回撤区间底色
    peak, trough = stats["peak"], stats["trough"]
    rec = stats["recovery"] if pd.notna(stats["recovery"]) else nav.index[-1]
    ax1.axvspan(peak, rec, color=DOWN_COLOR, alpha=0.05, zorder=0)

    ax1.plot(nav.index, nav.values, color=UP_COLOR, lw=2.3, zorder=5,
             label=f"{name}等权（每日再平衡）")
    ax1.plot(bh.index, bh.values, color=BUYHOLD_COLOR, lw=1.2, ls="--",
             alpha=0.9, zorder=4, label="等权静态持有（对照）")
    ax1.plot(bench.index, bench.values, color=BENCH_COLOR, lw=1.5,
             zorder=3, label=f"{BENCH_NAME}（基准）")
    ax1.axhline(0, color="#aaaaaa", lw=0.9, ls="--", zorder=1)

    for s, color in ((nav, UP_COLOR), (bench, BENCH_COLOR), (bh, BUYHOLD_COLOR)):
        ax1.annotate(
            f"{s.iloc[-1]:+.1f}%", xy=(s.index[-1], s.iloc[-1]),
            xytext=(7, 0), textcoords="offset points", color=color,
            fontsize=10, fontweight="bold", va="center",
        )

    # 最大回撤标注
    ax1.plot([peak, trough], [nav.loc[peak], nav.loc[trough]],
             color=DOWN_COLOR, lw=1.0, ls=":", zorder=6)
    ax1.scatter([peak], [nav.loc[peak]], color="#27254c", s=28, zorder=7)
    ax1.scatter([trough], [nav.loc[trough]], color=DOWN_COLOR, s=42, zorder=7)
    span = float(nav.max() - nav.min())
    ax1.annotate(
        f"最大回撤 {stats['mdd']:.1%}\n{peak:%Y-%m-%d} → {trough:%Y-%m-%d}",
        xy=(trough, nav.loc[trough]),
        xytext=(peak + pd.Timedelta(days=120), float(nav.max() - span * 0.40)),
        textcoords="data", fontsize=9.5, color="#27254c",
        bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=DOWN_COLOR,
                  lw=0.8, alpha=0.92),
        arrowprops=dict(arrowstyle="-", color=DOWN_COLOR, lw=0.8,
                        connectionstyle="arc3,rad=-0.18"),
    )

    ax1.set_ylabel("累计收益（%）", fontsize=11)
    ax1.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.0f}%"))
    ax1.grid(linestyle="--", alpha=0.3)
    ax1.legend(loc="upper left", fontsize=9.5, framealpha=0.9)

    subtitle = (
        f"累计 {stats['total']:+.1%}｜年化 {stats['cagr']:+.1%}｜"
        f"年化波动 {stats['vol']:.1%}｜夏普 {stats['sharpe']:.2f}｜"
        f"最大回撤 {stats['mdd']:.1%}｜成分股 {n_members} 只"
    )
    if n_used < n_members:
        subtitle += f"（有行情 {n_used} 只）"
    fig.suptitle(f"{name}（{block}）等权组合 · 近 {stats['years']:.0f} 年累计收益",
                 fontsize=15, fontweight="bold", y=0.975)
    fig.text(0.5, 0.938, subtitle, ha="center", fontsize=10.2, color="#4a5568")

    # 回撤面板
    ax2.fill_between(dd.index, dd.values, 0, color=DOWN_COLOR, alpha=0.22)
    ax2.plot(dd.index, dd.values, color=DOWN_COLOR, lw=1.4)
    ax2.axhline(stats["mdd"] * 100, color="#078f6e", lw=1.0, ls="--")
    ax2.scatter([trough], [stats["mdd"] * 100], color="#078f6e", s=45, zorder=5)
    ax2.annotate(
        f"{stats['mdd']:.1%}", xy=(trough, stats["mdd"] * 100),
        xytext=(8, -12), textcoords="offset points", fontsize=9.5,
        color="#078f6e", fontweight="bold",
    )
    ax2.set_ylabel("回撤（%）", fontsize=11)
    ax2.set_ylim(min(stats["mdd"] * 100 * 1.18, -1.0), 2.0)
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.0f}%"))
    ax2.grid(linestyle="--", alpha=0.3)

    ax2.xaxis.set_major_locator(mdates.YearLocator())
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax2.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[4, 7, 10]))
    ax2.tick_params(axis="x", labelsize=10)

    fig.text(
        0.5, 0.015,
        "数据来源：通达信 TdxQuant（后复权收盘价）｜口径：每日等权再平衡，不计交易成本｜"
        "注：按当前板块成分回溯，存在幸存者偏差，历史收益偏乐观",
        ha="center", fontsize=8.8, color="#7a8291",
    )
    fig.tight_layout(rect=(0, 0.035, 1, 0.915))
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"\n图表已保存: {path}")


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------
def _write_report(result: dict, stats: dict, bh_stats: dict, bench_stats: dict,
                  annual: pd.DataFrame, block: str, name: str,
                  n_members: int, n_used: int, failed: list[str],
                  image_name: str, csv_name: str) -> str:
    nav = result["nav"]
    peak, trough, rec = stats["peak"], stats["trough"], stats["recovery"]
    rec_txt = f"{rec:%Y-%m-%d}" if pd.notna(rec) else "尚未修复"
    first_valid = result["px"].apply(lambda s: s.first_valid_index()).dropna()
    n_new = int((pd.to_datetime(first_valid) > nav.index[0]).sum())

    def row(label: str, a: float, b: float, c: float,
            pct: bool = True, signed: bool = True) -> str:
        if pct:
            f = (lambda x: f"{x:+.2%}") if signed else (lambda x: f"{x:.2%}")
        else:
            f = lambda x: f"{x:.2f}"
        return f"| {label} | {f(a)} | {f(b)} | {f(c)} |"

    md = [
        f"# {name}（{block}）等权组合 · 近{stats['years']:.0f}年收益与最大回撤",
        "",
        f"**统计区间**：{nav.index[0]:%Y-%m-%d}（基准日）~ {nav.index[-1]:%Y-%m-%d}，"
        f"共 {stats['years']:.2f} 年",
        "",
        f"**成分股**：{n_members} 只（区间内新上市 {n_new} 只），"
        f"区间内取得行情 {n_used} 只"
        + (f"，拉取失败 {len(failed)} 只" if failed else ""),
        "",
        "**构建方式**：等权、每日收盘再平衡；个股按通达信后复权收盘价计算收益"
        "（含分红送转）；不计交易成本、印花税与冲击成本。"
        f"基准为{BENCH_NAME}（{BENCH_CODE}）。",
        "",
        f"![{name}等权收益与回撤](./{image_name})",
        "",
        "## 核心指标",
        "",
        f"| 指标 | {name}等权 | 等权静态持有 | {BENCH_NAME} |",
        "|---|---:|---:|---:|",
        row("累计收益", stats["total"], bh_stats["total"], bench_stats["total"]),
        row("年化收益", stats["cagr"], bh_stats["cagr"], bench_stats["cagr"]),
        row("年化波动", stats["vol"], bh_stats["vol"], bench_stats["vol"], signed=False),
        row("夏普比率", stats["sharpe"], bh_stats["sharpe"], bench_stats["sharpe"], pct=False),
        row("最大回撤", stats["mdd"], bh_stats["mdd"], bench_stats["mdd"]),
        row("当前回撤", stats["current_dd"], bh_stats["current_dd"], bench_stats["current_dd"]),
        row("日胜率", stats["win_rate"], bh_stats["win_rate"], bench_stats["win_rate"],
            signed=False),
        "",
        "## 年度收益",
        "",
        "| 年度 | 等权组合 | 等权静态持有 | 中证全指 |",
        "|---|---:|---:|---:|",
    ]
    for year, v in annual.iterrows():
        md.append(f"| {year} | {v['port']:+.2%} | {v['bh']:+.2%} | {v['bench']:+.2%} |")

    first_year, last_year = nav.index[0].year, nav.index[-1].year
    partial = []
    if nav.index[0] > pd.Timestamp(year=first_year, month=1, day=1):
        partial.append(f"{first_year} 年为 {nav.index[0]:%m-%d} 至年末")
    if nav.index[-1] < pd.Timestamp(year=last_year, month=12, day=31):
        partial.append(f"{last_year} 年为年初至 {nav.index[-1]:%m-%d}")

    md += [
        "",
        f"*注：{'，'.join(partial)}，均为不完整年度。*" if partial else "",
        "",
        "## 最大回撤明细",
        "",
        f"- **最大回撤**：{stats['mdd']:.2%}",
        f"- **峰值日**：{peak:%Y-%m-%d}（净值 {nav.loc[peak]:.4f}）",
        f"- **谷底日**：{trough:%Y-%m-%d}（净值 {nav.loc[trough]:.4f}）",
        f"- **修复日**：{rec_txt}",
        f"- **当前回撤**：{stats['current_dd']:.2%}",
        f"- **单日最佳 / 最差**：{stats['best']:+.2%} / {stats['worst']:+.2%}",
        "",
        "## 口径与风险提示",
        "",
        f"1. 组合按**当前**“{name}”板块成分回溯，历史上被调出或退市的个股不在样本中，"
        "存在**幸存者偏差与前视偏差**，历史收益大概率偏乐观。",
        f"2. 等权组合按每日收盘再平衡计算，{n_members} 只成分股每日再平衡在实盘中不可行，"
        "交易成本会显著侵蚀收益；静态持有曲线仅作对照（老股以基准日收盘等权买入，"
        "新股以上市首日收盘纳入）。",
        "3. 停牌股按停牌前收盘价冻结，复牌当日一次性体现区间涨跌；"
        "区间内停止交易的个股在最后有效日后退出组合。",
        "4. 后复权价格已包含分红送转，但除权处理以通达信数据为准；"
        "极端异常日收益（绝对值 >500%）已按缺失处理。",
        "",
        f"*数据与图表由 `strategies/sector_equal_weight_curve.py` 生成；"
        f"明细见 `{csv_name}`。*",
    ]

    out_dir = report_dir()
    years = int(round(stats["years"]))
    path = os.path.join(out_dir, f"{block}_equal_weight_{years}y_report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"简报已保存: {path}")
    return path


# ---------------------------------------------------------------------------
def main() -> None:
    args = _parse_args()
    end = pd.Timestamp(args.end) if args.end else pd.Timestamp.today().normalize()
    start = end - pd.DateOffset(years=args.years)
    fetch_start = (start - pd.Timedelta(days=35)).strftime("%Y%m%d")
    end_str = end.strftime("%Y%m%d")
    start_str = start.strftime("%Y%m%d")

    t0 = time.time()
    tq.initialize(__file__)
    try:
        codes, names = _get_members(args.block)
        print(f"板块 {args.name}（{args.block}）成分股 {len(codes)} 只")

        close, bench, failed = _load_data(
            args.block, args.name, codes, names, fetch_start, end_str,
            args.batch, args.refresh,
        )
    finally:
        tq.close()

    if close.empty:
        raise RuntimeError("未获取到任何成分股行情。")

    # 基准日：统计起点前的最后一个交易日
    bench_dates = pd.to_datetime(bench.index).sort_values()
    prior = bench_dates[bench_dates < start]
    if len(prior) == 0:
        raise RuntimeError("基准日前无行情，请扩大 fetch_start。")
    base_date = prior[-1]

    result = _build_portfolio(close, bench, base_date, end)
    nav, bh_nav, bench_nav = result["nav"], result["bh_nav"], result["bench_nav"]
    nav = nav.dropna()
    bh_nav = bh_nav.reindex(nav.index).ffill()
    bench_nav = bench_nav.reindex(nav.index).ffill()

    stats = _stats(nav)
    bh_stats = _stats(bh_nav)
    bench_stats = _stats(bench_nav)

    annual = pd.DataFrame({
        "port": _annual_returns(nav),
        "bh": _annual_returns(bh_nav),
        "bench": _annual_returns(bench_nav),
    })
    annual.index.name = "year"

    coverage = result["coverage"].reindex(nav.index[1:])
    px_used = result["px"]
    used = int(px_used.shape[1])
    last_valid = px_used.apply(lambda s: s.last_valid_index()).dropna()
    stopped = int((pd.to_datetime(last_valid) < end - pd.Timedelta(days=10)).sum())

    # 异常值诊断
    ret_all = px_used.pct_change(fill_method=None)
    n_big = int((ret_all.abs() > 0.5).to_numpy().sum())
    print(f"\n[数据] 成功股票 {used} 只 / 名单 {len(codes)} 只；"
          f"失败 {len(failed)} 只；区间内停止交易 {stopped} 只")
    print(f"[数据] 日收益绝对值 >50% 的样本：{n_big} 个")
    print(f"[数据] 日覆盖股票数：最小 {int(coverage.min())}，"
          f"中位 {int(coverage.median())}，最大 {int(coverage.max())}")

    print(f"\n[业绩] {start:%Y-%m-%d} ~ {end:%Y-%m-%d}  ({stats['years']:.2f} 年)")
    print(f"  等权组合   累计 {stats['total']:+.2%}  年化 {stats['cagr']:+.2%}  "
          f"波动 {stats['vol']:.2%}  夏普 {stats['sharpe']:.2f}  最大回撤 {stats['mdd']:.2%}")
    print(f"  静态持有   累计 {bh_stats['total']:+.2%}  年化 {bh_stats['cagr']:+.2%}  "
          f"波动 {bh_stats['vol']:.2%}  夏普 {bh_stats['sharpe']:.2f}  最大回撤 {bh_stats['mdd']:.2%}")
    print(f"  {BENCH_NAME}   累计 {bench_stats['total']:+.2%}  年化 {bench_stats['cagr']:+.2%}  "
          f"波动 {bench_stats['vol']:.2%}  夏普 {bench_stats['sharpe']:.2f}  最大回撤 {bench_stats['mdd']:.2%}")
    print(f"  最大回撤区间：{stats['peak']:%Y-%m-%d} → {stats['trough']:%Y-%m-%d}，"
          f"修复日 {stats['recovery']:%Y-%m-%d}" if pd.notna(stats["recovery"])
          else f"  最大回撤区间：{stats['peak']:%Y-%m-%d} → {stats['trough']:%Y-%m-%d}，尚未修复")

    print("\n[年度收益]")
    print("  年度    等权组合    静态持有    中证全指")
    for year, v in annual.iterrows():
        print(f"  {year}   {v['port']:+9.2%}  {v['bh']:+9.2%}  {v['bench']:+9.2%}")

    # 产物
    image_path = report_image_path(9, f"{args.block}_equal_weight_{int(round(args.years))}y")
    image_name = os.path.basename(image_path)
    _plot(result, stats, args.block, args.name,
          len(codes), used, image_path)

    csv_path = os.path.splitext(image_path)[0] + ".csv"
    out = pd.DataFrame({
        "date": nav.index,
        "nav": nav.values,
        "cum_return_pct": (nav.values - 1) * 100,
        "daily_return_pct": [np.nan] + (nav.pct_change().iloc[1:] * 100).tolist(),
        "drawdown_pct": stats["dd"].values * 100,
        "coverage": [np.nan] + coverage.tolist(),
        "nav_buyhold": bh_nav.values,
        "cum_return_buyhold_pct": (bh_nav.values - 1) * 100,
        f"nav_{BENCH_CODE}": bench_nav.values,
        "bench_cum_return_pct": (bench_nav.values - 1) * 100,
    })
    out.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"明细已保存: {csv_path}")

    _write_report(result, stats, bh_stats, bench_stats, annual, args.block,
                  args.name, len(codes), used, failed, image_name, os.path.basename(csv_path))
    print(f"\n总耗时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
