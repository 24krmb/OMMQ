# Agent

> 给 AI Agent 的持久化项目指引。README.md 面向人类,本文件面向 Agent;两者冲突时以本文件为准。
> 记忆库 `.opencode/memory/*.md` 由 opencode.json `instructions` 注入,每次会话自动生效(事实/经验/结论进记忆,规则/铁律写本文件)。

## 执行任务前的铁律

1. 用户需求宽泛、模糊、表达不清或事实冲突时,必须用 `question` 澄清,在多个实现方案间让用户做决定;
2. 多步任务必须通过子代理 `general` 执行;
3. OpenCode CLI 版本须 ≥ `2.2.7`,否则提示用户升级或协助升级。

## 环境(平台差异,最易踩坑)

- Windows 用 `.\.venv\Scripts\python.exe`,macOS/Linux 用 `.venv/bin/python`;`.venv` 不入库,本机缺失时先 `python3 -m venv .venv` 再装依赖。
- Python ≥ 3.12;依赖以根目录 `requirements.txt` 全量锁定(akshare、TA-Lib 0.8.3 预编译 wheel 无需装 C 库);**不要改锁定版本**。
- tqcenter 本地 HTTP(`127.0.0.1:17709`,JSON-RPC)仅 **Windows 通达信客户端**可用;macOS/Linux 取数改用 `tdx-aidata`(libTdxAiData.dylib)、gildata-aidata 远程 MCP(需用户级环境变量 `GILDATA_API_KEY`,`{env:...}` 在服务启动时解析,改密钥后必须重启 OpenCode)或 akshare。
- tqsdk 为可选依赖(固定 3.10.4):`pip install -r strategies/tqsdk/requirements.txt`;快期账号走 `YOUR_ACCOUNT` / `YOUR_PASSWORD` 环境变量。

## 脚本与产物

- 脚本从**仓库根目录**运行:`.venv/bin/python strategies/stock/xxx.py [参数]`,参数见脚本头部注释。
- 图表统一写入 `reports/YYYYMMDD/`,编号规则见 `strategies/plot_paths.py`(核心八图 01–08、扩展图 09 起、参数化脚本以代码为后缀如 `10_600519.png`);**不要顺手修改编号规则**。报告正文用相对路径 `./<NN>.png` 嵌图。
- 复用工具前先把仓库根加入 `sys.path`:`sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))`,再 `from plot_paths import report_image_path`(根目录 `plot_utils.py` 同理),勿重复造轮子。
- 财务 CSV → `strategies/output/financials/`;日线缓存 → `data/daily/`(parquet,`fetch_daily.py` 生成)。
- 以下均为运行产物、**不入库**:`reports/`、`strategies/output/`、`data/`、`backtest/data|output/`、`自定义数据/`、`自定义指标/`、`neff_value_strategy_tdx.py`(开发中)。需长期保留的案例放 `.opencode/Example/` 或 `backtest/archive/`(这两个入库)。
- 回测入口 `backtest/equal_weight_backtest.py`:fetch/process/all 三阶段,`--board xflt|scqlt`,fetch 需本机通达信在线(process 不需要),支持断点续传。

## Agent 调度

- 主 Agent:Build(默认)/ Plan / Explore;子 Agent:TdxQuant(通达信投研)、Futures(TqSdk 期货)、General(多步任务)。定义在 `.opencode/agents/`。
- 技能在 `.opencode/skills/`,按任务类型加载:取数 tdx-tq-local/tdx-quant/tdx-aidata;分析 tdx-financial-quick-read / tdx-stock-analysis / tdx-gszddf / tdx-valuation-navigator / tdx-dragon-tiger-miner / tdx-yjygby;收盘复盘 market-close-analysis;期货 tqsdk-trading-and-data;热点 a-market-hotspot-discovery(走 gildata-aidata)。
- 投研任务优先复用 `strategies/` 下现成脚本,再走技能取数。

## 绘图铁律

1. 每张图必须有标题、图例、坐标轴标签,不能仅靠颜色或形状表达数据;
2. 红涨绿跌;配色统一:红 `#F36`、绿 `#0C9`、蓝 `#99F`、黄 `#FC3`,字体色 `#9999FF`;
3. 不同数据系列不同色,同一系列同色;
4. 图表来源一律标注 `OMMQ`,不标注具体上游数据源;
5. 所有面向用户的文本与图表用**中文**;报告结尾注明"仅供参考,不构成投资建议"。

## 数据与安全硬规则

- 期货凭据只用环境变量 `YOUR_ACCOUNT` / `YOUR_PASSWORD`,**严禁写入任何文件、示例、日志或聊天**;
- 当前期货行情优先 `KQ.m@` 主连;**主连不能直接下单**,交易须用真实合约;历史回测按目标日期核实合约覆盖,不能用今天的 `expired` 状态排除历史合约;
- API 会话(TqSdk 等)必须用上下文管理器或 `finally: api.close()` 释放;
- `insert_order()` 返回不代表成交,`FINISHED` 也可能是撤单/拒单;以 `volume_left`、`last_msg`、成交记录为准;
- 数据取数失败先排查(网络/账号/客户端在线/合约状态),仍失败则如实报告;**任何情况下不得编造数据**。

## memory 记忆

| 场景 | 做法 |
| --- | --- |
| 新经验 / 新坑 | 用户说"记一下:xxx"时,按 `结论 \| 证据 \| 对策` 格式追加到对应记忆文件,带日期 |
| 旧知识失效 | 告诉用户,由用户删除对应条目(过时即删) |
| 新主题 | 新建 `.opencode/memory/<主题>.md` 即自动纳入 glob(下次配置变更后生效) |
| AGENTS.md vs 记忆库 | **规则/铁律**写本文件(全文覆盖);**事实/经验/结论**进 memory(增量追加) |

## 验证与提交

- 修改任何取数/绘图脚本后,**实际运行一次**核对输出与图表,再宣称完成;
- 涉及交易判断的内容附风险提示,不做确定性收益承诺;
- 提交信息用约定式提交:`<type>: <subject>`(feat/fix/docs/refactor/test/chore/build/ci/style),主题用中文、简洁明了。
