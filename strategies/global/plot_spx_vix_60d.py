# -*- coding: utf-8 -*-
"""标普500 近60个交易日累计收益(主图)+ VIX 恐慌指数(附图)
内容:
    主图:美股标普500指数近 N(默认60)个交易日累计收益曲线,区间首日归一化为 0%
    附图:同区间 VIX 收盘水平,标注 20 点警戒线、区间均值与最新情绪档位
    对齐:两图共用标普500交易日 x 轴;VIX 按同交易日对齐,个别缺失日向前填充
口径:价格指数口径(不含分红),累计收益 = 当日收盘 / 区间首日收盘 - 1
取数:标普500 新浪 → 东财;VIX CBOE 官网 → 雅虎(均按顺序降级,复用
      plot_global_indices_60d.py 的 fetch_index 重试/降级逻辑)
用法:.\\.venv\\Scripts\\python.exe strategies/global/plot_spx_vix_60d.py [交易日数]
      (交易日数默认60;复用上游取数链单次最多返回140个交易日,超出则按140天绘制并提示)
输出:reports/YYYYMMDD/27_spx_vix_60d.png(编号规则见 strategies/plot_paths.py)
依赖:akshare>=1.20  pandas  matplotlib  requests
"""

from __future__ import annotations

import io
import os
import sys
import warnings

import matplotlib

matplotlib.use("Agg")  # 只出图不弹窗；如需交互窗口可注释本行
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import requests

warnings.filterwarnings("ignore")

# 复用仓库共享模块:根目录 plot_utils 配色、strategies/plot_paths 编号、同目录脚本的降级取数
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, os.path.join(_ROOT, "strategies"), _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from plot_global_indices_60d import (_series, em_global, fetch_index, setup_font,
                                     sina_us, yahoo_chart)
from plot_paths import report_image_path
from plot_utils import DOWN_COLOR, UP_COLOR

# ════════════════════════ 可调参数 ════════════════════════
N_DAYS_DEFAULT = 60            # 交易日窗口长度(可用命令行参数覆盖)
OUT_NO         = 27            # 扩展图编号(09 起),见 strategies/plot_paths.py;17–20 属 trend_charts.py
OUT_AUX        = "spx_vix_60d"
VIX_ALERT      = 20.0          # VIX 警戒线:≥20 通常代表避险情绪升温
VIX_URL        = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
TEXT_C   = "#27254c"
TEXT_SOFT = "#73718b"
GRID_C   = "#C9C9D6"
VIX_C    = "#99F"
# ══════════════════════════════════════════════════════════


