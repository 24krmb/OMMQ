## 策略脚本

`strategies/` 下的脚本**独立于技能体系**,直接用拉取数据并出图,可单独运行或作为取数参考。图表产物按**当天日期**统一写入 `reports/YYYYMMDD/`;

| 脚本 | 用途 |
| --- | --- |
| stock/market_overview.py | A 股市场全景日报:四大指数走势(归一化)+ 成交额 + 涨跌家数 |
| stock/market_sentiment.py | 市场情绪:涨停/跌停家数趋势、连板梯队、涨停行业分布 |
| stock/money_flow_trend.py | 杠杆资金(两融)趋势:融资余额、两融余额、单日净增 |
| stock/sector_top5_chart.py | 申万一级行业 / 概念板块 涨跌幅 TOP5 |
| stock/sector_rotation_heatmap.py | 申万一级行业板块轮动热力图(行=行业,列=交易日) |
| stock/industry_valuation_percentile.py | 申万一级行业 PE / PB 当前值及近 5 年历史分位 |
| stock/stock_financials.py | 个股财务:主要指标 + 三大报表(季度口径),导出 CSV 并出图 |
| stock/stock_financials_annual.py | 年度财务概览:营收 / 净利 / EPS / ROE 长周期趋势 |
| stock/stock_money_flow.py | 个股资金流 |
| stock/stock_technical.py | 个股技术面:日 K + MA5/20/60 + 成交量 + MACD + RSI |
| stock/peer_dupond.py | 同业杜邦分析 / 财务估值横向对比 |
| stock/charts_demo.py | 绘图示例:折线、柱状、直方、热力图各一张 |
| stock/sector_equal_weight_curve.py | 自定义板块收益回测分析案例(**需本机通达信**取板块成分) |
| stock/neff_value_strategy.py | John Neff低PE价值投资策略/选股/回测/监控/模板 4 个功能全部内置在里面 |
| stock/plot_ashare_indices_60d.py | A股主要宽基指数近60个交易日累计收益率对比图|
| futures/futures_basis_spread.py | 期货基差与跨期价差:期货 vs 现货、近月 vs 远月、股指基差 |
| futures/futures_top5_chart.py | 国内商品期货主力合约 涨幅/跌幅 TOP5 |
| futures/futures_volume_oi.py | 期货量仓:主力合约成交量与持仓量、日增仓 |
| futures/stock_index_basis.py | 股指期货期现基差与升贴水分析 |
| global/global_index_week_curve.py | 全球三大指数周度累计收益曲线:沪深300 / 恒生指数 / 标普500 |
| global/global_index_5y_mdd.py | 标普500 vs 沪深300:近5年累计收益与最大回撤对比 |
| global/trend_charts.py | 近三年“费半”、“七姐妹”走势对比图 |
| global/plot_global_indices_60d.py | 全球主要股指近60个交易日累计收益率对比图 |
| global/plot_spx_vix_60d.py | 标普500 近60个交易日累计收益+ VIX 恐慌指数 |
| global/plot_acwi_ftseaw_60d.py | MSCI ACWI vs 富时All-World 近60个交易日累计收益+ 两者收益差|
| global/plot_apac_indices_60d.py | 亚太主要股指近60个交易日累计收益率对比图 |
| global/plot_euro_indices_60d.py | 欧洲主要股指近60个交易日累计收益率对比图 |
| global/plot_gold_silver_ratio_120d.py | 国际金银比近120个交易日走势 + 比值最大回撤 |
| fetch_daily.py | 本地日线行情缓存:data/daily/ 按证券代码分文件(parquet) |

**共享模块**:`plot_paths.py`(产物编号归档规则)、`global/gindex_fetch.py`(指数多源降级取数 + 中文字体回退,供 `global/` 下五个 60 日脚本与 `stock/plot_ashare_indices_60d.py` 复用;A股另有 `csindex_a`(中证官网)/`cni_a`(国证官网)兜底源);`global/plot_gold_silver_ratio_120d.py` 只复用其 `_series`(序列清洗)与 `setup_font`,金银比按"配对"降级、不走 `fetch_index`;均不属于脚本清单,不单独运行。

**回测**:`backtest/equal_weight_backtest.py` 提供自定义板块等权指数回测(通达信数据,`--board xflt|scqlt` 参数化,fetch/process/all 三阶段,支持断点续传),历史报告见 `backtest/archive/`,详见 `backtest/README.md`。