---
name: market-close-analysis
description: A 股收盘分析工作流：运行 strategies 全套脚本（市场全景/情绪/资金/板块/轮动/期货）取数出图，读图核验关键数据，独立复核两融与指数收盘，生成图文并茂的收盘报告落盘 reports/（Markdown + 嵌入图表）。适用请求：收盘分析、收盘复盘、盘后总结、今日行情分析、执行收盘(日期)分析。
---

# A 股收盘分析工作流

> 以 OMMQ 仓库 `strategies/` 脚本套件为数据引擎，产出**图文并茂**的收盘分析报告并归档。

## 触发条件

用户要求执行收盘分析 / 收盘复盘 / 盘后总结 / 今日行情分析（可带日期，如"执行收盘(2026年10月19日)分析"）。

## 前置条件

- 工作目录必须是项目根目录（脚本输出路径基于根目录计算）。
- 无需通达信客户端：脚本基于 Akshare 公开数据源（新浪 / 申万 / 乐咕 / 中证指数 / 生意社）。
- 运行环境：`uv run python`（或 `.\.venv\Scripts\python.exe`）。

## 执行步骤

### 第 1 步：并行运行两个脚本批次（后台执行）

**批次 A —— A 股核心**（按序执行）：

```powershell
uv run python strategies/market_overview.py
uv run python strategies/market_sentiment.py
uv run python strategies/money_flow_trend.py
uv run python strategies/sector_top5_chart.py
uv run python strategies/sector_rotation_heatmap.py
```

**批次 B —— 行业估值与期货**（与批次 A 并行）：

```powershell
uv run python strategies/industry_valuation_percentile.py
uv run python strategies/futures_top5_chart.py
uv run python strategies/futures_volume_oi.py
uv run python strategies/futures_basis_spread.py
```

注意：
- 每个脚本用 `| Select-Object -Last N` 截取控制台尾部摘要即可，完整数字以第 3 步**读图**为准。
- Windows 控制台默认 GBK，中文输出会乱码；**不得**根据乱码猜数字，只取可辨识的数字部分，其余以读图核验。

### 第 2 步：确认产物

```powershell
Get-ChildItem strategies/output/*_<YYYYMMDD>.png
```

应得到 8 张图：`market_overview` / `market_sentiment` / `money_flow_trend` / `sector_top5` / `sector_rotation` / `futures_top5` / `futures_volume_oi` / `futures_basis`。

### 第 3 步：读图核验（关键，不得跳过）

用图片读取工具逐张查看 PNG，提取图表标题/标注中的准确数字。控制台乱码一律以图为准。

**已知易错点（读图时重点核对）：**
- 涨停家数存在两个口径：全市场宽口径（market_overview，如 50 家）vs 情绪口径（market_sentiment 标题，如 46 家），报告中并列注明。
- 行业轮动热力图数据滞后一天（窗口不含当日），报告需标注区间。
- 期货基差图的"现货基差"面板可能因现货源返回空而留空，属正常缺失。

### 第 4 步：独立复核关键数字（防止数据源口径污染）

用简短的内联 Python 复核（`uv run python -c`）：

1. **指数收盘**（A股/港股/美股最近两日）：
   - A 股：`ak.stock_zh_index_daily(symbol="sh000001" / "sh000300" / "sz399001" / "sz399006")`
   - 港股：`ak.stock_hk_index_daily_sina(symbol="HSI")`
   - 美股：`ak.index_us_stock_sina(symbol=".INX")`
   - 美股最新一行通常是上一交易日收盘（北京时间的"今天"美盘未收盘），报告中必须标注日期。
2. **两融**（官方核验，数据滞后 1 日）：
   `ak.stock_margin_sse(start_date, end_date)` → 融资余额逐日差分得净增/净偿还方向与金额。

### 第 5 步：生成图文报告

1. 复制 8 张图到报告目录（与 MD 同目录，保证相对路径嵌入在本地与 GitHub 均可显示）：
   建议按日期建子目录并按图序重命名（如 `reports/YYYYMMDD/01.png` … `reports/YYYYMMDD/08.png`），MD 用 `./01.png` 相对路径嵌入。
2. 报告文件：`reports/YYYYMMDD/market_close_analysis_YYYYMMDD.md`（按日期建子目录，MD 与图片同目录）。

**报告结构模板（七节）：**

```markdown
# A 股收盘分析 · YYYY-MM-DD（周X）
来源：24K-Claw ｜ 数据脚本：strategies/* ｜ 图表：已嵌入下文（另归档于 reports/ 与 strategies/output/）

## 核心摘要          ← 一段话定性（如"缩量分化修复日"），量能/情绪/资金三要素结论
## 一、指数表现      ← 表格：上证/沪深300/深成指/创业板/恒指/标普500 收盘与涨跌
                      60日归一终点 + 上周三大市场累计；嵌入图1（market_overview）
## 二、市场情绪      ← 涨平跌/涨跌停(两口径)/梯队/封板率 表格；涨停行业TOP；
                      与前一交易日对比；嵌入图2（market_sentiment）
## 三、行业与板块    ← 行业TOP5+概念TOP5；热力图区间累计结论；嵌入图3、图4
## 四、成交与杠杆资金 ← 成交额 vs 60日均值；两融官方核验数字与方向解读；嵌入图5
## 五、期货与衍生品  ← 商品涨跌TOP5表；螺纹量仓；股指贴水；嵌入图6、7、8
## 六、数据缺失与异常 ← 表格如实标注缺失项与原因（见下方已知故障清单）
## 七、解读与提示    ← 编号要点：反弹成色/风格判断/隔夜变量/商品信号
> 免责声明（固定文案）
```

每张图嵌入格式：`![标题](./文件名.png)`，下一行斜体 `*图N：一句话说明（含数据日期）*`。

### 第 6 步：收尾

- 向用户输出核心结论表（维度/关键数据/信号）与缺失项说明。
- **提交推送前必须先询问用户**，确认后 commit + push（SSH 远程 `origin`）。

## 已知故障与缺失清单（如实标注，不得编造）

| 项目 | 现象 | 处理 |
|------|------|------|
| 行业估值分位（申万接口） | JSON 解析错或长时间超时 | 重试一次；仍失败则在报告"数据缺失"节标注 |
| 商品现货基差（生意社/新浪现货） | 返回空 DataFrame | 标注缺失，历史走势面板不受影响 |
| 两融官方数据 | 滞后 1 日（T-1） | 用东财口径补最新一日并注明 |
| 行业轮动热力图 | 滞后一天 | 区间标注"截至 T-1" |
| 东方财富部分接口 | 本机限流 | 脚本已内置替代源，无需处理 |

## 输出规范（必须遵守）

- 全部文本中文；关键数据用表格；结论给出理由与不确定性。
- 红涨绿跌；配色：红 `#F36`、绿 `#0C9`、蓝 `#99F`、黄 `#FC3`、字体色 `#27254c`；图表来源统一 `24K-Claw`。
- 图表必须有标题、图例、坐标轴标签，不能仅靠颜色区分。
- 免责声明：本项目所有输出内容仅供研究与学习参考，不构成任何投资建议。
