# -*- coding: utf-8 -*-
"""plot_paths — 统一产物归档路径(按当前日期落盘 reports/)

所有图表与文章产物统一写入 reports/<当天日期>/,与报告 Markdown 同目录:
    - 核心八图编号固定:01 全景 / 02 情绪 / 03 板块TOP5 / 04 轮动热力图 /
      05 两融资金 / 06 期货TOP5 / 07 期货量仓 / 08 期货基差
    - 扩展与研究图从 09 起；参数化脚本以代码作后缀避免同日覆盖,如 10_600519.png
    - 报告正文用相对路径 ./<NN>.png 嵌入图片

用法(strategies/stock 与 strategies/futures 下的脚本,导入前先把 strategies/ 目录加入 sys.path):
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from plot_paths import report_image_path
    out = report_image_path(7)            # -> reports/20261023/07.png
    out = report_image_path(10, code)     # -> reports/20261023/10_600519.png
"""

from __future__ import annotations
import datetime as dt
import os

# 仓库根目录(本文件位于 <root>/strategies/),产物始终落盘 <root>/reports/,与运行时 CWD 无关
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def report_dir(date: dt.date | None = None) -> str:
    """当天日期的产物目录 <root>/reports/YYYYMMDD/(自动创建)。"""
    d = date or dt.date.today()
    path = os.path.join(_ROOT, "reports", f"{d:%Y%m%d}")
    os.makedirs(path, exist_ok=True)
    return path
def report_image_path(no: int, aux: str = "", date: dt.date | None = None) -> str:
    """当天日期目录下的编号图片路径:reports/YYYYMMDD/<NN>[_<aux>].png。"""
    name = f"{no:02d}_{aux}.png" if aux else f"{no:02d}.png"
    return os.path.join(report_dir(date), name)
