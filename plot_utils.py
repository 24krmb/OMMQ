# -*- coding: utf-8 -*-
"""plot_utils — 策略脚本统一绘图工具(24K-Claw 配色)
供 strategies/ 下脚本复用的快速出图函数,统一中文字体、配色与落盘格式:
    - plot_line    折线图(时间序列)
    - plot_bar     柱状图(红涨绿跌,按数值正负自动着色)
    - plot_hist    直方图(分布)
    - plot_heatmap 相关性热力图(红正绿负发散配色)
"""

from __future__ import annotations
import os
import warnings
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

warnings.filterwarnings("ignore")
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC","Noto Sans SC","Microsoft YaHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False
matplotlib.rcParams["text.color"] = "#27254c"
matplotlib.rcParams["axes.labelcolor"] = "#27254c"
matplotlib.rcParams["axes.titlecolor"] = "#27254c"
matplotlib.rcParams["xtick.color"] = "#27254c"
matplotlib.rcParams["ytick.color"] = "#27254c"

UP_COLOR = "#F36"    # 涨 / 正值
DOWN_COLOR = "#0C9"  # 跌 / 负值

# 红正绿负发散配色(用于热力图)
_DIVERGING = LinearSegmentedColormap.from_list(
    "updown", ["#0C9", "#ffffff", "#F36"])


def _save(fig: plt.Figure, path: str) -> None:
    """统一落盘:自动建目录、固定 dpi、关闭 figure。"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"图表已保存: {path}")


def plot_line(series: pd.Series, title: str = "", xlabel: str = "",
              ylabel: str = "", path: str = "plot.png",
              color: str = UP_COLOR) -> None:
    """折线图:series 为带索引的一维序列(如日期索引收盘价)。"""
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(series.index, series.values, linewidth=1.8, color=color,
            marker="o", markersize=3)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(linestyle="--", alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    _save(fig, path)


def plot_bar(series: pd.Series, title: str = "", ylabel: str = "",
             path: str = "plot.png", xlabel: str = "") -> None:
    """柱状图:红涨绿跌由数值正负自动着色,柱端标注数值。"""
    fig, ax = plt.subplots(figsize=(12, 6))
    colors = [UP_COLOR if v >= 0 else DOWN_COLOR for v in series.values]
    bars = ax.bar(series.index, series.values, color=colors, width=0.6)
    span = series.abs().max() or 1.0
    for b, v in zip(bars, series.values):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:+.2f}",
                ha="center", va="bottom" if v >= 0 else "top",
                fontsize=9)
    ax.axhline(0, color="#bbb", linewidth=0.8)
    ax.set_ylim(series.min() - span * 0.15, series.max() + span * 0.15)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    fig.tight_layout()
    _save(fig, path)


def plot_hist(series: pd.Series, bins: int = 10, title: str = "",
              xlabel: str = "", ylabel: str = "频数",
              path: str = "plot.png") -> None:
    """直方图:展示序列分布,附带均值参考线。"""
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(series.values, bins=bins, color="#99F", alpha=0.85,
            edgecolor="white", linewidth=0.8)
    mean = float(series.mean())
    ax.axvline(mean, color="#F36", linestyle="--", linewidth=1.2,
               label=f"均值 {mean:.2f}")
    ax.legend(loc="best", fontsize=10)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    fig.tight_layout()
    _save(fig, path)


def plot_heatmap(df: pd.DataFrame, path: str = "plot.png",
                 title: str = "") -> None:
    """相关性热力图:对 df 计算相关系数矩阵,红正绿负,格内标注数值。"""
    corr = df.corr(numeric_only=True)
    n = len(corr)
    fig, ax = plt.subplots(figsize=(1.6 * n + 2.4, 1.2 * n + 2.0))
    im = ax.imshow(corr.values, cmap=_DIVERGING, vmin=-1, vmax=1)
    ax.set_xticks(range(n), corr.columns, rotation=45, ha="right")
    ax.set_yticks(range(n), corr.index)
    for i in range(n):
        for j in range(n):
            v = float(corr.iloc[i, j])
            ax.text(j, i, f"{v:+.2f}", ha="center", va="center", fontsize=10,
                    color="white" if abs(v) > 0.6 else "#27254c")
    fig.colorbar(im, ax=ax, shrink=0.8, label="相关系数")
    if title:
        ax.set_title(title, fontsize=14, fontweight="bold")
    fig.tight_layout()
    _save(fig, path)
