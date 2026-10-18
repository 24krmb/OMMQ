# Oh My Mini Quant (OMMQ)

基于 OpenCode 平台+ 通达信软件+ Akshare。依托本机通达信客户端提供的 `tqcenter` 接口取数，由一组技能（Skill）驱动，完成从行情数据、财报分析到个股深度研究、估值与龙虎榜博弈的全流程投研任务，输出结构化研报。

> 所有数据均来自本机通达信客户端接口或用户提供的材料，**不编造数据**。本项目输出仅供研究与学习参考，**不构成任何投资建议**。

## 项目简介

OMMQ 是一个**轻量级、本地优先**的 A 股投研工作台，不依赖云端数据服务，也不做自动化实盘交易。核心思路是：把专业的投研流程拆解成可复用的技能（Skill），由 Agent 按任务类型调度，最终产出结构化、可落盘的研报。

核心能力：

- **取数**：通过本地通达信 `tqcenter` 接口获取行情、K 线、财务、龙虎榜等原始数据
- **分析**：财报速读、个股深度研究、公司质地打分、估值研判、龙虎榜掘金、业绩预告博弈
- **补充数据源**：Akshare 作为第三方数据补充
- **量化计算与绘图**：pandas / numpy / scipy / TA-Lib 计算，matplotlib / seaborn 出图
- **产出归档**：正式报告与图表统一落盘至 `reports/`

## 技术栈

| 类别 | 组件 | 说明 |
| --- | --- | --- |
| 运行平台 | OpenCode / Trae | 加载 `.opencode` 下的 Agent 与技能 |
| 数据接口 | 通达信 TdxQuant（`tqcenter`） | 本地客户端取数，主数据源 |
| 第三方数据 | Akshare | 补充行情与宏观数据 |
| 数据处理 | pandas、numpy、scipy | 数据清洗、统计与计算 |
| 技术指标 | TA-Lib | 常用技术指标计算（预编译 wheel，无需额外 C 库） |
| 可视化 | matplotlib、seaborn | 研报图表输出 |
| 运行环境 | Python 3.12 | Windows |

## 环境要求

- Windows 系统（`tqcenter` 接口仅在 Windows 下可用）
- Python 3.12（项目虚拟环境 `.venv` 基于此版本创建）
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

依赖清单见 [requirements.txt](./requirements.txt)，已包含 akshare、pandas、numpy、scipy、TA-Lib、matplotlib、seaborn 等。

## 快速开始

1. 启动通达信客户端（TdxQuant 平台）并登录到主界面。
2. 确认本地 HTTP 服务可用：

   ```powershell
   curl -s --connect-timeout 3 -X POST "http://127.0.0.1:17709/" `
     -H "Content-Type: application/json; charset=utf-8" `
     -d '{"id":1,"method":"get_match_stkinfo","params":{"key_word":"茅台"}}'
   ```

   返回正常 JSON-RPC 响应即取数链路通畅。
3. 在 OpenCode / Trae 中打开本项目，直接用自然语言提问（见下方"常用提问示例"），Agent 会自动加载对应技能并调度取数。
4. 报告与图表产物归档至 `reports/`。

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

## 常用提问示例

| 想做什么 | 参考问法 | 触发技能 |
| --- | --- | --- |
| 快速看财报 | "看看 XX 的财报"、"XX 最近业绩怎么样"、"XX 现金流健康吗" | `tdx-financial-quick-read` |
| 个股深度研究 | "XX 股票怎么样"、"XX 投资逻辑"、"帮我研究一下 XX" | `tdx-stock-analysis` |
| 判断公司质地 | "公司质地"、"这家公司好不好"、"是不是好公司"、"壁垒强不强" | `tdx-gszddf` |
| 估值研判 | "XX 估值贵不贵"、"业绩超预期"、"增速下滑要不要杀估值" | `tdx-valuation-navigator` |
| 龙虎榜拆解 | "XX 上龙虎榜了吗"、"游资追踪"、"机构买了什么"、"三日榜" | `tdx-dragon-tiger-miner` |
| 业绩预告博弈 | "业绩预告"、"超预期还能涨吗"、"利空出尽"、"预告后还能买吗" | `tdx-yjygby` |

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

## 故障排查

| 现象 | 排查方向 |
| --- | --- |
| 取数请求失败 | 确认通达信客户端（`TdxW.exe`）已启动并登录到主界面 |
| 端口 `17709` 连接被拒 | 客户端未完全启动，或本地 HTTP 服务未就绪，重启客户端后重试 |
| `tqcenter` 导入失败 | 将通达信 `PYPlugins\user` 目录加入 `sys.path`，并优先使用 `sys.path.insert(0, ...)` |
| `talib` 导入报错 | 使用本项目的 `TA-Lib 0.8.2`（PyPI 预编译 wheel），`pip install -r requirements.txt` 即可，无需单独安装 C 库 |
| 数据缺失 | 如实标注缺失项，**不得编造**；必要时改用 Akshare 补充数据源 |

## 免责声明

本项目所有输出内容仅供研究与学习参考，不构成任何投资建议。投资有风险，据此操作风险自担，请结合自身风险承受能力独立决策。
