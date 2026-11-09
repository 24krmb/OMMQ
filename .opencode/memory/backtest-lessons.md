# 回测教训(backtest-lessons)

> OMMQ 记忆库:回测相关的约定、教训与结论。每个新会话自动注入。
> 维护约定:每条 = `- [日期] 结论 | 证据/场景 | 对策`;过时条目及时删除。

## 既有约定(自 README)

- [2026-11-09] A 股等权回测入口:`backtest/equal_weight_backtest.py`,三阶段 fetch/process/all,`--board xflt|scqlt` 参数化,支持断点续传;板块成分取数需**本机通达信**在线。历史报告归档 `backtest/archive/`,详见 `backtest/README.md`。
- [2026-11-09] 回测缓存与产物不入库:`backtest/data/`、`backtest/output/` 均在 `.gitignore`。
- [2026-11-09] 期货回测/实盘走 TqSdk(`strategies/tqsdk/`),规则约束见 AGENTS.md"数据与安全硬规则"(主连不可下单、FINISHED 需核验成交量、API 必须 close)。

## 待沉淀(下次回测后补充)

- [日期] 结论 | 证据/场景 | 对策

## 追加记录(模板)

- [日期] 结论 | 证据/场景 | 对策
