# Agent

> 给 AI Agent 的持久化项目指引。README.md 面向人类,本文件面向 Agent;两者冲突时以本文件为准。

## 执行任务前的铁律

1. If the user's question or request is too broad, vague, unclear, or contains factual conflicts, it is necessary to clarify the vague request through `question` and let the user decide among multiple implementation options to determine the user's preference;
2. Multi-step tasks must be executed through the sub-agent `general`;
3. OpenCode CLI The version must be ≥ `2.2.6`; otherwise, it won't run, and the user will be informed to upgrade or helped to upgrade to the latest version.

## Agent目录

| Agent      | 类别          | 用途                  |
| -------------| --------------| ----------------------------|
| Build | 主Agent| 启用了所有工具,适合需要完整文件操作和系统命令访问权限的日常工作|
| Plan | 主Agent| 专为代码分析和规划设计的受限代理。|
| TdxQuant | 子Agent | 通过通达信获取数,输出结构化研报。|
| Futures | 子Agent | 期货实盘量化任务路由:期货行情/回测/交易程序。|
| General | 子Agent| 适用于研究复杂问题和执行多步骤任务,也可以并行运行多个独立的工作单元。|
| Explore | 主Agent| 适合快速查找文件、搜索代码关键字或回答关于代码库结构的问题,速度快且不会产生副作用。|

## 脚本与产物

- `strategies/` 下脚本可独立运行:`stock/`、`futures/`、`tqsdk/`
- 图表产物统一写入 `reports/YYYYMMDD/`,编号规则见 `strategies/plot_paths.py`(核心八图 01–08、扩展研究图 09 起);**不要顺手修改编号规则**
- 财务 CSV 输出 `strategies/output/financials/`;
- 日线缓存 `data/daily/`(parquet,`fetch_daily.py` 生成)
- 大体积产物不入库:`data/`、`backtest/data/`、`backtest/output/` 已在 `.gitignore`
- 产物、正式报告落盘至 `reports/`,须含结构化结论、关键数据表格与风险提示

## 绘图铁律

1. Each figure must have a title, legend, and axis labels, and data cannot be expressed solely by color or shape.
2. Red rises, green falls; specified colors: red `#F36`, green `#0C9`, blue `#99F`, yellow `#FC3`, font color `#9999FF`
3. Different data series use different colors, and the same data series uses the same color.
4. All charts should be labeled `OMMQ`, without specifying the exact upstream data source.
5. 优先复用根目录 `plot_utils.py` 与 `strategies/plot_paths.py` 的既有工具,勿重复造轮子
6. All user-facing text and charts must be in **Chinese**; at the end of the report, indicate "For reference only, not investment advice"

## 数据与安全硬规则

- Futures credentials use the environment variables `TQ_ACCOUNT` / `TQ_PASSWORD`, **strictly prohibited from writing to any files, examples, logs, or chats**
- For the current futures market, give priority to `KQ.m@` main continuous contract; you cannot place orders directly on the main continuous contract, trading requires real contracts; for historical backtesting, verify contract coverage according to the target date, and do not use today's `expired` status to exclude historical contracts
- API sessions (TqSdk, etc.) must be released using a context manager or `finally: api.close()`
- `insert_order()` 返回不代表成交,`FINISHED` 也可能是撤单/拒单;以 `volume_left`、`last_msg`、成交记录为准
- If data retrieval fails, first check (network/account/contract status). If it still fails, report truthfully; **under no circumstances should data be fabricated**

## memory 记忆

| 场景 | 做法 |
| --- | --- |
| 新经验 / 新坑 | 用户说“记一下：xxx”,按 `结论 \| 证据 \| 对策` 格式追加，带日期 |
| 旧知识失效 | 告诉我，我会删掉对应条目(记忆库约定：过时即删) |
| 新主题 | 想分门别类时新建 `.opencode/memory/<主题>.md` 即可自动纳入 glob(下次配置变更后生效) |
| AGENTS.md vs 记忆库 | **规则/铁律**写 `AGENTS.md`(全文覆盖)；**事实/经验/结论**进 memory(增量追加) |

## 验证要求

- 修改任何取数/绘图脚本后,实际运行一次核对输出与图表,再宣称完成
- 涉及交易判断的内容附风险提示,不做确定性收益承诺
