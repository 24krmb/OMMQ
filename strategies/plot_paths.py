# -*- coding: utf-8 -*-
"""plot_paths — 统一产物归档路径（按当前日期落盘 reports/）

所有图表与文章产物统一写入 reports/<当天日期>/，与报告 Markdown 同目录：
    - 核心八图编号固定：01 全景 / 02 情绪 / 03 板块TOP5 / 04 轮动热力图 /
      05 两融资金 / 06 期货TOP5 / 07 期货量仓 / 08 期货基差
    - 扩展与研究图从 09 起；参数化脚本以代码作后缀避免同日覆盖，如 10_600519.png
    - 报告正文用相对路径 ./<NN>.png 嵌入图片

用法（strategies/ 下脚本，直接运行时 sys.path[0] 即本目录）：
    from plot_paths import report_image_path
    out = report_image_path(7)            # -> reports/20261023/07.png
    out = report_image_path(10, code)     # -> reports/20261023/10_600519.png
"""

from __future__ import annotations
import datetime as dt
import os
def report_dir(date: dt.date | None = None) -> str:
    """当天日期的产物目录 reports/YYYYMMDD/（自动创建）。"""
    d = date or dt.date.today()
    path = os.path.join("reports", f"{d:%Y%m%d}")
    os.makedirs(path, exist_ok=True)
    return path
def report_image_path(no: int, aux: str = "", date: dt.date | None = None) -> str:
    """当天日期目录下的编号图片路径：reports/YYYYMMDD/<NN>[_<aux>].png。"""
    name = f"{no:02d}_{aux}.png" if aux else f"{no:02d}.png"
    return os.path.join(report_dir(date), name)
