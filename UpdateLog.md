# OMMQ 更新日志

## 2026-11-19

### 新增脚本
| 脚本 | 用途 |
| --- | --- |
| global/plot_acwi_ftseaw_60d.py | MSCI ACWI vs 富时All-World 近60个交易日累计收益+ 两者收益差(ETF 代理:ACWI / VT) |

### 取数备忘
- MSCI ACWI、富时 All-World 均为授权指数:akshare 无对应接口,东财全球指数清单(56 个)亦不含;本机雅虎 403、markets.ft.com 连接超时、stooq 返回 JS 校验页,故改用**同在美国收盘定价**的两只 ETF 作代理——ACWI(iShares MSCI ACWI)、VT(Vanguard Total World;基准为 FTSE Global Small Cap,即在 All-World 大中盘之外另含小盘)
- 代理序列取数:新浪 `stock_us_hist_sina` → StockAnalysis(`api.stockanalysis.com/api/symbol/e/<代码>/history`)依次降级;两源最新收盘一致,且都是未复权价(价格指数口径,不含分红),两序列取公共交易日交集对齐,不存在跨时区快照错位
- 图例直接写 `VT(富时全球小型股)` 而非指数名,避免误读为富时 All-World 指数本身

### 目录调整
- 新建 `strategies/global/`,6 个全球市场脚本从 `strategies/stock/` 迁入:`plot_global_indices_60d.py`(编号 16)、`plot_spx_vix_60d.py`(27)、`plot_acwi_ftseaw_60d.py`(28)、`global_index_week_curve.py`(15)、`global_index_5y_mdd.py`(22)、`trend_charts.py`(17–20);同层平移不动代码,`sys.path` 注入与 `plot_paths` / `plot_utils` 的复用关系不变,README 与 `strategies/README.md` 表内前缀、各脚本 docstring 的用法行同步改为 `strategies/global/`
- **撞号修正**:`trend_charts.py` 的四张图占用 17/18/19/20(编号写在 `groups` 的 `no=` 字段,此前只按 `OUT_NO` 与 `report_image_path(N)` 扫描因而漏掉),导致 `plot_spx_vix_60d.py` 的 17、`plot_acwi_ftseaw_60d.py` 的 18 与它重复;现改为 17→27、18→28,全库编号恢复唯一(1–28 连续无缺口)

## 2026-11-18 (V1.2.1)

### 绘图
- 全库绘图脚本统一字体色:图表标题与坐标文字(轴标签/刻度/图例)由 `#9999FF` 改为 `#27254c`(rgb(39,37,76)),涉及 `strategies/` 下 20 个绘图脚本、`backtest/equal_weight_backtest.py` 与共享模块 `plot_utils.py`(原已达标);`global_index_5y_mdd.py`、`equal_weight_backtest.py` 补齐颜色配置
- 双轴图中原随数据系列着色的轴标签/刻度(如 `futures_volume_oi.py`、`peer_dupond.py`)同步改为统一字体色
- 同步更新文档中的配色规范:AGENTS.md、README.md、`.opencode/agents/TdxQuant.md`、`.opencode/agents/Futures.md`

### 新增脚本
| 脚本 | 用途 |
| --- | --- |
| stock/plot_global_indices_60d.py | 全球主要股指近60个交易日累计收益率对比图 |
| stock/plot_spx_vix_60d.py | 标普500 近60个交易日累计收益+ VIX 恐慌指数 |

### 文档
- 新增 `docs/` 目录:本地收录 OpenCode 官方文档 24 篇(英文原文),覆盖平台/CLI/Console、配置与权限、Agent/技能/命令/插件、模型与 Provider、上下文与会话机制等主题
- README 新增"OpenCode 文档(docs/)"章节作为 24 篇文档的中文索引;目录结构纳入 `docs/`,并合并目录树中重复列出的 `.opencode/` 块
- 版本号升至 V1.2.1(pyproject.toml 已同步)

## 2026-11-17 (V1.2.0)

1. 适配 akshare 1.20.65 接口重构:17 个接口改名/参数变更,财务脚本适配器同步更新
2. 更新依赖锁定版本(requirements.txt)
3. README 完善 macOS/Linux 说明

## 2026-11-17

### 问题修复
- `stock_index_basis.py` 补 macOS 字体回退(原仅配置 Windows 字体,macOS 下中文渲染为方块)
- 扩展图编号撞号治理(全库编号恢复唯一):`sector_equal_weight_curve.py` 09→21、`global_index_5y_mdd.py` 15→22、`futures_sector_review.py` 09/10/11/12→23/24/25/26;`industry_valuation_percentile.py` 保持 09 不变
- `.gitignore` 纳入 `strategies/stock/neff_output/`(内夫策略运行产物不入库)
- `stock_technical.py` 改为在全历史上计算 MA/MACD/RSI 后再截取展示窗口,消除指标热身期缺失;头注释 MACD 参数与代码对齐(快8.39/慢17.52/信号9.05)
- `backtest/equal_weight_backtest.py` 断点续传加固:取数区间参数(--end/--years)变更时中止并提示 `--refresh`;自动丢弃上次崩溃留下的截断残行并补取;process 阶段读取 fetch_errors.json 告警缺失成分;process 按 `<board>_codes.json` 过滤 CSV 中已移出板块的过期成分

