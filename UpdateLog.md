# OMMQ 更新日志

> 数据来源：OMMQ 仓库（`main` 分支）Git 提交推送历史，共 28 次提交，已全部同步至远程 `origin/main`（github.com:24krmb/OMMQ.git）
> 类型说明：`feat` 新功能 / `fix` 问题修复 / `docs` 文档 / `chore` 杂项维护 / `merge` 分支合并
> 每个日期内按提交时间倒序排列（最新在前）

## 2026-10-24（5 次提交）

### 功能新增
- 新增约翰·内夫（John Neff）低 PE 价值投资策略脚本，覆盖选股 / 回测 / 监控 / 报告模板
- 新增 `strategies/plot_paths.py` 统一产物路径模块；17 个策略脚本完成接入，产物按编号写入 `reports/YYYYMMDD/`，并兼容 macOS 中文字体

### 文档
- 部分案例图片迁移至 `.opencode/Example/`（01、2–8 共 8 张），README 收录策略产物示例，并修正 20261019 收盘报告图片链接
- 收盘分析技能（market-close-analysis）同步产物新路径与核心八图编号规则

### 杂项
- 归档 20261023 策略脚本运行产物（market_overview / futures_volume_oi / industry_valuation 三图）
- 图表布局治理（tight_layout 两大坑）与全景数据日期修复

## 2026-10-23（8 次提交）

### 功能新增
- 新增通达信数据接口技能 `tdx-aidata`（v1.2.2，基于 tqs 跨平台取数）
- 统一绘图工具（补齐 `charts_demo` 依赖，兼容 macOS 字体回退）
- 新增 `plot_paths.py`：全部策略脚本产物统一切换为 `reports/YYYYMMDD/` 编号命名。

### 文档
- 调整 README 章节顺序（策略脚本 / 技能清单 / 目录结构前移，环境要求后移）
- 更新 README：技能清单收录 `tdx-aidata`、新增交互能力说明、快速开始步骤调整
-README 新增 Agent 章节，精简 `market_overview` 数据源说明（同步修改对应脚本）
- README Agent 章节补充目录小标题
- 重写 README Agent 章节（主代理 / 子代理说明、调用方式与创建示例）

### 杂项
- 策略脚本取数截止日期更新至 2026-10-23，并刷新 charts 四张产物图（折线 / 柱状 / 直方 / 热力）

## 2026-10-19（2 次提交）

### 功能新增
- 新增收盘分析技能（market-close-analysis）与 2026-10-19 图文收盘报告（含期货基差图与 7 张核心行情图）

### 问题修复
- 修正收盘报告图片链接（对应用户整理后的 `reports/20261019` 目录），技能路径约定同步更新

## 2026-10-18（13 次提交）

### 功能新增
- 新增三大指数周度累计收益曲线脚本 `global_index_week_curve.py`（沪深300 / 恒生指数 / 标普500），README 同步收录
- 新增 `strategies` 策略脚本体系：图表演示、期货基差 / 持仓前五 / 量仓、行业估值分位、市场总览、市场情绪、资金流向趋势、同业杜邦分析、行业轮动热力、行业资金前五、个股财务 / 财务年报 / 资金流 / 技术面共 14 个脚本，并附带首批运行产物

### 文档
- 新增 README 与依赖锁定文件 `requirements.txt`
- 完善 README
- README 收录 strategies 脚本说明
- 调整 README 说明

### 初始化 / 合并
- 新增 LICENSE（作者：王成）
- 合并远程 LICENSE 初始提交
- 初始化仓库：`.gitignore`、`.opencode/agents/TdxQuant.md` 代理、10 个 tdx 系列技能、YGHZ 等权曲线报告及自定义指标 / 数据目录占位
- 忽略自定义数据 / 自定义指标目录
- 补充 `.gitignore` 忽略自定义数据与自定义指标目录
- 统一绘图配色规范并调整报告标题（同步 TdxQuant 代理配置）
- 补充量化分析依赖

## 统计概览

| 维度 | 数值 |
| --- | --- |
| 提交总数 | 28 |
| 类型分布 | feat 7 / fix 1 / docs 11 / chore 8 / merge 1 |
| 按日分布 | 10-24（5）· 10-23（8）· 10-19（2）· 10-18（13） |

### 阶段里程碑
- **2026-10-18**：仓库初始化，落地 LICENSE、README、依赖清单与首批 14 个策略脚本
- **2026-10-19**：沉淀收盘分析技能，产出首份图文收盘报告
- **2026-10-23**：统一绘图工具 `plot_utils.py` 上线，新增 `tdx-aidata` 技能，README 完成章节重排与 Agent 章节建设
- **2026-10-24**：统一产物路径 `plot_paths.py` 接入全部策略脚本，新增约翰·内夫价值投资策略
