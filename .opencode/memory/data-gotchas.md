# 数据取数备忘(data-gotchas)

> OMMQ 记忆库:取数相关的平台特性、坑与结论。每个新会话自动注入。
> 维护约定:每条 = `- [日期] 结论 | 证据/场景 | 对策`;过时条目及时删除。

## OpenCode 与工具环境

- [2026-11-09] `opencode.json` 的 `{env:VAR}` 在**服务进程启动时**解析;改用户级环境变量(如 `GILDATA_API_KEY`)后必须重启 OpenCode 服务才生效,重启会中断执行中的 shell 会话,属正常现象。诊断入口:`opencode mcp list` 出现 401 `InvalidApiKey` ≈ 密钥没进服务进程。
- [2026-11-09] gildata-aidata MCP 凭据存用户级环境变量 `GILDATA_API_KEY`(setx 写入),配置文件只引用 `{env:...}`,不落盘。

## 数据源

- [2026-11-09] 通达信 tqcenter 走本机 HTTP(`127.0.0.1:17709`,JSON-RPC),报错先确认通达信客户端已启动。
- [2026-11-09] Akshare Interface signatures/fields may change with versions. If the scripts under `strategies/stock/` report errors when fetching data, first check whether the interface has been renamed; only then consider code issues.
- [2026-11-09] TqSdk 为可选依赖(pyproject 固定 3.10.4),安装用 `.\.venv\Scripts\python.exe -m pip install -r strategies/tqsdk/requirements.txt`;快期账号走 `YOUR_ACCOUNT` / `YOUR_PASSWORD` 环境变量。
- [2026-11-09] 日线缓存 `data/daily/`(parquet,按证券代码分文件,`fetch_daily.py` 生成),仅 Windows 本机,不入库。
- [2026-11-18] akshare 1.20.44 起批量更名了一批指数接口,旧名仍可调用但会抛"已在 1.20.44 更名"异常:IndexDaily 类 `stock_zh_index_daily`→`index_zh_daily_sina`、`stock_hk_index_daily_sina`→`index_hk_daily_sina`、`index_us_stock_sina`→`index_us_daily_sina`;实时快照 `stock_zh_index_spot_sina`→`index_zh_spot_sina`、`stock_zh_index_spot_em`→`index_zh_spot_em` | 证据:2026-11-18 收盘复核实测(本机 akshare 1.20.65,与 requirements.txt 锁定版本一致);scripts 套件本身未受影响 | 对策:写一次性复核脚本时直接用新名;报错信息里会给出替代名,按其提示改名即可,不要误判为代码 bug 或降版本
- [2026-11-18] 新浪 A 股指数日线偶尔当日缺行(如 2026-11-18 的 sz399001/sz399006 只到 11-17),`index_zh_daily_sina` 静默返回旧数据不报错 | 证据:当日复核脚本 last date 停在 11-17,而 `index_zh_spot_sina` 已有 11-18 收盘 | 对策:收盘复核先看 `date` 最后一行的日期,若早于当日则用 `index_zh_spot_sina` 的"最新价/昨收/成交额"补齐并标注口径
- [2026-11-18] 东方财富 push2 行情接口易触发 IP 限流(`index_zh_spot_em` 报连接断开),限流后约 5 分钟恢复,重复调用会延长封禁 | 证据:2026-11-18 与新浪接口同时调用时触发 | 对策:同一时刻只跑一个行情源;复核优先用新浪,东财留给脚本内置或稍后重试

## 追加记录(模板)

- [日期] 结论 | 证据/场景 | 对策