## 2026-11-09 (V1.1.0)

1. 完善持久化记忆机制
注意区分：旧会话恢复 ≠ 新会话继承。`--continue` 能接着聊，但开一个全新会话时，历史对话内容不会自动进来 —— 只有 `AGENTS.md`、skills、agents 这些磁盘文件才会每次必载。

2. 配置 `instructions` 数组 glob,一个专门的记忆目录：
`data-gotchas.md` 取数备忘
`backtest-lessons.md`回测教训(入口/断点续传/产物归档/约束)

3. Agent 自己以后会怎么用？解读

4. 其他更新
完善文档说明，完善约束，完善铁律，更新版本号

## 2026-11-08 (V1.0.0)

### 问题修复(目录重构遗留清理)
- 修复 4 个期货脚本无法运行的问题:`plot_paths.py` 上移至 `strategies/`(与文档声明一致),stock/futures 共 20 个脚本统一加入 `sys.path` 引导;`report_dir` 改为锚定仓库根,不再依赖运行时 CWD
- 同步 README 与 `market-close-analysis` 技能中重构后的脚本路径;修正运行示例、目录结构(移除从未存在的 `backtest/run.py`、`screening/screen.py`)、重复段落与笔误
- 重建损坏的 `.venv`(原基于已卸载的第三方 Python 创建,无法启动);`requirements.txt` 补充 `pyarrow==26.0.1`(`fetch_daily.py` 落盘 parquet 必需)并去除 BOM
- 数据源边界标注:`sector_equal_weight_curve.py` 需本机通达信客户端取板块成分,README 表格与脚本头注释已标注;`.gitignore` 为 `neff_value_strategy_tdx.py` 补充说明
- 新增脚本导入冒烟验证:strategies 下 24 个脚本全部通过,期货 TOP5 脚本端到端跑通

### 回测目录合并
- `backtest_xflt/` 与 `backtest_scqlt/` 两套重复脚本合并为参数化 `backtest/equal_weight_backtest.py`:`fetch / process / all` 三阶段,`--board xflt|scqlt` 一键切换;成分股改为实时读取通达信自定义板块(不再依赖 %TEMP% 下已被清理的临时 JSON),基准修正为 `000300.SH`,支持断点续传,process 阶段无需通达信在线
- 验证:XFLT 迁移旧数据重算,全部统计指标与原结果**逐位一致**;SCQLT 全新拉取(204 只,0 缺失),与原结果差异仅为前复权数据正常重算(累计收益 0.04pp)
- 历史回测报告与图迁移至 `backtest/archive/{xflt,scqlt}/`(入库案例),原两目录删除;用法见 `backtest/README.md`

### 归档策略统一(.gitignore)
- 移除全局 `*.csv` / `*.html` 忽略(及被其覆盖的 `backtest_*/quotes_long.csv` 冗余规则),改为按产物目录排除:`reports/`、`strategies/output/`、`backtest/data|output/`、`data/`;技能 HTML 报告模板、财务 CSV 等共享资产不再被误伤
- `git rm -r --cached` 取消跟踪 `reports/` 与 `strategies/output/` 中历史产物(文件保留本地);README 案例图仍保留于 `.opencode/Example/`
- 确认 `neff_value_strategy_tdx.py` 开发中、暂不入库,`.gitignore` 注释同步

### 量化(tqsdk)接入与技能新增
- 新技能 `tqsdk-trading-and-data`(行情/回测/交易专题参考 + 环境体检脚本)与子代理 Futures(天勤任务路由)；
- 新技能 `a-market-hotspot-discovery`热点资讯/热门板块/热门股票多维监测 → 结构化热点报告；
- 新增 `strategies/tqsdk/` 脚本目录并统一 snake_case 命名:`trix_strategy.py`(主连行情 + 自动换月移仓)、`trix_strategy_index.py`(单合约对照版)、`vwap_order.py`(VWAP 算法单示例)
- 修复:Futures 权限模式大小写(`TqSdk-*` → `tqsdk-*`,否则技能加载被拒)、工作流程指向不存在的 `trading-strategy` 目录、过期合约回测(MA701/fu2701 → 运行时解析主连 `underlying_symbol`)、`TqAuth` 占位符硬编码 → 环境变量 `YOUR_ACCOUNT`/`YOUR_PASSWORD` 友好校验
- 补充 `strategies/tqsdk/README.md`(前置条件/脚本清单)与 `requirements.txt`(`tqsdk==3.10.4`,按需安装,不进主 requirements);README 技能清单/Agent 目录/目录结构/环境要求同步

