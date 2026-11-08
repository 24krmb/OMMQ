# OMMQ 项目指南

> 给 AI Agent 的持久化项目指引。README.md 面向人类,本文件面向 Agent;两者冲突时以本文件为准。

## 项目定位

- 本地优先的 A股/期货投研工作台:行情取数 → 分析 → 结构化研报,产物统一落盘 `reports/`
- 数据源:通达信 tqcenter(主)、Akshare(补充)、TqSdk(期货,需快期账号)
- 所有面向用户的文本、图表必须使用**中文**;报告结尾注明"仅供参考,不构成投资建议"

## 环境

- Python 3.12,虚拟环境 `.venv/`(不入库),Windows 平台
- 运行脚本:`.\.venv\Scripts\python.exe <script>`
- 依赖全量锁定 `requirements.txt`;TqSdk 为可选依赖:`.\.venv\Scripts\python.exe -m pip install -r strategies/tqsdk/requirements.txt`
- 代码风格:Ruff,`line-length = 120`

## 数据与安全硬规则

- 期货凭证走环境变量 `TQ_ACCOUNT` / `TQ_PASSWORD`,**严禁写入任何文件、示例、日志或聊天**
- 期货当前行情优先 `KQ.m@` 主连;主连不能直接下单,交易需真实合约;历史回测按目标日期核实合约覆盖,不得用今天的 `expired` 状态排除历史合约
- API 会话(TqSdk 等)必须用上下文管理器或 `finally: api.close()` 释放
- `insert_order()` 返回不代表成交,`FINISHED` 也可能是撤单/拒单;以 `volume_left`、`last_msg`、成交记录为准
- 取数失败先排查(网络/账号/合约存续状态),仍失败则如实报告;**任何情况下不得编造数据**

## 脚本与产物

- `strategies/` 下脚本可独立运行:`stock/`(Akshare)、`futures/`(通达信)、`tqsdk/`(天勤)
- 图表产物统一写入 `reports/YYYYMMDD/`,编号规则见 `strategies/plot_paths.py`(核心八图 01–08、扩展研究图 09 起);**不要顺手修改编号规则**
- 财务 CSV 输出 `strategies/output/financials/`;日线缓存 `data/daily/`(parquet,`fetch_daily.py` 生成)
- 大体积产物不入库:`data/`、`backtest/data/`、`backtest/output/` 已在 `.gitignore`
- 正式报告落盘为 Markdown 至 `reports/`,须含结构化结论、关键数据表格与风险提示

## 绘图铁律

1. 每张图必须有标题、图例、坐标轴标签,不能用颜色或形状单独表达数据
2. 红涨绿跌;指定颜色:红 `#F36`、绿 `#0C9`、蓝 `#99F`、黄 `#FC3`、字体色 `#9999FF`
3. 不同数据系列用不同颜色,相同数据系列用相同颜色
4. 图表来源一律标注 `OMMQ`,不标注具体上游数据源
5. 优先复用根目录 `plot_utils.py` 与 `strategies/plot_paths.py` 的既有工具,勿重复造轮子

## 验证要求

- 修改任何取数/绘图脚本后,实际运行一次核对输出与图表,再宣称完成
- 报告中的关键数字必须与图表或原始数据交叉核对
- 涉及交易判断的内容附风险提示,不做确定性收益承诺
