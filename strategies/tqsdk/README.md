# 天勤量化脚本(tqsdk)

基于天勤 TqSdk 的期货回测 / 交易脚本。与 `strategies/stock|futures`,**本目录脚本需要额外的包与快期账号**:

## 前置条件

1. **安装 SDK**(项目虚拟环境):
   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r strategies/tqsdk/requirements.txt
   ```
2. **快期账号**,凭据通过环境变量提供,不写入任何文件:
   ```powershell
   $env:TQ_ACCOUNT = "账号"
   $env:TQ_PASSWORD = "密码"
   ```
3. 运行示例:
   ```powershell
   .\.venv\Scripts\python.exe strategies/tqsdk/trix_strategy.py
   ```

## 脚本清单

| 脚本 | 说明 |
| --- | --- |
| trix_strategy.py | TRIX 趋势策略回测(主连行情,自动换月移仓,ATR 止损止盈) |
| trix_strategy_index.py | 同策略**单合约对照版**(不处理换月,用于评估换月贡献) |
| vwap_order.py | VWAP 算法单示例(按历史成交量占比拆单,默认 TqSim 模拟盘) |

## 说明

- 回测产物由 tqsdk 自行管理(web 图表 / 控制台输出),不走 `reports/YYYYMMDD/` 编号;需长期保留的报告手工归档至 `backtest/archive/` 或 `reports/`;
- 所有示例默认**模拟/回测**语义;接入实盘前请改用 `TqAccount` 并确认操作在授权范围内;
- 仅供研究学习,不构成投资建议。
