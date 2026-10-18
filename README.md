# Oh My Mini Quant (OMMQ)

基于 OpenCode 平台+ 通达信软件+ Akshare。依托本机通达信客户端提供的 `tqcenter` 接口取数，由一组技能（Skill）驱动，完成从行情数据、财报分析到个股深度研究、估值与龙虎榜博弈的全流程投研任务，输出结构化研报。

> 所有数据均来自本机通达信客户端接口或用户提供的材料，**不编造数据**。本项目输出仅供研究与学习参考，**不构成任何投资建议**。

## 环境要求

- Windows 系统（`tqcenter` 接口仅在 Windows 下可用）
- 本机已安装并**启动**通达信客户端（TdxQuant 平台）
- `PYPlugins\user\tqcenter.py` 模块可用（Python 取数方式）
- 本地 HTTP 服务可达：`http://127.0.0.1:17709/`（JSON-RPC 取数方式）

## 依赖安装

项目使用 `.venv` 虚拟环境管理 Python 依赖（akshare 等）。`.venv/` 不入库。

```powershell
# 激活虚拟环境
.\.venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt

# 或直接使用虚拟环境中的解释器运行脚本
.\.venv\Scripts\python.exe your_script.py
```

首次创建虚拟环境（基于本机 Python 3.12）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip -r requirements.txt
```

## 目录结构

```
OMMQ/
├── .opencode/
│   ├── agents/TdxQuant.md        # 投研分析 Agent 定义
│   └── skills/                   # 技能集（取数 + 分析）
├── reports/                      # 生成的研报与图表产物
├── requirements.txt              # Python 依赖锁定文件
├── .venv/                        # 项目虚拟环境（已忽略，不入库）
└── .gitignore
```

## 技能清单

**数据获取类**（按需二选一，优先 `tdx-tq-local`）

| 技能 ID | 名称 | 说明 |
| --- | --- | --- |
| `tdx-tq-local` | 通达信 TQ-Local | 通过本机 HTTP 服务（JSON-RPC，`127.0.0.1:17709`）直接调用 `tqcenter` 接口，**首选** |
| `tdx-quant` | 通达信 TQ-Python | 生成 Python 代码，通过 `tqcenter.py` 模块与本地通达信客户端交互 |

**分析研究类**（按任务类型加载）

| 技能 ID | 名称 | 适用任务 |
| --- | --- | --- |
| `tdx-financial-quick-read` | 财报速读 | 三表关键指标提取、多期趋势对比、财务异常检测、盈利能力诊断与同业对标 |
| `tdx-stock-analysis` | 个股深度分析 | 单只 A 股全面研究，输出结构化一页纸报告（九大维度） |
| `tdx-gszddf` | 公司质地打分 | 长期质地结构化评估打分，区分"好公司"与"好股票"，辅助长线选股 |
| `tdx-valuation-navigator` | 估值导航员 | 估值方法选择、估值合理性、市场交易预期、重估/杀估值风险 |
| `tdx-dragon-tiger-miner` | 龙虎榜掘金 | 龙虎榜明细拆解、机构/北向/游资席位意图、买卖力量评分、三日榜分析 |
| `tdx-yjygby` | 业绩预告博弈 | 业绩发布前后的市场交易、预期差、博弈路径与多情景推演 |

## 工作流程

1. **明确任务类型**（取数 / 财报 / 个股研究 / 质地 / 估值 / 龙虎榜 / 业绩博弈），加载最匹配的分析技能。
2. **按技能流程执行**；需要行情、K 线、财务、龙虎榜等原始数据时，再加载 `tdx-tq-local` 或 `tdx-quant` 取数。
3. **数据请求失败时排查**：通达信客户端是否运行、HTTP 服务端口 `17709` 是否可达；仍失败则如实报告，不得编造。
4. **输出结构化结论**：关键数据用表格，评分/结论给出理由与不确定性，涉及交易判断时附风险提示。
5. **报告落盘**：正式报告保存为 Markdown 至 `reports/`，图表产物同样归档于此。

## 输出规范

- 所有文本使用中文；图表必须包含标题、图例、坐标轴标签，不能仅靠颜色或形状区分数据。
- 同一数据系列用相同颜色，不同系列用不同颜色；遵循红涨绿跌。
- 配色统一：红色 `#F36`、绿色 `#0C9`、蓝色 `#99F`、黄色 `#FC3`、字体色 `#9999FF`；图表来源统一标注 `24K-Claw`。

## 免责声明

本项目所有输出内容仅供研究与学习参考，不构成任何投资建议。投资有风险，据此操作风险自担，请结合自身风险承受能力独立决策。
