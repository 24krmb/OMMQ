#!/usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = "Chaos"
"""TRIX 期货策略 —— 单合约对照版

与 trix_strategy.py 的区别:不处理主力换月。
- 行情与指标:主连 KQ.m@CZCE.MA(数据连续,不受个别合约换月跳空影响);
- 下单:回测开始时主连的 underlying_symbol(真实主力合约),持有到回测结束;
- 用途:与 trix_strategy.py(自动换月移仓)对照,评估换月处理的贡献。
"""

import os
from datetime import date
import pandas as pd
from tqsdk import TqApi, TqAuth, TqBacktest, TargetPosTask, BacktestFinished
from tqsdk.ta import ATR

# 从环境变量读取快期账户凭据(凭据不入库、不写入任何文件)
YOUR_ACCOUNT = os.environ.get("YOUR_ACCOUNT", "")
YOUR_PASSWORD = os.environ.get("YOUR_PASSWORD", "")
if not YOUR_ACCOUNT or not YOUR_PASSWORD:
    raise SystemExit("缺少快期账号凭据:请先设置环境变量 YOUR_ACCOUNT / YOUR_PASSWORD 后重试。")

# ===== 全局参数设置 =====
SYMBOL_MAIN = "KQ.m@CZCE.MA"  # 甲醇主连(行情与指标用;主连不能直接下单)
POSITION_SIZE = 30  # 基础持仓手数
START_DATE = date(2026, 6, 1)  # 回测开始日期
END_DATE = date(2026, 10, 30)  # 回测结束日期
TRIX_PERIOD = 12  # TRIX计算周期
SIGNAL_PERIOD = 9  # 信号线计算周期
MA_PERIOD = 60    # 长期移动平均线周期，用于趋势过滤
SIGNAL_THRESHOLD = 0.05  # TRIX与信号线差值的阈值，避免微小交叉
ATR_PERIOD = 14  # ATR计算周期
STOP_LOSS_MULTIPLIER = 2.0  # 止损ATR倍数
TAKE_PROFIT_MULTIPLIER = 3.0  # 止盈ATR倍数
MAX_HOLDING_DAYS = 15  # 最大持仓天数

# ===== 全局变量 =====
current_direction = 0  # 当前持仓方向：1=多头，-1=空头，0=空仓
entry_price = 0  # 开仓价格
stop_loss_price = 0  # 止损价格
entry_date = None  # 开仓日期
trade_count = 0  # 交易次数
win_count = 0  # 盈利次数

# ===== TRIX指标计算函数 =====
def calculate_trix(close_prices, period):
    ema1 = close_prices.ewm(span=period, adjust=False).mean()
    ema2 = ema1.ewm(span=period, adjust=False).mean()
    ema3 = ema2.ewm(span=period, adjust=False).mean()
    trix = 100 * (ema3 / ema3.shift(1) - 1)
    signal = trix.rolling(SIGNAL_PERIOD).mean()
    return trix, signal

# ===== 策略开始 =====
print("开始运行TRIX指标期货策略(单合约对照版,不处理换月)...")
print(f"品种: {SYMBOL_MAIN}, 回测周期: {START_DATE} - {END_DATE}")
print(f"TRIX参数: 周期={TRIX_PERIOD}, 信号线周期={SIGNAL_PERIOD}")

# 创建API实例
api = TqApi(backtest=TqBacktest(start_dt=START_DATE, end_dt=END_DATE),
            auth=TqAuth(YOUR_ACCOUNT, YOUR_PASSWORD))
klines = api.get_kline_serial(SYMBOL_MAIN, 60 * 60 * 24)  # 主连日线数据

# 解析回测开始时的真实主力合约,全程持有(不处理换月)
quote_main = api.get_quote(SYMBOL_MAIN)
while not quote_main.underlying_symbol:
    api.wait_update()
SYMBOL = quote_main.underlying_symbol
print(f"当前主力合约(单合约持有): {SYMBOL}")

# 创建目标持仓任务
target_pos = TargetPosTask(api, SYMBOL)

