# 自定义板块等权回测

`equal_weight_backtest.py` —— 通达信数据驱动的自定义板块等权指数回测,参数化合并自原
`backtest_xflt` / `backtest_scqlt` 两套重复脚本。

## 用法

```powershell
# 全流程:取数 + 合成出图(默认 xflt 板块,近 5 年)
.\.venv\Scripts\python.exe backtest/equal_weight_backtest.py all --board xflt
.\.venv\Scripts\python.exe backtest/equal_weight_backtest.py all --board scqlt

# 仅取数 / 仅合成出图(process 不需要通达信在线)
.\.venv\Scripts\python.exe backtest/equal_weight_backtest.py fetch  --board xflt --years 3
.\.venv\Scripts\python.exe backtest/equal_weight_backtest.py process --board xflt --end 20261028
```

- 取数阶段支持**断点续传**(已拉取的股票自动跳过),`--refresh` 全量重拉;
- 成分股来源:`--codes-file` > 通达信自定义板块(`xflt→XFLT`,`scqlt→XQLT`) > 本地缓存;
- 前提:本机通达信客户端已启动(fetch 阶段需要,process 阶段不需要)。

## 目录约定

| 目录 | 内容 | 是否入库 |
| --- | --- | --- |
| `data/<board>/` | 取数缓存:`quotes_long.csv`、`calendar.json`、`hs300.json`、`<board>_codes.json` | 否 |
| `output/<board>/` | 统计与图表产物:`result_stats.json`、`fig1/fig2`、净值序列 CSV | 否 |
| `archive/` | 历史回测报告(案例) | 是 |

## 口径

等权、每日再平衡;前复权收盘;单日有效成分股 < `--min-valid`(默认 100)时该日剔除;
基准沪深300(`000300.SH`)。按当前板块成分回溯存在幸存者偏差,不计交易成本;
结果仅供研究,不构成投资建议。
