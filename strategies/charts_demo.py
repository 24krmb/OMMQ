"""plot_utils 模块示例脚本 — 四种常用图各画一张

1. 折线图: 白酒板块指数 2026-09 ~ 10 月收盘价 (AKShare 实时拉取)
2. 柱状图: 行业板块当周涨幅 TOP15 (复用 industry_top5.py 的输出 CSV)
3. 直方图: 白酒板块日涨跌幅分布 (由 1 的数据计算)
4. 热力图: 模拟策略净值相关性矩阵 (随机数据, 仅演示)

运行: uv run python strategies/charts_demo.py
输出: strategies/output/charts/*.png
"""

from __future__ import annotations

import os
import sys

import akshare as ak
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)).rsplit("strategies", 1)[0].rstrip("\\/"))
import plot_utils as pm

OUT = "strategies/output/charts"


def main() -> None:
    os.makedirs(OUT, exist_ok=True)

    # 1) 折线图 —— 板块指数走势
    wine = ak.stock_board_industry_index_ths(symbol="白酒", start_date="20260901", end_date="20261016")
    wine = wine.set_index("日期")
    pm.plot_line(wine["收盘价"], title="白酒板块指数收盘价 (2026-09 ~ 2026-10)",
                 xlabel="日期", ylabel="指数点", path=f"{OUT}/1_line_白酒指数.png")

    # 2) 柱状图 —— 行业板块周涨幅 TOP15 (红涨绿跌由数值正负自动着色)
    #    (自足计算: 10-09 前收盘 -> 10-16 收盘, 与当年 industry_top5 脚本口径一致)
    import time as _time
    names = ak.stock_board_industry_name_ths()["name"].tolist()
    records: list[dict] = []
    for board in names:
        try:
            h = ak.stock_board_industry_index_ths(symbol=board, start_date="20261009", end_date="20261016")
            closes = h.set_index("日期")["收盘价"]
            if len(closes) >= 2 and float(closes.iloc[0]) > 0:
                pct = (float(closes.iloc[-1]) / float(closes.iloc[0]) - 1) * 100
                records.append({"板块名称": board, "区间涨幅%": round(pct, 2)})
        except Exception:
            pass  # 个别板块抓取失败跳过, 不影响整体
        _time.sleep(0.3)
    boards = (pd.DataFrame(records)
              .sort_values("区间涨幅%", ascending=False, ignore_index=True))
    pm.plot_bar(boards.head(15).set_index("板块名称")["区间涨幅%"],
                title="行业板块周涨幅 TOP15 (2026-10-12 ~ 10-16)",
                ylabel="周涨幅 %", path=f"{OUT}/2_bar_top15.png")

    # 3) 直方图 —— 日涨跌幅分布
    rets = wine["收盘价"].pct_change().dropna() * 100
    pm.plot_hist(rets, bins=12, title="白酒板块日涨跌幅分布 (%)",
                 xlabel="涨跌幅 %", path=f"{OUT}/3_hist_涨跌幅.png")

    # 4) 热力图 —— 多策略净值曲线相关性 (随机演示数据)
    rng = np.random.default_rng(42)
    brokers = np.cumprod(1 + rng.normal(0.0004, 0.01, 240))  # 模拟净值
    demo = pd.DataFrame({
        "策略A-趋势": brokers,
        "策略B-趋势": brokers * (1 + rng.normal(0, 0.002, 240)),      # 与A高度相关
        "策略C-轮动": np.cumprod(1 + rng.normal(0.0002, 0.015, 240)), # 独立
        "策略D-对冲": np.cumprod(1 + rng.normal(0.0001, 0.005, 240)),
    })
    pm.plot_heatmap(demo, path=f"{OUT}/4_heatmap_策略相关性.png")


if __name__ == "__main__":
    main()