def cboe_vix() -> pd.Series:
    """CBOE 官网 VIX 全历史日线(CLOSE)。"""
    r = requests.get(VIX_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    return _series(df["DATE"], df["CLOSE"])


# ─── 取数清单 依次降级尝试 ───
SPX_STEPS = [("新浪", lambda: sina_us(".INX")),
             ("东财", lambda: em_global("标普500"))]
VIX_STEPS = [("CBOE", cboe_vix),
             ("雅虎", lambda: yahoo_chart("^VIX"))]


def mood(vix: float) -> str:
    """VIX 档位中文描述。"""
    if vix < 15:
        return "低波动"
    if vix < VIX_ALERT:
        return "温和偏谨慎"
    if vix < 30:
        return "避险升温"
    return "恐慌"


def align(target: pd.DatetimeIndex, series: pd.Series, name: str = "该序列") -> pd.Series:
    """把序列对齐到目标交易日:区间内缺失向前填充,首部缺失(上游行数不够)只能丢弃。"""
    out = series.reindex(target)
    lead = int(out.isna().cumprod().sum())
    filled = int(out.iloc[lead:].isna().sum())
    if filled:
        print(f"  [对齐] {name} 区间内{filled}个交易日无数据,已按前值填充")
    if lead:
        print(f"  [对齐] {name} 首部{lead}个交易日无数据(上游返回行数不足),附图起点后移")
    return out.iloc[lead:].ffill()


def plot(cum: pd.Series, vix: pd.Series | None) -> str:
    dates = cum.index
    final, peak, trough = float(cum.iloc[-1]), float(cum.max()), float(cum.min())
    curve_c = UP_COLOR if final >= 0 else DOWN_COLOR

    plt.rcParams.update({
        "figure.facecolor": "#FFFFFF", "axes.facecolor": "#FFFFFF",
        "axes.edgecolor": GRID_C, "axes.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False,
        "xtick.color": TEXT_SOFT, "ytick.color": TEXT_SOFT,
        "xtick.labelsize": 9.5, "ytick.labelsize": 10,
        "axes.labelcolor": TEXT_C, "axes.labelsize": 11,
        "text.color": TEXT_C, "legend.frameon": False, "legend.fontsize": 10,
        "savefig.facecolor": "#FFFFFF",
    })
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(13, 8.6), sharex=True,
        gridspec_kw={"height_ratios": [2.4, 1], "hspace": 0.12},
    )
    # 主标题贴图布左边缘(x=0.01),绘图区须同步收紧左边距,否则左侧出现空白列
    fig.subplots_adjust(left=0.055, right=0.995)

    # ── 主图:标普500 累计收益 ──
    ax1.fill_between(cum.index, 0, cum.values, where=cum.values >= 0,
                     color=UP_COLOR, alpha=0.10, interpolate=True, zorder=1)
    ax1.fill_between(cum.index, 0, cum.values, where=cum.values < 0,
                     color=DOWN_COLOR, alpha=0.10, interpolate=True, zorder=1)
    ax1.plot(cum.index, cum.values, color=curve_c, lw=2.2,
             solid_capstyle="round", zorder=3, label=f"标普500累计收益 {final:+.2f}%")
    ax1.axhline(0, color=TEXT_C, lw=1, ls=(0, (4, 4)), alpha=0.35, zorder=2)
    pad = (peak - trough) * 0.14 or 0.5
    ax1.set_ylim(trough - pad, peak + pad)
    n = len(cum)
    for tag, val, d, dy in (("峰值", peak, cum.idxmax(), 11), ("谷值", trough, cum.idxmin(), -17)):
        i = int(cum.index.get_loc(d))
        ha, dx = ("right", -8) if i >= n - 3 else (("left", 8) if i <= 2 else ("center", 0))
        ax1.scatter([d], [val], s=26, color=curve_c, zorder=4)
        ax1.annotate(f"{tag} {val:+.2f}%({d:%m-%d})", xy=(d, val), xytext=(dx, dy),
                     textcoords="offset points", ha=ha, fontsize=9.5,
                     color=TEXT_C, zorder=5)
    if cum.index[-1] not in (cum.idxmax(), cum.idxmin()):  # 端点即峰/谷时不重复标值
        ax1.annotate(f"{final:+.2f}%", xy=(dates[-1], final), xytext=(8, 4),
                     textcoords="offset points", fontsize=11, fontweight="bold",
                     color=curve_c)
    ax1.set_ylabel("累计收益(%)")
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax1.grid(axis="y", ls="--", alpha=0.25, color=GRID_C)
    ax1.set_axisbelow(True)
    ax1.legend(loc="upper left")

    # ── 附图:VIX ──
    if vix is None:
        ax2.set_yticks([])  # 无数据时不显示 0~1 的空刻度,避免误读
        ax2.text(0.5, 0.5, "VIX 数据未获取到(本图不含附图)", ha="center", va="center",
                 fontsize=13, color=TEXT_SOFT, transform=ax2.transAxes)
        ax2.set_ylabel("VIX(点)")
    else:
        last_vix = float(vix.iloc[-1])
        mean_vix = float(vix.mean())
        ax2.plot(vix.index, vix.values, color=VIX_C, lw=1.8,
                 solid_capstyle="round", zorder=3,
                 label=f"VIX {last_vix:.2f}({mood(last_vix)})")
        ax2.fill_between(vix.index, vix.min() - 1, vix.values, color=VIX_C,
                         alpha=0.12, zorder=1)
        ax2.axhline(VIX_ALERT, color=UP_COLOR, lw=1.0, ls="--", alpha=0.6, zorder=2)
        ax2.text(dates[0], VIX_ALERT, f" 警戒线 {VIX_ALERT:.0f}", fontsize=9,
                 color=UP_COLOR, va="bottom")
        ax2.axhline(mean_vix, color=TEXT_SOFT, lw=0.9, ls=":", alpha=0.9, zorder=2)
        ax2.text(dates[0], mean_vix, f" 区间均值 {mean_vix:.1f} ", fontsize=9,
                 color=TEXT_SOFT, va="bottom" if mean_vix >= VIX_ALERT else "top")
        ax2.annotate(f"{last_vix:.2f}", xy=(vix.index[-1], last_vix), xytext=(8, 4),
                     textcoords="offset points", fontsize=11, fontweight="bold",
                     color=VIX_C)
        ax2.set_ylabel("VIX(点)")
        ax2.grid(axis="y", ls="--", alpha=0.25, color=GRID_C)
        ax2.set_axisbelow(True)
        ax2.legend(loc="upper left")
        lo = min(float(vix.min()), VIX_ALERT) - 2
        hi = max(float(vix.max()), VIX_ALERT) + 2
        ax2.set_ylim(lo, hi)

    # ── 共用 x 轴 ──
    ax2.xaxis.set_major_locator(mdates.DayLocator(interval=6))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    span = (dates[-1] - dates[0]).days
    ax2.set_xlim(dates[0] - pd.Timedelta(days=2),
                 dates[-1] + pd.Timedelta(days=max(4, span * 0.03)))
    ax2.set_xlabel("交易日")

    # ── 标题与来源标注(一律标注 OMMQ) ──
    fig.suptitle(f"标普500近{len(cum)}个交易日累计收益与VIX走势　来源：OMMQ",
                 fontsize=17, fontweight="bold", color=TEXT_C, x=0.01, ha="left")
    note = (f"区间 {dates[0]:%Y-%m-%d} 至 {dates[-1]:%Y-%m-%d}"
            f"｜主图起点统一归一化为0%,价格指数口径不含分红"
            f"｜附图VIX与标普500同交易日对齐")
    if vix is None:
        note += "｜未获取到VIX"
    ax1.set_title(note, fontsize=10.5, color=TEXT_SOFT, loc="left", pad=12)

    out = report_image_path(OUT_NO, OUT_AUX)
    fig.savefig(out, dpi=200, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    return out


def main() -> None:
    n_days = int(sys.argv[1]) if len(sys.argv) > 1 else N_DAYS_DEFAULT
    print(f"窗口: 标普500 最近{n_days}个交易日累计收益 + 附图VIX")
    setup_font()  # 中文字体优先本机已安装字体,避免 Noto 变体字重回退成细体

    spx, spx_src = fetch_index("标普500", SPX_STEPS)
    if spx is None:
        raise SystemExit("标普500 各数据源均不可用,请检查网络后重试(不编造数据)")
    print(f"  [取数] 标普500 <- {spx_src}({len(spx)}个交易日，最新 {spx.index[-1]:%Y-%m-%d})")
    win = spx.tail(n_days)
    if len(win) < n_days:
        print(f"  [警告] 上游仅返回{len(spx)}个交易日,窗口按实际{len(win)}天绘制")
    cum = (win / win.iloc[0] - 1.0) * 100.0

    vix_raw, vix_src = fetch_index("VIX", VIX_STEPS)
    vix = None
    if vix_raw is not None:
        aligned = align(cum.index, vix_raw, "VIX")
        if len(aligned) >= 2:
            vix = pd.Series(aligned.values, index=aligned.index, name="VIX")
            print(f"  [取数] VIX <- {vix_src}({len(vix_raw)}个交易日，最新 {vix_raw.index[-1]:%Y-%m-%d})")
        else:
            print("  [失败] VIX 与标普500 无公共交易日,本图仅绘制主图")

    out = plot(cum, vix)
    print(f"已保存: {out}")

    print(f"\n[主图] 标普500 {cum.index[0]:%Y-%m-%d} ~ {cum.index[-1]:%Y-%m-%d}"
          f"({len(cum)}个交易日)")
    print(f"  区间累计 {cum.iloc[-1]:+.2f}%  峰值 {cum.max():+.2f}%(日 {cum.idxmax():%Y-%m-%d})"
          f"  谷值 {cum.min():+.2f}%(日 {cum.idxmin():%Y-%m-%d})")
    if vix is not None:
        corr = float(cum.diff().corr(vix.diff()))
        print(f"[附图] VIX 最新 {vix.iloc[-1]:.2f}({mood(float(vix.iloc[-1]))})"
              f"  均值 {vix.mean():.2f}  最高 {vix.max():.2f}({vix.idxmax():%Y-%m-%d})"
              f"  最低 {vix.min():.2f}({vix.idxmin():%Y-%m-%d})")
        print(f"  标普500日收益与VIX日变动相关系数 {corr:+.2f}(负值=股指下跌伴随避险情绪升温)")


if __name__ == "__main__":
    main()
