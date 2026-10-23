# UpdateLog

> 逆序列记录仓库重要变更；日常运行产物归档见 `reports/YYYYMMDD/`。

## 2026-10-24 · 图表布局治理（tight_layout 两大坑）与全景数据日期修复

**背景与根因**（matplotlib 3.11.2，源码级定位 `matplotlib/_tight_layout.py`）：

1. 向 gridspec 显式传入 `hspace`/`wspace`（`gridspec_kw` 或 `add_gridspec`）会经
   `GridSpec.locally_modified_subplot_params()` 将其 subplotspec 记为 `None`，
   `tight_layout` 据此判定 “Axes not compatible” 后**静默跳过整个布局**，
   子图顶部停留在默认边距 0.88，与 suptitle(≈0.98) 之间留出大片空白；
   而脚本头的 `warnings.filterwarnings("ignore")` 将警告吞掉，线下毫无感知。
2. `tight_layout` 仅在 `rect=None` 时自动为 suptitle 预留顶部空间；一旦显式传
   `rect`，其顶部余量=「自然余量(含 suptitle)」被再扣一次（双重预留），
   内容被额外压低 3%~5% 图高（单轴+colorbar 图实测同样存在，colorbar 本身不触发失效）。

**修复内容**：

| 文件 | 修复 | 效果（顶部净空白） |
|---|---|---|
| `strategies/stock_technical.py` | `hspace` 移出 gridspec_kw；去 `rect=(0,0,1,0.97)`；`suptitle y=0.995` | 109px/6.7% → 38px/2.11% |
| `strategies/market_overview.py` | 同上配方（`hspace/wspace` → `fig.subplots_adjust`）；去 `rect=(0,0,1,0.95)` | 5.03% → 2.96%（实测 40px） |
| `strategies/sector_rotation_heatmap.py` | 去 `rect=(0,0,1,0.96)`（colorbar 无需处理） | 主轴顶 0.8962 → 0.9362（5.75% → 1.75%） |
| `strategies/market_overview.py` | 「数据日期」改取**已抓取数据的最后一日**（`closes["上证指数"].index[-1].date()`） | 原 `latest_trade_date()` 异常兜底会在周末/瞬时网络失败时误标为当日（实测出现 10-24 误标，数据实至 10-23） |
| `plot_utils.py` | 核查无恙（无 suptitle、无 rect，本就自然路径） | — |

其余 12 个策略脚本无失效触发源（tight_layout 正常生效），仅存 “rect+suptitle” 双重预留带来的 2%~4% 轻度顶部空白，暂保留。

**数据复核**：关键数字读图 + akshare 内联复算一致——全景日报上证 3690.47、沪市成交额 8987 亿、涨/平/跌 4197/135/887、涨停 82（真实 78）、跌停 9（真实 6）；工商银行 601398 收盘 8.32（−3.14%）、MA5 8.45 / MA20 8.20 / MA60 7.89、RSI 56.9。当日产物目录 `reports/20261024/` 经用户整理后移除，本次不入库存档。

**并行改动披露**：`strategies/stock_technical.py` 的 MACD 周期由默认 (12, 26, 9) 调整为 (8.39, 17.52, 9.05)（用户会话内操作；两口径输出：柱 0.022 → 0.002，DIF 0.151 → 0.108）。

**附注**：`reports/20261023/` 旧归档已由用户移除整理（现存 `reports/20261019/`，本章不计）；`.opencode/Example/` 收录 601398 技术面示例图，README 同步增列「技术分析」展示位与「更新记录」入口。

## 2026-10-23 · 产物归档机制 + 全景日报

- 新增 `strategies/plot_paths.py`：全部策略脚本产物统一切换为 `reports/YYYYMMDD/` 编号命名（核心八图 01–08、扩展图 09 起、参数化脚本以代码作后缀），报告 Markdown 与图同目录嵌图。
- 15 个脚本中文字体统一五字体列表（Windows/macOS 双端验证）。
- 产出全景日报 `market_overview_20261023.md`、申万一级行业估值分位（数据截至 2026-09-30）、期货量仓图，均已归档。
- 相关提交：`addde9e`（plot_paths 与字体）、`d83607f`（SKILL.md 同步）、`4bbde31`（20261023 产物归档）。

## 2026-10-19 · 前次收盘分析

- 报告 `reports/20261019/market_close_analysis_20261019.md`（图片已迁移至 `.opencode/Example/`，见提交 `ebb6f53`）。
