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

## 追加记录(模板)

- [日期] 结论 | 证据/场景 | 对策
