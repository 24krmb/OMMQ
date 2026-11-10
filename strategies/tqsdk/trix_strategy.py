#!/usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = "Chaos"

import os
from datetime import date
import pandas as pd
from tqsdk import TqApi, TqAuth, TqBacktest, TargetPosTask, BacktestFinished
from tqsdk.ta import ATR

# ===== 全局参数设置 =====
# 从环境变量读取快期账户凭据(凭据不入库、不写入任何文件)
YOUR_ACCOUNT = os.environ.get("YOUR_ACCOUNT", "")
YOUR_PASSWORD = os.environ.get("YOUR_PASSWORD", "")
if not YOUR_ACCOUNT or not YOUR_PASSWORD:
    raise SystemExit("缺少快期账号凭据:请先设置环境变量 YOUR_ACCOUNT / YOUR_PASSWORD 后重试。")
SYMBOL = "KQ.m@CZCE.MA"  # 甲醇主力连续合约（行情与指标用；主连不能直接下单，下单个为其underlying_symbol）
POSITION_SIZE = 10  # 基础持仓手数
START_DATE = date(2023, 10, 30)  # 回测开始日期（近3年）
END_DATE = date(2026, 10, 30)  # 回测结束日期

# TRIX指标参数
TRIX_PERIOD = 12  # TRIX计算周期
SIGNAL_PERIOD = 9  # 信号线计算周期
MA_PERIOD = 60    # 长期移动平均线周期，用于趋势过滤

# 信号阈值参数
SIGNAL_THRESHOLD = 0.05  # TRIX与信号线差值的阈值，避免微小交叉

# 风控参数
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

# 换月相关
trade_symbol = None  # 当前正在下单/持仓的真实主力合约
target_pos = None  # 与 trade_symbol 绑定的目标持仓任务
retired_tasks = []  # 换月后已退役的旧任务（保存引用，等旧合约平仓完成）
atr_data = None  # 最近一次ATR计算结果

# ===== TRIX指标计算函数 =====
def calculate_trix(close_prices, period):
    """计算TRIX指标和信号线"""
    # 第一重EMA
    ema1 = close_prices.ewm(span=period, adjust=False).mean()
    # 第二重EMA
    ema2 = ema1.ewm(span=period, adjust=False).mean()
    # 第三重EMA
    ema3 = ema2.ewm(span=period, adjust=False).mean()
    # 计算TRIX
    trix = 100 * (ema3 / ema3.shift(1) - 1)
    # 计算信号线
    signal = trix.rolling(SIGNAL_PERIOD).mean()

    return trix, signal

# ===== 主力换月函数 =====
def do_rollover(new_symbol):
    """主力合约切换：平掉旧合约仓位，在新主力上按原方向重新建仓，止损/止盈按新合约重置"""
    global trade_symbol, target_pos, entry_price, stop_loss_price, take_profit_price, current_direction
    old_symbol = trade_symbol
    if target_pos is not None:
        target_pos.set_target_volume(0)  # 旧合约仓位归零
        retired_tasks.append(target_pos)  # 保留引用，让旧任务继续完成平仓
    trade_symbol = new_symbol
    target_pos = TargetPosTask(api, trade_symbol, support_open_min_volume=True)
    has_data = (atr_data is not None
                and not pd.isna(klines.close.iloc[-1])
                and not pd.isna(atr_data.atr.iloc[-1]))
    if current_direction != 0 and has_data:
        # 在新主力合约上按原方向重新建仓
        px = float(klines.close.iloc[-1])
        current_atr = float(atr_data.atr.iloc[-1])
        entry_price = px
        if current_direction == 1:
            stop_loss_price = px - STOP_LOSS_MULTIPLIER * current_atr
            take_profit_price = px + TAKE_PROFIT_MULTIPLIER * current_atr
        else:
            stop_loss_price = px + STOP_LOSS_MULTIPLIER * current_atr
            take_profit_price = px - TAKE_PROFIT_MULTIPLIER * current_atr
        target_pos.set_target_volume(current_direction * POSITION_SIZE)
        print(f"主力换月: {old_symbol} -> {trade_symbol}, 同向移仓(当前方向={current_direction}), "
              f"参考价={px:.2f}, 止损={stop_loss_price:.2f}, 止盈={take_profit_price:.2f}")
    elif current_direction != 0 and not has_data:
        # 回测初期指标未就绪的极端情况：仅平旧仓，方向状态复位为空仓
        current_direction = 0
        entry_price = 0
        print(f"主力换月: {old_symbol} -> {trade_symbol}, 指标未就绪, 平旧仓后处于空仓状态")
    else:
        print(f"主力换月: {old_symbol} -> {trade_symbol}, 当前空仓")

# ===== 策略开始 =====
print("开始运行TRIX指标期货策略...")
print(f"品种: {SYMBOL} (甲醇主力连续), 回测周期: {START_DATE} - {END_DATE}")
print(f"TRIX参数: 周期={TRIX_PERIOD}, 信号线周期={SIGNAL_PERIOD}")

# 创建API实例
api = TqApi(backtest=TqBacktest(start_dt=START_DATE, end_dt=END_DATE),
            auth=TqAuth(YOUR_ACCOUNT, YOUR_PASSWORD))

# 订阅主连K线与主连行情
klines = api.get_kline_serial(SYMBOL, 60 * 60 * 24)  # 主连日线数据
quote_main = api.get_quote(SYMBOL)  # 主连行情, 用于读取当前主力合约 underlying_symbol

# 等待主连返回当前主力合约，并以其作为实际下单合约
while not quote_main.underlying_symbol:
    api.wait_update()