### 来源标注统一
- 图表/报告来源标注一律 `OMMQ`(取代 24K-Claw / 24KRMB.COM / "数据来源:通达信 tqcenter" 等写法);通过 Akshare 等公开源取数时**不标注具体上游来源**,只显示 `来源:OMMQ`
- 覆盖:12 个策略脚本图注、backtest 回测图脚注(口径信息保留)、2 个技能 HTML 报告模板、归档回测报告、README 输出规范、TdxQuant/Futures Agent 绘图铁律、market-close-analysis 技能输出规范

### 工程化
- 新增轻量 `pyproject.toml`:仅项目元数据(name / version / requires-python>=3.12 / license)与工具配置(`[tool.uv] package=false` 非打包声明、`[tool.ruff]` 预留),不构建发行包;依赖仍以 `requirements.txt` 全量锁定为准,tqsdk 建模为可选依赖

## 2026-11-07

新增：近三年“费半”、“七姐妹”走势对比图一键生成脚本  `trend_charts.py`

## 2026-10-28

- 新增本地日线行情缓存 `data/daily/`(parquet,按证券代码分文件)与增量更新脚本 `quant/fetch_daily.py`(数据源,同日去重覆盖,支持 `--refresh` 全量重拉)
- `requirements.txt` 补充 `pyarrow`(parquet 读写引擎)

## 2026-10-26

1. 新增量化策略目录
2. 新增股指期货期现基差与升贴水分析 `stock_index_basis.py`
3. 新增自定义板块收益回测分析案例  `sector_equal_weight_curve.py `   

## 2026-10-24(5 次提交)

### 功能新增
- 新增约翰·内夫(John Neff)低 PE 价值投资策略脚本,覆盖选股 / 回测 / 监控 / 报告模板
- 新增 `strategies/plot_paths.py` 统一产物路径模块；17 个策略脚本完成接入,产物按编号写入 `reports/YYYYMMDD/`,并兼容 macOS 中文字体

### 文档
- 部分案例图片迁移至 `.opencode/Example/`(01、2–8 共 8 张),README 收录策略产物示例,并修正 20261019 收盘报告图片链接
- 收盘分析技能(market-close-analysis)同步产物新路径与核心八图编号规则

### 杂项
- 归档 20261023 策略脚本运行产物(market_overview / futures_volume_oi / industry_valuation 三图)
- 图表布局治理(tight_layout 两大坑)与全景数据日期修复

## 2026-10-23(8 次提交)

### 功能新增
- 新增通达信数据接口技能 `tdx-aidata`(v1.2.2,基于 tqs 跨平台取数)
- 统一绘图工具(补齐 `charts_demo` 依赖,兼容 macOS 字体回退)
- 新增 `plot_paths.py`:全部策略脚本产物统一切换为 `reports/YYYYMMDD/` 编号命名。

### 文档
- 调整 README 章节顺序(策略脚本 / 技能清单 / 目录结构前移,环境要求后移)
- 更新 README:技能清单收录 `tdx-aidata`、新增交互能力说明、快速开始步骤调整
-README 新增 Agent 章节,精简 `market_overview` 数据源说明(同步修改对应脚本)
- README Agent 章节补充目录小标题
- 重写 README Agent 章节(主代理 / 子代理说明、调用方式与创建示例)

### 杂项
- 策略脚本取数截止日期更新至 2026-10-23,并刷新 charts 四张产物图(折线 / 柱状 / 直方 / 热力)

## 2026-10-19(2 次提交)

### 功能新增
- 新增收盘分析技能(market-close-analysis)与 2026-10-19 图文收盘报告(含期货基差图与 7 张核心行情图)

### 问题修复
- 修正收盘报告图片链接(对应用户整理后的 `reports/20261019` 目录),技能路径约定同步更新

## 2026-10-18(13 次提交)

### 功能新增
- 新增三大指数周度累计收益曲线脚本 `global_index_week_curve.py`(沪深300 / 恒生指数 / 标普500),README 同步收录
- 新增 `strategies` 策略脚本体系:图表演示、期货基差 / 持仓前五 / 量仓、行业估值分位、市场总览、市场情绪、资金流向趋势、同业杜邦分析、行业轮动热力、行业资金前五、个股财务 / 财务年报 / 资金流 / 技术面共 14 个脚本,并附带首批运行产物

### 文档
- 新增 README 与依赖锁定文件 `requirements.txt`
- 完善 README
- README 收录 strategies 脚本说明
- 调整 README 说明

### 初始化 / 合并
- 新增 LICENSE(作者:王成)
- 合并远程 LICENSE 初始提交
- 初始化仓库:`.gitignore`、`.opencode/agents/TdxQuant.md` 代理、10 个 tdx 系列技能、YGHZ 等权曲线报告及自定义指标 / 数据目录占位
- 忽略自定义数据 / 自定义指标目录
- 补充 `.gitignore` 忽略自定义数据与自定义指标目录
- 统一绘图配色规范并调整报告标题(同步 TdxQuant 代理配置)
- 补充量化分析依赖