try:
    while True:
        api.wait_update()
        if api.is_changing(klines.iloc[-1], "datetime"):
            if len(klines) < max(TRIX_PERIOD, SIGNAL_PERIOD, MA_PERIOD, ATR_PERIOD) + 10:
                continue
            klines['trix'], klines['signal'] = calculate_trix(klines.close, TRIX_PERIOD)
            klines['ma'] = klines.close.rolling(window=MA_PERIOD).mean()
            atr_data = ATR(klines, ATR_PERIOD)
            current_price = float(klines.close.iloc[-1])
            current_datetime = pd.to_datetime(klines.datetime.iloc[-1], unit='ns')
            current_trix = float(klines.trix.iloc[-1])
            previous_trix = float(klines.trix.iloc[-2])
            current_signal = float(klines.signal.iloc[-1])
            previous_signal = float(klines.signal.iloc[-2])
            current_ma = float(klines.ma.iloc[-1])
            current_atr = float(atr_data.atr.iloc[-1])
            trix_diff = current_trix - current_signal
            previous_trix_diff = previous_trix - previous_signal
            print(f"日期: {current_datetime.strftime('%Y-%m-%d')}, 价格: {current_price:.2f}")
            print(f"TRIX: {current_trix:.4f}, 信号线: {current_signal:.4f}, 差值: {trix_diff:.4f}")
            
            # ===== 交易逻辑 =====
            if current_direction == 0:
                if previous_trix < previous_signal and current_trix > current_signal:
                    current_direction = 1
                    target_pos.set_target_volume(POSITION_SIZE)
                    entry_price = current_price
                    stop_loss_price = entry_price - STOP_LOSS_MULTIPLIER * current_atr
                    take_profit_price = entry_price + TAKE_PROFIT_MULTIPLIER * current_atr
                    print(f"多头开仓: 价格={entry_price}, 止损={stop_loss_price:.2f}, 止盈={take_profit_price:.2f}")
                elif previous_trix > previous_signal and current_trix < current_signal:
                    current_direction = -1
                    target_pos.set_target_volume(-POSITION_SIZE)
                    entry_price = current_price
                    stop_loss_price = entry_price + STOP_LOSS_MULTIPLIER * current_atr
                    take_profit_price = entry_price - TAKE_PROFIT_MULTIPLIER * current_atr
                    print(f"空头开仓: 价格={entry_price}, 止损={stop_loss_price:.2f}, 止盈={take_profit_price:.2f}")
            
            # 多头持仓 - 检查平仓条件
            elif current_direction == 1:
                if current_price <= stop_loss_price:
                    profit_pct = (current_price - entry_price) / entry_price * 100
                    target_pos.set_target_volume(0)
                    current_direction = 0
                    print(f"多头止损平仓: 价格={current_price}, 盈亏={profit_pct:.2f}%")
                elif current_price >= take_profit_price:
                    profit_pct = (current_price - entry_price) / entry_price * 100
                    target_pos.set_target_volume(0)
                    current_direction = 0
                    print(f"多头止盈平仓: 价格={current_price}, 盈亏={profit_pct:.2f}%")
                elif previous_trix > previous_signal and current_trix < current_signal:
                    profit_pct = (current_price - entry_price) / entry_price * 100
                    target_pos.set_target_volume(0)
                    current_direction = 0
                    print(f"多头信号平仓: 价格={current_price}, 盈亏={profit_pct:.2f}%")
            
            # 空头持仓 - 检查平仓条件
            elif current_direction == -1:
                if current_price >= stop_loss_price:
                    profit_pct = (entry_price - current_price) / entry_price * 100
                    target_pos.set_target_volume(0)
                    current_direction = 0
                    print(f"空头止损平仓: 价格={current_price}, 盈亏={profit_pct:.2f}%")
                elif current_price <= take_profit_price:
                    profit_pct = (entry_price - current_price) / entry_price * 100
                    target_pos.set_target_volume(0)
                    current_direction = 0
                    print(f"空头止盈平仓: 价格={current_price}, 盈亏={profit_pct:.2f}%")
                elif previous_trix < previous_signal and current_trix > current_signal:
                    profit_pct = (entry_price - current_price) / entry_price * 100
                    target_pos.set_target_volume(0)
                    current_direction = 0
                    print(f"空头信号平仓: 价格={current_price}, 盈亏={profit_pct:.2f}%")

except BacktestFinished as e:
    print("回测结束")
    api.close()
