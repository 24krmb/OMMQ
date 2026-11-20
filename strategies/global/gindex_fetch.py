# -*- coding: utf-8 -*-
"""全球/A股指数共享取数模块(供 plot_global_indices_60d / plot_spx_vix_60d / plot_acwi_ftseaw_60d / plot_ashare_indices_60d 复用)
内容:
    _series        : 任意 (dates, closes) 归一为干净日线 Series(去重、去非正、按日期升序)
    fetch_index    : 按"降级清单"依次取数,每个来源重试 2 次,全失败返回 (None, "")
    sina_* / em_global / yahoo_chart / csindex_a / cni_a : 各上游的单序列取数封装
    setup_font     : 中文字体优先本机已安装字体,避免变体字回退成细体
用法:from gindex_fetch import fetch_index, sina_us, em_global, yahoo_chart, setup_font
      (脚本从仓库根目录运行,同目录模块由 sys.path 注入后可直接 import;
       strategies/stock 下的 A股脚本同样注入本目录以复用降级与字体逻辑)
注意:真指数(MSCI ACWI、富时 All-World)无免费日线,ETF 代理取数见 plot_acwi_ftseaw_60d.py
      中证/国证官网接口的 start_date/end_date 默认值写死在函数签名里(且已过期),必须显式传区间
"""

from __future__ import annotations
import datetime as dt
import os
import sys
import time
import warnings
warnings.filterwarnings("ignore")
import akshare as ak
import pandas as pd
import requests

# ════════════════════════ 可调参数 ════════════════════════
N_DAYS        = 60          # 公共交易日窗口长度(fetch_index 判定数据是否够用)
WINDOW_ROWS   = 140         # 每个指数取最近140个交易日参与公共日求交集
EM_CALL_PAUSE = 1.0
# ══════════════════════════════════════════════════════════

def _series(dates, closes) -> pd.Series:
    s = pd.Series(pd.to_numeric(pd.Series(closes), errors="coerce").values,
                  index=pd.to_datetime(pd.Series(dates), errors="coerce"))
    s.index = s.index.normalize()
    s = s.replace([float("inf"), float("-inf")], pd.NA).dropna()
    s = s[s > 0]
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s.astype(float)

def em_global(symbol: str) -> pd.Series:
    df = ak.index_global_hist_em(symbol=symbol)
    return _series(df["日期"], df["最新价"])

def sina_us(symbol: str) -> pd.Series:
    df = ak.index_us_daily_sina(symbol=symbol)
    return _series(df["date"], df["close"])

def sina_global(name: str) -> pd.Series:
    df = ak.index_global_hist_sina(symbol=name)
    return _series(df["date"], df["close"])

def sina_hk(symbol: str) -> pd.Series:
    df = ak.index_hk_daily_sina(symbol=symbol)
    return _series(df["date"], df["close"])

def sina_a(symbol: str) -> pd.Series:
    df = ak.index_zh_daily_sina(symbol=symbol)
    return _series(df["date"], df["close"])

def _recent(days: int) -> tuple:
    """官网接口的显式区间(近 days 个自然日),避免沿用函数签名里过期的默认结束日。"""
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    return f"{start:%Y%m%d}", f"{end:%Y%m%d}"

def csindex_a(symbol: str, lookback_days: int = 220) -> pd.Series:
    """中证指数官网(上证综指/上证50/中证500/中证1000 等中证系列)。"""
    s0, s1 = _recent(lookback_days)
    df = ak.index_hist_csindex(symbol=symbol, start_date=s0, end_date=s1)
    return _series(df["日期"], df["收盘"])

def cni_a(symbol: str, lookback_days: int = 220) -> pd.Series:
    """国证指数官网(深证成指/创业板指/国证2000 等国证系列),发布比新浪晚一个交易日。"""
    s0, s1 = _recent(lookback_days)
    df = ak.index_hist_cni(symbol=symbol, start_date=s0, end_date=s1)
    return _series(df["日期"], df["收盘价"])

def sina_eem() -> pd.Series:
    df = ak.stock_us_hist_sina(symbol="EEM", period="daily")
    return _series(df["date"], df["close"])

def yahoo_chart(ticker: str) -> pd.Series:
    last_err = None
    for host in ("query1", "query2"):
        try:
            url = f"https://{host}.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(ticker)}"
            r = requests.get(url, params={"range": "6mo", "interval": "1d"},
                             headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            res = r.json()["chart"]["result"][0]
            ts = res["timestamp"]
            closes = res["indicators"]["quote"][0]["close"]
            idx = pd.to_datetime(ts, unit="s", utc=True).tz_convert(None)
            return _series(pd.Series(idx), pd.Series(closes))
        except Exception as e:
            last_err = e
    raise last_err


def fetch_index(label: str, steps, rows: int = WINDOW_ROWS) -> tuple:
    last_err = None
    for desc, fn in steps:
        for attempt in range(2):
            try:
                s = fn()
                if len(s) >= N_DAYS + 10:
                    return s.tail(rows), desc
                raise ValueError(f"返回数据不足({len(s)}行)")
            except Exception as e:
                last_err = e
                if attempt == 0:
                    time.sleep(2)
        print(f"  [降级] {label} <- {desc} 失败: {type(last_err).__name__}: {str(last_err)[:70]}")
    print(f"  [失败] {label}: 全部来源均不可用，本图将不含该指数")
    return None, ""

def setup_font():
    from matplotlib import font_manager
    import matplotlib.pyplot as plt
    preferred = ["Microsoft YaHei", "SimHei", "PingFang SC", "Hiragino Sans GB",
                 "Noto Sans CJK SC", "Source Han Sans SC", "Source Han Sans CN",
                 "WenQuanYi Micro Hei", "WenQuanYi Zen Hei", "Arial Unicode MS"]
    installed = {f.name for f in font_manager.fontManager.ttflist}
    chosen = [n for n in preferred if n in installed]
    if not chosen:
        for path in ("/usr/share/fonts/truetype/chinese/NotoSansSC-Regular.ttf",
                     "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                     "C:/Windows/Fonts/msyh.ttc",
                     "/System/Library/Fonts/PingFang.ttc"):
            try:
                if os.path.exists(path):
                    font_manager.fontManager.addfont(path)
                    chosen = [font_manager.FontProperties(fname=path).get_name()]
                    break
            except Exception:
                pass
    if chosen:
        plt.rcParams["font.sans-serif"] = chosen + ["DejaVu Sans"]
    else:
        print("警告: 未找到中文字体，图中中文可能显示为方块(可安装微软雅黑/思源黑体后重试)")
    plt.rcParams["axes.unicode_minus"] = False