trade_symbol = quote_main.underlying_symbol
print(f"当前主力合约: {trade_symbol}")

# 创建目标持仓任务（绑定真实主力合约）
target_pos = TargetPosTask(api, trade_symbol, support_open_min_volume=True)

try:
    while True:
        # 等待更新
        api.wait_update()

        # ===== 主力换月检测 =====
        new_underlying = quote_main.underlying_symbol
        if (new_underlying and new_underlying != trade_symbol
                and api.is_changing(quote_main, "underlying_symbol")):
            do_rollover(new_underlying)

        # 如果K线有更新
        if api.is_changing(klines.iloc[-1], "datetime"):
            # 确保有足够的数据计算指标
            if len(klines) < max(TRIX_PERIOD, SIGNAL_PERIOD, MA_PERIOD, ATR_PERIOD) + 10:
                continue

            # 计算TRIX指标和信号线
            klines['trix'], klines['signal'] = calculate_trix(klines.close, TRIX_PERIOD)

            # 计算长期移动平均线，用于趋势过滤
            klines['ma'] = klines.close.rolling(window=MA_PERIOD).mean()

            # 计算ATR用于设置止损
            atr_data = ATR(klines, ATR_PERIOD)

            # 获取最新数据
            current_price = float(klines.close.iloc[-1])
            current_datetime = pd.to_datetime(klines.datetime.iloc[-1], unit='ns')
            current_trix = float(klines.trix.iloc[-1])
            previous_trix = float(klines.trix.iloc[-2])
            current_signal = float(klines.signal.iloc[-1])
            previous_signal = float(klines.signal.iloc[-2])
            current_ma = float(klines.ma.iloc[-1])
            current_atr = float(atr_data.atr.iloc[-1])

            # 计算TRIX与信号线的差值
            trix_diff = current_trix - current_signal
            previous_trix_diff = previous_trix - previous_signal

            # 输出调试信息
            print(f"日期: {current_datetime.strftime('%Y-%m-%d')}, 价格: {current_price:.2f}")
            print(f"TRIX: {current_trix:.4f}, 信号线: {current_signal:.4f}, 差值: {trix_diff:.4f}")

            # ===== 交易逻辑 =====

            # 空仓状态 - 寻找开仓机会
            if current_direction == 0:
                # 多头开仓条件：TRIX上穿信号线
                if previous_trix < previous_signal and current_trix > current_signal:
                    current_direction = 1
                    target_pos.set_target_volume(POSITION_SIZE)
                    entry_price = current_price
                    stop_loss_price = entry_price - STOP_LOSS_MULTIPLIER * current_atr
                    take_profit_price = entry_price + TAKE_PROFIT_MULTIPLIER * current_atr
                    print(f"多头开仓: 价格={entry_price}, 止损={stop_loss_price:.2f}, 止盈={take_profit_price:.2f}")

                # 空头开仓条件：TRIX下穿信号线
                elif previous_trix > previous_signal and current_trix < current_signal:
                    current_direction = -1
                    target_pos.set_target_volume(-POSITION_SIZE)
                    entry_price = current_price
                    stop_loss_price = entry_price + STOP_LOSS_MULTIPLIER * current_atr
                    take_profit_price = entry_price - TAKE_PROFIT_MULTIPLIER * current_atr
                    print(f"空头开仓: 价格={entry_price}, 止损={stop_loss_price:.2f}, 止盈={take_profit_price:.2f}")

            # 多头持仓 - 检查平仓条件
            elif current_direction == 1:
                # 止损条件
                if current_price <= stop_loss_price:
                    profit_pct = (current_price - entry_price) / entry_price * 100
                    target_pos.set_target_volume(0)
                    current_direction = 0
                    print(f"多头止损平仓: 价格={current_price}, 盈亏={profit_pct:.2f}%")

                # 止盈条件
                elif current_price >= take_profit_price:
                    profit_pct = (current_price - entry_price) / entry_price * 100
                    target_pos.set_target_volume(0)
                    current_direction = 0
                    print(f"多头止盈平仓: 价格={current_price}, 盈亏={profit_pct:.2f}%")

                # 信号平仓：TRIX下穿信号线
                elif previous_trix > previous_signal and current_trix < current_signal:
                    profit_pct = (current_price - entry_price) / entry_price * 100
                    target_pos.set_target_volume(0)
                    current_direction = 0
                    print(f"多头信号平仓: 价格={current_price}, 盈亏={profit_pct:.2f}%")

            # 空头持仓 - 检查平仓条件
            elif current_direction == -1:
                # 止损条件
                if current_price >= stop_loss_price:
                    profit_pct = (entry_price - current_price) / entry_price * 100
                    target_pos.set_target_volume(0)
                    current_direction = 0
                    print(f"空头止损平仓: 价格={current_price}, 盈亏={profit_pct:.2f}%")

                # 止盈条件
                elif current_price <= take_profit_price:
                    profit_pct = (entry_price - current_price) / entry_price * 100
                    target_pos.set_target_volume(0)
                    current_direction = 0
                    print(f"空头止盈平仓: 价格={current_price}, 盈亏={profit_pct:.2f}%")

                # 信号平仓：TRIX上穿信号线
                elif previous_trix < previous_signal and current_trix > current_signal:
                    profit_pct = (entry_price - current_price) / entry_price * 100
                    target_pos.set_target_volume(0)
                    current_direction = 0
                    print(f"空头信号平仓: 价格={current_price}, 盈亏={profit_pct:.2f}%")

except BacktestFinished as e:
    print("回测结束")
    api.close()
