# -*- coding: utf-8 -*-
"""
================================================================================
 约翰·内夫(John Neff)低PE价值投资策略 —— 全A股实战脚本（三合一：选股/回测/持仓监控）
================================================================================

【策略理念 —— 严格遵循约翰·内夫的低市盈率投资哲学】
约翰·内夫管理温莎基金(Windsor Fund)31年(1964-1995)，年化收益率约13.7%，
跑赢同期市场约3个百分点，其核心理念可概括为：
  1. 低PE买入：以远低于市场平均的市盈率，买入"被市场冷落/忽视"的公司，
     在别人不看好时进场，赚"低估值→价值回归"的钱，而不是追逐热门股；
  2. 优质公司：低PE不等于垃圾股，必须配合"盈利为正且在增长、有分红"等
     质量门槛，避开价值陷阱（本脚本采用"标准版"门槛：PE<行业中位、
     股息率>0、最新净利润同比正增长）；
  3. 总回报比 TRR (Total Return Ratio)：内夫的招牌指标，
     TRR = (股息率 + 盈利增长率) / 市盈率。TRR越高，代表"每一倍PE买到
     的回报越高"。内夫本人要求TRR>=2（严格版），本脚本标准版取TRR>=1.5，
     并按TRR从高到低排名构建组合；
  4. 耐心持有、逆向而为：不追涨杀跌，等待价值回归兑现后止盈离场；
  5. 纪律风控：单只-15%无条件止损；组合分散持有8~12只、单只仓位8%~12%。

【脚本功能】
  screen   —— Neff选股：全A股两阶段筛选，输出候选名单CSV(含建议仓位)；
  backtest —— 历史回测：季度调仓+四类卖出规则，输出净值曲线/交易记录/绩效；
  monitor  —— 持仓监控：对 holdings.csv 中的持仓逐只检查卖出信号与仓位偏离，
              并结合最新选股结果给出补仓候选；
  template —— 生成持仓明细模板 CSV（monitor 的输入文件）；
  all      —— screen + monitor 一次跑完。

【使用方法】(在本脚本所在目录执行)
  python neff_value_strategy.py screen      # 跑一次全A选股
  python neff_value_strategy.py backtest    # 5年历史回测(首次较慢，见配置区说明)
  python neff_value_strategy.py monitor     # 检查持仓并给出操作建议
  python neff_value_strategy.py template    # 生成持仓模板(先填再monitor)
  python neff_value_strategy.py all         # 选股+监控

【依赖环境】
  pip install akshare pandas numpy
  Python >= 3.8；需联网访问东方财富/乐咕乐股等公开行情接口。

【重要声明】
  * 回测存在幸存者偏差（用今天仍在上市的股票回测历史），结果仅供参考，
    不构成任何投资建议；实盘决策请自行判断。
  * AkShare 接口偶有超时或字段变动，脚本已内置重试/跳过/日志容错，
    单只股票数据缺失不影响整体运行，全部异常会记录到 neff_output/neff.log。
================================================================================
"""

import argparse
import logging
import math
import os
import random
import sys
import time
import unicodedata
import urllib.request
from datetime import date, datetime, timedelta
from functools import wraps

import numpy as np
import pandas as pd

try:
    import akshare as ak
except ImportError:
    print("缺少 akshare 库，请先执行: pip install akshare")
    sys.exit(1)

# ==============================================================================
# 第一部分：全局配置参数区（所有可调参数集中在此，改这里即可，无需动函数）
# ==============================================================================

# ---------- 1. Neff 选股参数（"标准版"严格度，可按需收紧/放宽） ----------
NEFF_PARAMS = {
    "TRR_MIN": 1.5,        # 总回报比下限：(股息率% + 净利润同比增速%) / PE-TTM。内夫严格版为2，标准版1.5
    "DIVIDEND_MIN": 0.0,   # 股息率(%)下限：>0 即"必须有分红"，剔除铁公鸡（Neff重视股东回报）
    "GROWTH_MIN": 0.0,     # 最新报告期净利润同比增长(%)下限：>0 保证盈利在改善，避开衰退型低PE
    "STAGE1_N": 120,       # 第一阶段初筛后进入二阶段(逐股核对PE-TTM/股息率)的候选数量
                           # —— 越大越彻底但越慢(每只需调1次接口)，建议 80~200
}

# ---------- 2. 组合构建参数（用户核心要求：8-12只 / 单只8%-12% / 止损-15%） ----------
PORTFOLIO_PARAMS = {
    "MIN_HOLDINGS": 8,      # 组合最少持仓只数
    "MAX_HOLDINGS": 12,     # 组合最多持仓只数（候选不足8只时宁可留现金，不硬凑）
    "MIN_WEIGHT": 0.08,     # 单只仓位下限（用于监控仓位偏离提醒）
    "MAX_WEIGHT": 0.12,     # 单只仓位上限：等权 1/N 超过12%时截断，余额留现金
    "STOP_LOSS": -0.15,     # ★ 硬性止损线：相对买入成本 -15%，无条件执行
    "TOTAL_CAPITAL": 1000000,  # 总资金(元)：用于计算每只股票的建议买入金额，请改成你的实际资金
}

# ---------- 3. 卖出规则参数（止损之外的Neff式卖出纪律） ----------
SELL_RULES = {
    # 规则A 价值回归止盈：赚"低估值→回归"的钱，兑现就走，不贪
    "TAKE_PROFIT_GAIN": 0.50,    # 浮盈达到 +50% → 提示分批止盈
    "PE_REGRESSION_MULT": 1.2,   # 个股市盈率回升到行业中位数×1.2 → 视为价值回归兑现 → 提示止盈
    # 规则B 基本面恶化：低PE的前提被破坏，无论盈亏都应离场
    "NEG_GROWTH_SELL": True,     # 最新净利润同比增长 < 0 且上期也 < 0（连续两期下滑）→ 清仓
    "LOSS_MAKING_SELL": True,    # 净利润转负(TTM亏损) → 无条件清仓（价值陷阱典型特征）
    # 规则C 超时轮换：持有满2年既没止盈也没止损 → 轮出换入新的高TRR候选（Neff平均持股约3年，
    #        A股波动更大，取2年作为轮换上限，可在下方调整）
    "MAX_HOLD_DAYS": 730,
}

# ---------- 4. 股票池参数（全A股） ----------
STOCK_POOL_PARAMS = {
    # 纳入的股票代码前缀：沪市主板600/601/603/605，深市主板000/001、中小板并入主板002/003，
    # 创业板300/301，科创板688/689。北交所(8xx/4xx)流动性差且数据接口不同，默认排除，
    # 如需纳入请自行添加前缀
    "CODE_PREFIXES": ("600", "601", "603", "605", "000", "001", "002", "003",
                      "300", "301", "688", "689"),
    "MIN_FLOAT_MV": 30e8,      # 流通市值下限30亿：Nef买的是"被忽视的优质公司"而非微型壳股，
                               # 过小市值流动性差、财务操纵风险高
    "MIN_LIST_DAYS_PROXY": True,  # 新股过滤：用"60日涨跌幅字段是否缺失"近似判断上市是否满60日
                                  #（刚上市的次新股估值波动大，无历史PE参考，先排除）
}

# ---------- 5. 回测参数 ----------
BACKTEST_PARAMS = {
    "START_DATE": "20210101",   # 回测起始日（约5年半）
    "END_DATE": "20260930",     # 回测结束日
    "SAMPLE_SIZE": 800,         # 回测股票池抽样数量：按流通市值从大到小取前N只。
                                # ★ 全A逐股拉历史数据(5000+只)首次要下载数小时，取800只
                                #   约20-40分钟跑完，兼顾代表性与耗时；想全量改成 99999
    "MIN_FLOAT_MV": 50e8,       # 回测抽样池流通市值下限(50亿)：保证历史流动性与数据质量
    "REBALANCE_MONTHS": (1, 4, 7, 10),  # 季度调仓月：每季首个交易日按最新数据重建组合
    "COMMISSION": 0.00025,      # 佣金 万2.5（双边）
    "MIN_COMMISSION": 5.0,      # 单笔最低佣金5元
    "STAMP_TAX": 0.001,         # 印花税 千1（仅卖出收取，保守取旧税率）
    "USE_CACHE": True,          # ★ 回测数据本地缓存开关：首次下载后存到 neff_output/cache，
                                #   再次运行秒级加载。个股历史数据一天内基本不变，强烈建议开启
    "BENCHMARK": "000300",      # 基准指数：沪深300
    "RISK_FREE": 0.02,          # 夏普比率使用的无风险利率(年化2%)
}

# ---------- 6. 路径与运行参数 ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))       # 脚本所在目录
OUTPUT_DIR = os.path.join(BASE_DIR, "neff_output")           # 所有结果CSV的输出目录
CACHE_DIR = os.path.join(OUTPUT_DIR, "cache")                # 回测数据缓存目录
LOG_FILE = os.path.join(OUTPUT_DIR, "neff.log")              # 运行日志（容错记录都在这里）
HOLDINGS_FILE = os.path.join(OUTPUT_DIR, "holdings.csv")     # 持仓明细文件（monitor输入）
TEMPLATE_FILE = os.path.join(OUTPUT_DIR, "持仓模板.csv")      # 持仓模板示例文件

RETRY_TIMES = 3      # 接口调用失败自动重试次数
RETRY_DELAY = 2      # 首次重试等待秒数（之后指数退避：2s → 4s → 8s）
API_SLEEP = 0.3      # 逐股调用接口的间隔(秒)：礼貌限速，防止被数据源封IP
CACHE_VERSION = "v2" # 缓存文件版本号：字段口径变更时递增，旧缓存自动失效

# 持仓明细文件的列定义（monitor 的输入格式，用户按此填写即可）
HOLDINGS_COLUMNS = ["代码", "名称", "买入日期", "买入价", "持股数", "备注"]


# ==============================================================================
# 第二部分：日志与通用工具函数
# ==============================================================================

def setup_logger() -> logging.Logger:
    """初始化日志：同时输出到控制台(INFO)和日志文件(DEBUG)。
    所有被容错跳过的接口异常都会写入日志文件，便于事后排查数据缺口。"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    logger = logging.getLogger("neff")
    if logger.handlers:                     # 避免重复初始化
        return logger
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    # 控制台：只看关键信息
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    # 文件：记录全部细节，包括每次重试的异常原因
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(sh)
    logger.addHandler(fh)
    return logger


logger = setup_logger()


def with_retry(desc: str, swallow: bool = True, default=None):
    """接口调用重试装饰器（容错核心）。

    参数:
        desc    : 接口用途描述，用于日志定位
        swallow : True=重试耗尽后返回 default 继续跑（单点失败不影响整体）；
                  False=直接抛出异常（用于"数据不存在整个策略就没法跑"的关键接口）
        default : 吞掉异常时的返回值，通常为 None 或空DataFrame
    重试策略: 最多 RETRY_TIMES 次，间隔指数退避 2s/4s/8s，避免瞬时网络抖动。"""
    def deco(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(1, RETRY_TIMES + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:  # noqa: BLE001 —— AkShare内部异常类型多样，统一兜底
                    last_err = e
                    logger.warning("[重试 %d/%d] %s 失败: %s", attempt, RETRY_TIMES, desc, e)
                    time.sleep(RETRY_DELAY * attempt)   # 指数退避
            if swallow:
                logger.error("[放弃] %s: %s （本项数据缺失，已跳过，详见日志）", desc, last_err)
                return default
            raise last_err
        return wrapper
    return deco


def find_col(df: pd.DataFrame, keywords, exclude=()) -> str:
    """在DataFrame里按关键词模糊定位列名。
    AkShare不同版本字段名常有微调（如"市盈率-动态"/"市盈率"），这是应对字段
    变动的防御性措施：按优先级依次匹配，找不到返回空字符串。"""
    for kw in keywords:
        for col in df.columns:
            if kw in col and not any(x in col for x in exclude):
                return col
    return ""


def cjk_width(s: str) -> int:
    """计算字符串的显示宽度（中文/全角算2格，英文数字算1格），
    用于控制台表格对齐，否则中文列会错位。"""
    return sum(2 if unicodedata.east_asian_width(c) in "FW" else 1 for c in str(s))


def pad(s, width: int, align: str = "left") -> str:
    """按显示宽度补空格（等宽对齐），支持左/右对齐。"""
    s = str(s)
    gap = width - cjk_width(s)
    if gap <= 0:
        return s
    return " " * gap + s if align == "right" else s + " " * gap


def print_table(title: str, headers, rows, aligns=None):
    """在控制台打印对齐良好的中文表格。
    aligns: 每列对齐方式列表，"l"=左对齐 / "r"=右对齐，默认全部右对齐（数字习惯）。"""
    print("\n" + "=" * 78)
    print(f"  {title}")
    print("=" * 78)
    if not rows:
        print("  （无记录）")
        return
    aligns = aligns or ["r"] * len(headers)
    # 计算每列宽度 = max(表头宽, 各行宽)
    widths = [max(cjk_width(h), max((cjk_width(r[i]) for r in rows), default=0))
              for i, h in enumerate(headers)]
    print("  " + "  ".join(pad(h, widths[i], "l" if i == 0 else "r")
                           for i, h in enumerate(headers)))
    print("  " + "-" * (sum(widths) + 2 * (len(widths) - 1)))
    for r in rows:
        print("  " + "  ".join(pad(r[i], widths[i], aligns[i]) for i in range(len(r))))
    print(f"  共 {len(rows)} 条记录")


def to_num(series, errors: str = "coerce"):
    """把可能含 '--'、空串的列安全转成数值型；errors='coerce' 时坏值变NaN。"""
    return pd.to_numeric(series, errors=errors)


def latest_report_period(today: date = None) -> str:
    """推算"最新一期已披露完毕"的财报报告期(YYYYMMDD)。
    A股披露截止日：一季报4-30 / 中报8-31 / 三季报10-31 / 年报次年4-30。
    例如今天是2026-10-20 → 三季报尚未披露完 → 返回 20260630（中报）。
    这样取数能避免用到"尚未披露"的数据，保证无未来函数。"""
    today = today or date.today()
    y = today.year
    if today >= date(y, 10, 31):
        return f"{y}0930"
    if today >= date(y, 8, 31):
        return f"{y}0630"
    if today >= date(y, 4, 30):
        return f"{y}0331"
    return f"{y - 1}1231"


def prev_report_period(period: str) -> str:
    """报告期回退一步：20260630 → 20260331 → 20251231 ...（接口无数据时逐期回退）"""
    y = int(period[:4])
    mmdd = period[4:]                 # "20260630"[4:]="0630"，直接用月日字符串做键
    table = {"0930": ("0630", 0), "0630": ("0331", 0),
             "0331": ("1231", -1), "1231": ("0930", -1)}
    mm, dy = table[mmdd]
    return f"{y + dy}{mm}"


def ensure_dirs():
    """确保输出目录/缓存目录存在。"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)


# ==============================================================================
# 第三部分：数据获取层（AkShare封装 + 本地缓存 + 完整容错）
# 所有函数的约定：失败返回 None（不抛异常），由调用方决定跳过或中止。
# ==============================================================================

SPOT_SOURCE = "auto"    # 全A快照数据源路由: "em"=固定东财 / "tx"=固定腾讯 / "auto"=东财优先,
                        # 被拒连(push2风控)或超时自动切换腾讯兜底，恢复后无感切回主源
TX_BATCH_N = 60         # 腾讯行情单批请求的代码数(qt.gtimg.cn 批量报价上限内)


@with_retry("全A股实时快照-东财(stock_zh_a_spot_em)", swallow=False)   # 失败抛出，由路由逻辑决定是否兜底
def _fetch_spot_all_a_em() -> pd.DataFrame:
    """东财主源：一次性拉取全A股实时快照（1次接口调用≈5700只股票）。
    关键字段：代码/名称/最新价/市盈率-动态/总市值/流通市值/60日涨跌幅。
    这是全脚本"性价比"最高的一次调用，选股与监控都依赖它。"""
    df = ak.stock_zh_a_spot_em()
    if df is None or df.empty:
        raise RuntimeError("全A股快照返回为空")
    logger.info("全A快照获取成功(东财): %d 只股票", len(df))
    return df


@with_retry("全A股名单-交易所官方(stock_info_a_code_name)", swallow=False)
def _fetch_all_a_list() -> pd.DataFrame:
    """交易所官方全A代码名单（上交所/深交所/北交所官方站点，非东财），列 code/name。"""
    df = ak.stock_info_a_code_name()
    if df is None or df.empty:
        raise RuntimeError("交易所全A名单返回为空")
    logger.info("交易所全A名单: %d 行", len(df))
    return df


def _tx_prefix(code: str) -> str:
    """腾讯行情的市场前缀：沪市(5/6/9开头)→sh，其余→sz（0/2/3深市+北交所）。"""
    return "sh" if code.startswith(("5", "6", "9")) else "sz"


@with_retry("全A股实时快照-腾讯(qt.gtimg)", swallow=False)
def _fetch_spot_all_a_tx() -> pd.DataFrame:
    """腾讯兜底快照：交易所官方全A名单 + qt.gtimg.cn 批量报价(共93批)，
    列名与东财快照同构：代码/名称/最新价/市盈率-动态/流通市值/总市值。
    字段实证(2026-10-24，工行/茅台/平安对照)：
      idx1名称 idx2代码 idx3现价 idx39动态PE idx44流通市值(亿) idx45总市值(亿)
      idx52静态PE idx53TTM PE idx30行情时间戳。
    口径披露：市值单位亿→元(×1e8)；动态PE为腾讯口径(与东财略有差异，但行业内
    中位PE同源同口径，PE折价的相对排序不受影响)；腾讯无"60日涨跌幅"列，
    次新股过滤改由 filter_recent_listings 在二阶段前用腾讯日K核对。"""
    lst = _fetch_all_a_list()
    names = dict(zip(lst["code"].astype(str).str.zfill(6), lst["name"].astype(str)))
    codes = sorted(names)          # 稳定顺序，日志可复现
    rows, n_batches = [], math.ceil(len(codes) / TX_BATCH_N)
    for b in range(1, n_batches + 1):
        chunk = codes[(b - 1) * TX_BATCH_N: b * TX_BATCH_N]
        url = "https://qt.gtimg.cn/q=" + ",".join(_tx_prefix(c) + c for c in chunk)
        with urllib.request.urlopen(url, timeout=15) as r:
            raw = r.read().decode("gbk", "replace")
        for line in raw.splitlines():
            if '="' not in line:
                continue
            f = line.split('="', 1)[1].rstrip('";').split("~")
            if len(f) < 54 or not f[2]:
                continue
            code = str(f[2]).zfill(6)
            try:
                rows.append({
                    "代码": code, "名称": names.get(code, f[1]),
                    "最新价": float(f[3]) if f[3] else np.nan,
                    "市盈率-动态": float(f[39]) if f[39] else np.nan,
                    "流通市值": float(f[44]) * 1e8 if f[44] else np.nan,
                    "总市值": float(f[45]) * 1e8 if f[45] else np.nan,
                })
            except (ValueError, IndexError):
                continue
        if b % 20 == 0:
            logger.info("  腾讯快照进度: %d/%d 批", b, n_batches)
        time.sleep(API_SLEEP)          # 限速
    df = pd.DataFrame(rows).drop_duplicates("代码")
    if df.empty:
        raise RuntimeError("腾讯快照解析为空")
    logger.info("全A快照获取成功(腾讯兜底): %d 只股票", len(df))
    return df


def fetch_spot_all_a() -> pd.DataFrame:
    """全A实时快照·数据源路由（选股根基，最终失败必须抛出中止）。
    SPOT_SOURCE="auto": 东财优先，异常自动切腾讯兜底（日志声明）；
    "em"/"tx": 固定指定源。"""
    if SPOT_SOURCE == "tx":
        return _fetch_spot_all_a_tx()
    try:
        return _fetch_spot_all_a_em()
    except Exception as e:  # noqa: BLE001
        if SPOT_SOURCE == "em":
            raise
        logger.warning("东财快照不可用(%s) → 自动切换腾讯快照兜底", e)
        return _fetch_spot_all_a_tx()


@with_retry("东财行业板块列表", swallow=False)
def _fetch_industry_boards() -> pd.DataFrame:
    """获取东方财富行业板块名单（约86个行业）。"""
    return ak.stock_board_industry_name_em()


@with_retry("行业成分股", swallow=True, default=None)
def _fetch_industry_cons(board_name: str) -> pd.DataFrame:
    """获取单个行业板块的成分股列表（东财源）。失败返回None由调用方跳过。"""
    return ak.stock_board_industry_cons_em(symbol=board_name)


def fetch_industry_map(use_cache: bool = True) -> pd.DataFrame:
    """构建 股票代码→东财行业 的映射表（约86次接口调用，结果落盘缓存7天）。
    主源: 东财行业板块逐个拉成分股；若接口不可用(超时/被限)，自动降级为
    业绩报表(stock_yjbb_em)里的"所处行业"字段(1次调用，行业为东财口径)。
    用途：计算"行业中位市盈率"，落实Neff"PE低于同行业水平"的选股条件。"""
    cache_file = os.path.join(CACHE_DIR, "industry_map.csv")
    if use_cache and os.path.exists(cache_file):
        age = time.time() - os.path.getmtime(cache_file)
        if age < 7 * 86400:                       # 缓存7天内有效
            df = pd.read_csv(cache_file, dtype={"代码": str})
            if len(df) > 3000:      # 缓存有效性粗校验
                logger.info("行业映射读取缓存: %d 只（%d天前构建）", len(df), int(age // 86400))
                return df
    imap = None
    try:   # ---- 主源：逐行业拉成分股 ----
        boards = _fetch_industry_boards()
        name_col = find_col(boards, ["板块名称"])
        pieces = []
        total = len(boards)
        for i, bname in enumerate(boards[name_col].astype(str), 1):
            cons = _fetch_industry_cons(bname)
            if cons is not None and not cons.empty:
                code_col = find_col(cons, ["代码"])
                name_col2 = find_col(cons, ["名称"])
                sub = cons[[code_col, name_col2]].copy()
                sub.columns = ["代码", "名称"]
                sub["行业"] = bname
                pieces.append(sub)
            if i % 20 == 0:
                logger.info("  行业成分下载进度: %d/%d", i, total)
            time.sleep(API_SLEEP)   # 限速
        if pieces:
            imap = pd.concat(pieces, ignore_index=True).drop_duplicates("代码")
    except Exception as e:  # noqa: BLE001 —— 降级路径，继续用备源
        logger.warning("行业板块主源不可用: %s", e)
    if imap is None or len(imap) < 3000:
        # ---- 备源：业绩报表自带"所处行业"(1次调用覆盖全A) ----
        logger.info("改用业绩报表[所处行业]字段构建行业映射(备源)")
        period = latest_report_period()
        for _ in range(3):
            raw = fetch_earnings_bulk(period)
            if raw is not None and not raw.empty:
                code_col = find_col(raw, ["股票代码"])
                name_col = find_col(raw, ["股票简称"])
                ind_col = find_col(raw, ["所处行业"])
                if code_col and ind_col:
                    imap = pd.DataFrame({
                        "代码": raw[code_col].astype(str).str.zfill(6),
                        "名称": raw[name_col].astype(str) if name_col else "",
                        "行业": raw[ind_col].astype(str),
                    }).drop_duplicates("代码")
                    break
            period = prev_report_period(period)
    if imap is None or imap.empty:
        logger.error("行业映射构建失败(主源+备源均不可用)，选股将无法按行业比较PE")
        return pd.DataFrame(columns=["代码", "名称", "行业"])
    imap.to_csv(cache_file, index=False, encoding="utf-8-sig")
    logger.info("行业映射构建完成: %d 只股票 → 已缓存", len(imap))
    return imap


# ---------- 个股PE-TTM历史：兼容新旧版akshare的双源设计 ----------
# 老版akshare(<1.18): stock_a_indicator_lg 乐咕日频PE/股息率
# 新版akshare(>=1.18): 该接口被移除，改用百度股市通 stock_zh_valuation_baidu

def _baidu_period(start: str, end: str) -> str:
    """选择百度估值接口的时间段参数。
    ★ 关键：百度的"近N年"窗口一律锚定"今天"往回看，与请求的[start,end]无关。
    因此必须按"今天距start的跨度"选窗（而不是按end-start），否则回测历史区间的
    前半段会被截断（实测踩坑：2022~2024回测错选"近三年"导致2022年PE缺失）。
    选出的窗口需完整覆盖 start；随后由 fetch_pe_ttm_history 截取[start,end]。"""
    lookback = (pd.Timestamp.today() - pd.Timestamp(start)).days
    if lookback <= 366:
        return "近一年"
    if lookback <= 3 * 366:
        return "近三年"
    if lookback <= 5 * 366:
        return "近五年"
    return "全部"


@with_retry("个股PE-TTM历史(乐咕,老版akshare)", swallow=True, default=None)
def _fetch_pe_ttm_lg(code: str) -> pd.DataFrame:
    """老版akshare的乐咕接口：返回全历史日频 pe/pe_ttm/pb/dv_ratio 等。"""
    df = ak.stock_a_indicator_lg(symbol=code)
    if df is None or df.empty:
        raise RuntimeError(f"{code} 乐咕估值为空")
    out = pd.DataFrame({
        "日期": pd.to_datetime(df["trade_date"]),
        "pe_ttm": to_num(df["pe_ttm"]),
    })
    time.sleep(API_SLEEP)
    return out


@with_retry("个股PE-TTM历史(百度股市通)", swallow=True, default=None)
def _fetch_pe_ttm_baidu(code: str, start: str, end: str) -> pd.DataFrame:
    """新版akshare的百度估值接口：市盈率(TTM)历史，date/value两列。"""
    df = ak.stock_zh_valuation_baidu(symbol=code, indicator="市盈率(TTM)",
                                     period=_baidu_period(start, end))
    if df is None or df.empty:
        raise RuntimeError(f"{code} 百度估值为空")
    out = pd.DataFrame({
        "日期": pd.to_datetime(df["date"]),
        "pe_ttm": to_num(df["value"]),
    })
    time.sleep(API_SLEEP)
    return out


def fetch_pe_ttm_history(code: str, start: str, end: str) -> pd.DataFrame:
    """PE-TTM历史(双源自动切换)：返回[日期, pe_ttm]，失败返回None。"""
    df = None
    if hasattr(ak, "stock_a_indicator_lg"):       # 老版akshare优先乐咕(粒度更细)
        df = _fetch_pe_ttm_lg(code)
    if df is None:
        df = _fetch_pe_ttm_baidu(code, start, end)  # 新版akshare用百度
    if df is None or df.empty:
        return None
    df = df.dropna().sort_values("日期")
    df = df[(df["日期"] >= pd.Timestamp(start)) & (df["日期"] <= pd.Timestamp(end))]
    return df[~df["日期"].duplicated(keep="last")].reset_index(drop=True)


@with_retry("个股分红历史(stock_fhps_detail_em)", swallow=True, default=None)
def fetch_dividend_events(code: str) -> pd.DataFrame:
    """个股分红实施记录：返回[除权除息日, 每股派息(元)]，仅保留已实施且派息>0的记录。
    用于: ①构造TTM股息率序列(回测) ②实盘选股时核对"必须分红"门槛。
    统一用事件流而非静态股息率字段，保证回测与实盘口径一致且无未来函数。"""
    df = ak.stock_fhps_detail_em(symbol=code)
    if df is None or df.empty:
        raise RuntimeError(f"{code} 无分红记录")
    dps_col = find_col(df, ["现金分红比例"], exclude=["描述", "股息率"])  # 单位：每10股派息(元)
    ex_col = find_col(df, ["除权除息日"])
    if not dps_col or not ex_col:
        logger.warning("%s 分红字段异常: %s", code, list(df.columns))
        return None
    ev = pd.DataFrame({
        "除权除息日": pd.to_datetime(df[ex_col], errors="coerce"),
        # 东财该字段为"每10股派息(元)"（如10派10.60元→字段值10.60），除以10换算为每股
        "每股派息": to_num(df[dps_col]) / 10.0,
    }).dropna()
    ev = ev[ev["每股派息"] > 0]
    time.sleep(API_SLEEP)
    return ev if not ev.empty else None


def build_dividend_yield_series(events: pd.DataFrame, close_raw: pd.Series,
                                cal_index: pd.DatetimeIndex) -> pd.Series:
    """把分红事件流展开成"TTM股息率(%)"日频序列：
    TTM股息率 = 过去244个交易日每股派息合计 / 不复权价 × 100。
    仅用已发生的除权除息事件，无未来函数；无分红记录的股票返回全0序列。"""
    zero = pd.Series(0.0, index=cal_index)
    if events is None or events.empty:
        return zero
    ev = events.groupby("除权除息日")["每股派息"].sum().sort_index()
    ev_daily = ev.reindex(cal_index).fillna(0.0)
    ttm_dps = ev_daily.rolling(244, min_periods=1).sum()      # 244交易日≈TTM
    dv = ttm_dps / close_raw.reindex(cal_index).ffill() * 100
    return dv.where(close_raw.reindex(cal_index).ffill() > 0, 0.0).fillna(0.0)


def _cache_path(kind: str, code: str) -> str:
    """生成个股数据缓存文件路径（带版本号，口径升级后旧缓存自动失效）。
    kind: pe / close_raw / close_qfq / fenghong / industry 等"""
    return os.path.join(CACHE_DIR, f"{kind}_{CACHE_VERSION}_{code}.csv")


def _read_cache(path: str) -> pd.DataFrame:
    """读缓存文件；不存在返回None。"""
    if os.path.exists(path):
        try:
            return pd.read_csv(path, dtype={"代码": str})
        except Exception:    # 缓存损坏则当作无缓存
            return None
    return None


def _tx_symbol(code: str) -> str:
    """6位代码 → 腾讯接口的带市场前缀代码：6/9开头=沪市sh，其余=深市sz。
    (北交所8/4开头已排除在股票池外，无需处理)"""
    return ("sh" if code.startswith(("6", "9")) else "sz") + code


@with_retry("个股日线-东财(stock_zh_a_hist)", swallow=True, default=None)
def _fetch_hist_em(code: str, start: str, end: str, adjust: str) -> pd.DataFrame:
    """东财日行情主源，返回统一列[日期, 收盘]。adjust: ""=不复权, "qfq"=前复权。"""
    df = ak.stock_zh_a_hist(symbol=code, period="daily",
                            start_date=start, end_date=end, adjust=adjust)
    if df is None or df.empty:
        raise RuntimeError(f"{code} 东财行情为空")
    out = pd.DataFrame({"日期": pd.to_datetime(df["日期"]),
                        "收盘": to_num(df["收盘"])})
    time.sleep(API_SLEEP)
    return out


@with_retry("个股日线-腾讯(stock_zh_a_hist_tx备源)", swallow=True, default=None)
def _fetch_hist_tx(code: str, start: str, end: str, adjust: str) -> pd.DataFrame:
    """腾讯日行情备源(东财不可用时自动切换)：列date/close归一化为[日期, 收盘]。
    同样支持 adjust qfq/"" ，保证备源下复权口径一致。"""
    df = ak.stock_zh_a_hist_tx(symbol=_tx_symbol(code), start_date=start,
                               end_date=end, adjust=adjust)
    if df is None or df.empty:
        raise RuntimeError(f"{code} 腾讯行情为空")
    out = pd.DataFrame({"日期": pd.to_datetime(df["date"]),
                        "收盘": to_num(df["close"])})
    time.sleep(API_SLEEP)
    return out


def fetch_price_history(code: str, start: str, end: str, adjust: str = ""):
    """个股日收盘价(双源自动切换)：东财 → 腾讯。返回[日期, 收盘]，失败返回None。"""
    df = _fetch_hist_em(code, start, end, adjust)
    if df is None:
        logger.info("%s 东财行情不可用，切换腾讯备源", code)
        df = _fetch_hist_tx(code, start, end, adjust)
    if df is None or df.empty:
        return None
    return df.dropna().sort_values("日期").reset_index(drop=True)


@with_retry("业绩报表(stock_yjbb_em)", swallow=True, default=None)
def fetch_earnings_bulk(period: str) -> pd.DataFrame:
    """一次性拉取全A股某报告期的业绩报表（东财源，1次调用≈5000只）。
    关键字段：净利润-同比增长(%)。比逐股查财务指标快三个数量级，
    用于选股阶段的"最新净利润正增长"过滤与监控阶段的基本面检查。
    period 形如 "20260630"。"""
    df = ak.stock_yjbb_em(date=period)
    if df is None or df.empty:
        raise RuntimeError(f"{period} 业绩报表为空")
    return df


def fetch_earnings_with_fallback() -> pd.DataFrame:
    """取"最新已披露报告期"的全A业绩表；若当期为空则自动回退上一期（最多回退4期）。
    返回统一列：代码 / 净利润同比 / 报告期。全部失败返回空DataFrame（容错）。"""
    period = latest_report_period()
    for _ in range(4):
        df = fetch_earnings_bulk(period)
        if df is not None and not df.empty:
            code_col = find_col(df, ["股票代码"])
            # 增长率列必须精确匹配"净利润-同比增长"：宽松匹配会撞上"净利润-净利润"
            # (净利润额列，单位元)，导致增长率出现天文数字（实测踩坑）
            growth_col = find_col(df, ["净利润-同比增长"]) or \
                find_col(df, ["净利润同比增长"]) or \
                find_col(df, ["同比增长"], exclude=["营业收入", "环比"])
            if not code_col or not growth_col:
                logger.error("业绩报表字段缺失: 现有列=%s", list(df.columns))
                period = prev_report_period(period)
                continue
            out = pd.DataFrame({
                "代码": df[code_col].astype(str).str.zfill(6),
                "净利润同比": to_num(df[growth_col]),
                "报告期": period,
            }).dropna(subset=["净利润同比"])
            logger.info("业绩报表(%s)获取成功: %d 条", period, len(out))
            return out
        logger.warning("报告期 %s 无数据，回退上一期", period)
        period = prev_report_period(period)
    logger.error("连续4个报告期均无业绩数据，净利润增速过滤将失效")
    return pd.DataFrame(columns=["代码", "净利润同比", "报告期"])


@with_retry("指数日线-东财(index_zh_a_hist)", swallow=True, default=None)
def _fetch_index_em(symbol: str, start: str, end: str) -> pd.DataFrame:
    """东财指数日线主源，返回[日期, 收盘]。"""
    df = ak.index_zh_a_hist(symbol=symbol, period="daily",
                            start_date=start, end_date=end)
    if df is None or df.empty:
        raise RuntimeError(f"指数{symbol}东财行情为空")
    return pd.DataFrame({"日期": pd.to_datetime(df["日期"]),
                         "收盘": to_num(df["收盘"])})


@with_retry("指数日线-腾讯(stock_zh_index_daily_tx备源)", swallow=True, default=None)
def _fetch_index_tx(symbol: str, start: str, end: str) -> pd.DataFrame:
    """腾讯指数日线备源：399开头=深市指数，其余按沪市处理。"""
    tx_sym = ("sz" if symbol.startswith("399") else "sh") + symbol
    df = ak.stock_zh_index_daily_tx(symbol=tx_sym, start_date=start, end_date=end)
    if df is None or df.empty:
        raise RuntimeError(f"指数{symbol}腾讯行情为空")
    return pd.DataFrame({"日期": pd.to_datetime(df["date"]),
                         "收盘": to_num(df["close"])})


def fetch_index_history(symbol: str, start: str, end: str) -> pd.DataFrame:
    """指数日收盘(双源自动切换)：东财 → 腾讯，返回[日期, 收盘]。
    用作回测基准与交易日历；两源都失败才抛异常(基准缺失回测无意义)。"""
    df = _fetch_index_em(symbol, start, end)
    if df is None:
        logger.info("指数东财源不可用，切换腾讯备源")
        df = _fetch_index_tx(symbol, start, end)
    if df is None or df.empty:
        raise RuntimeError(f"指数{symbol}两个数据源均不可用，请检查网络")
    return df.dropna().sort_values("日期").reset_index(drop=True)


# ==============================================================================
# 第四部分：Neff 选股模块（两阶段筛选，快慢结合）
# 第一阶段用"全A快照1次调用"完成粗筛（快）；第二阶段仅对入围股逐股调接口
# 核对 PE-TTM/股息率（准），兼顾速度与准确性。
# ==============================================================================

def prepare_stock_universe(spot: pd.DataFrame) -> pd.DataFrame:
    """Step0 清洗股票池（落实Neff"优质公司"的边界条件）：
      1) 只留A股主板/创业板/科创板（默认排除北交所，见配置区）；
      2) 剔除 ST / *ST / 退市股 —— 低PE里的ST多数是基本面已坏的价值陷阱；
      3) 剔除停牌（最新价为空）；
      4) 剔除上市不足60日的次新股（用"60日涨跌幅缺失"近似判断，次新股无估值锚）；
      5) 剔除流通市值 < 30亿的微型股（流动性差、易被操纵）；
      6) 剔除 PE 为负或缺失（亏损股的PE无意义，Neff只买盈利公司）。"""
    p = STOCK_POOL_PARAMS
    col_code = find_col(spot, ["代码"])
    col_name = find_col(spot, ["名称"])
    col_price = find_col(spot, ["最新价"])
    col_pe = find_col(spot, ["市盈率-动态", "市盈率"])
    col_fmv = find_col(spot, ["流通市值"])
    col_tmv = find_col(spot, ["总市值"])
    col_d60 = find_col(spot, ["60日涨跌幅"])
    for c in (col_code, col_name, col_price, col_pe, col_fmv):
        if not c:
            raise RuntimeError(f"全A快照缺少关键列，现有列: {list(spot.columns)}")

    df = pd.DataFrame({
        "代码": spot[col_code].astype(str).str.zfill(6),
        "名称": spot[col_name].astype(str),
        "现价": to_num(spot[col_price]),
        "PE动态": to_num(spot[col_pe]),
        "流通市值": to_num(spot[col_fmv]),
        "总市值": to_num(spot[col_tmv]) if col_tmv else np.nan,
    })
    if col_d60:
        df["60日涨跌幅"] = to_num(spot[col_d60])

    n0 = len(df)
    df = df[df["代码"].str.startswith(p["CODE_PREFIXES"])].copy()      # 1)
    df = df[~df["名称"].str.contains("ST|退", na=False)].copy()          # 2)
    df = df.dropna(subset=["现价"]).copy()                              # 3)
    if p["MIN_LIST_DAYS_PROXY"] and "60日涨跌幅" in df.columns:          # 4)
        df = df[df["60日涨跌幅"].notna()].copy()
    df = df[df["流通市值"] >= p["MIN_FLOAT_MV"]].copy()                  # 5)
    df = df[df["PE动态"] > 0].copy()                                     # 6)
    logger.info("股票池清洗: %d → %d 只（剔除ST/次新/微盘/亏损）", n0, len(df))
    return df.reset_index(drop=True)


def attach_industry_pe(df: pd.DataFrame) -> pd.DataFrame:
    """Step1 落实Neff"PE低于同行业"：
    按东财行业分组计算"行业中位PE"（用中位数而非算术均值，抗极端值干扰），
    再计算每只股票相对行业的PE折价率。行业归属缺失的股票剔除并记日志。"""
    imap = fetch_industry_map(use_cache=True)
    df = df.merge(imap[["代码", "行业"]], on="代码", how="left")
    n_missing = df["行业"].isna().sum()
    if n_missing:
        logger.warning("%d 只股票无行业归属，已剔除", n_missing)
        df = df[df["行业"].notna()].copy()
    # 行业内正PE成员的中位数作为行业估值锚
    df["行业中位PE"] = df.groupby("行业")["PE动态"].transform(lambda s: s[s > 0].median())
    df["PE折价%"] = (1 - df["PE动态"] / df["行业中位PE"]) * 100
    return df.reset_index(drop=True)


@with_retry("次新股核对-腾讯K线条数(stock_zh_a_hist_tx)", swallow=True, default=None)
def _fetch_tx_d60_bars(code: str):
    """近130自然日的日K条数（腾讯端点，已在用的备源行情接口）。
    沪深A股约每130个自然日有88~90个交易日：条数<60 ⇔ 上市不足60个交易日，
    与东财快照"60日涨跌幅缺失"的旧近似完全同义。返回 None 表示核对失败。"""
    start = (date.today() - timedelta(days=130)).strftime("%Y%m%d")
    df = ak.stock_zh_a_hist_tx(symbol=_tx_symbol(code), start_date=start,
                               end_date=date.today().strftime("%Y%m%d"), adjust="")
    if df is None or df.empty:
        raise RuntimeError(f"{code} 腾讯日K为空")
    return len(df)


def filter_recent_listings(cand: pd.DataFrame) -> pd.DataFrame:
    """剔除"上市不足60个交易日"的次新股（腾讯快照路径专用，iterable级补丁）。
    东财快照自带"60日涨跌幅"列（缺失⇔次新），prepare_stock_universe 已处理，
    列存在时直接返回零开销；腾讯路径无该列，对入围股(通常是STAGE1_N只量级)
    逐只调腾讯日K核对，核对失败的不误杀、放行并记日志。"""
    if "60日涨跌幅" in cand.columns:
        return cand
    keep, n_new, n_fail = [], 0, 0
    for i, code in enumerate(cand["代码"].astype(str), 1):
        bars = _fetch_tx_d60_bars(code)
        if bars is None:
            n_fail += 1
            keep.append(True)          # 失败不误杀
        elif bars < 60:
            n_new += 1
            keep.append(False)
        else:
            keep.append(True)
        if i % 30 == 0:
            logger.info("  次新股核对进度: %d/%d（已剔除 %d）", i, len(cand), n_new)
    out = cand[pd.Series(keep, index=cand.index)].copy()
    logger.info("次新股过滤: 核对 %d 只 → 剔除 %d 只次新、%d 只核对失败放行，剩 %d 只",
                len(cand), n_new, n_fail, len(out))
    return out


def stage2_enrich(candidates: pd.DataFrame) -> pd.DataFrame:
    """Step2 对初筛入围股逐股核对（每只2次接口，约1秒/只）：
      * PE-TTM：乐咕(老版akshare)/百度股市通(新版)，比东财"动态PE"更稳健
        （动态PE用单季年化，季节波动大），Neff口径按TTM计算；
      * 股息率TTM：由分红实施事件流计算（近365自然日每股派息合计/现价），
        落实"必须分红"的质量门槛（Neff重视股东现金回报）。
    PE取不到的股票退回用快照动态PE近似（在run_screening中fillnna处理）；
    接口失败的股票跳过并记日志（完整容错，不因个别失败中断）。"""
    today = pd.Timestamp(date.today())
    year_ago = today - pd.Timedelta(days=365)
    price_map = dict(zip(candidates["代码"], candidates["现价"]))
    codes = candidates["代码"].tolist()
    rows, fail = [], 0
    total = len(codes)
    logger.info("二阶段核查开始: 共 %d 只（每只约1秒，预计 %.1f 分钟）", total, total / 60)
    for i, code in enumerate(codes, 1):
        try:
            pe = np.nan
            pe_hist = fetch_pe_ttm_history(
                code, (today - pd.Timedelta(days=400)).strftime("%Y%m%d"),
                today.strftime("%Y%m%d"))
            if pe_hist is not None and not pe_hist.empty:
                pe = float(pe_hist["pe_ttm"].iloc[-1])      # 最新一个交易日PE-TTM
            dv = 0.0
            ev = fetch_dividend_events(code)
            if ev is not None and not ev.empty:
                ttm_dps = ev[ev["除权除息日"] >= year_ago]["每股派息"].sum()
                px = price_map.get(code, np.nan)
                if pd.notna(px) and px > 0:
                    dv = float(ttm_dps / px * 100)          # TTM股息率(%)
            rows.append({"代码": code, "PE_TTM": pe, "股息率": dv})
        except Exception as e:  # noqa: BLE001 —— 单股异常不拖垮整个选股
            logger.warning("%s 二阶段核查异常: %s", code, e)
        if i % 20 == 0 or i == total:
            logger.info("  二阶段进度: %d/%d（失败%d）", i, total, fail)
    enriched = pd.DataFrame(rows)
    return candidates.merge(enriched, on="代码", how="left") if enriched.size else \
        candidates.assign(PE_TTM=np.nan, 股息率=np.nan)


def run_screening(top_n: int = None, quiet: bool = False) -> pd.DataFrame:
    """Neff选股主流程：返回最终候选名单DataFrame并落盘CSV。
    top_n 默认取组合上限12只（候选池略多于实盘需要，便于替换轮换）。"""
    ensure_dirs()
    top_n = top_n or PORTFOLIO_PARAMS["MAX_HOLDINGS"]
    print("\n" + "#" * 78)
    print(f"#  约翰·内夫低PE价值选股（标准版：PE<行业中位 + 股息率>"
          f"{NEFF_PARAMS['DIVIDEND_MIN']:g} + 净利同比>{NEFF_PARAMS['GROWTH_MIN']:g} + TRR>={NEFF_PARAMS['TRR_MIN']:g}）")
    print("#" * 78)

    # ---- Step0/1 清洗与行业估值锚 ----
    spot = fetch_spot_all_a()                       # 关键接口，失败会中止（无未来函数风险）
    df = prepare_stock_universe(spot)
    df = attach_industry_pe(df)

    # ---- 初筛：PE低于行业中位（Neff"被市场忽视"的量化表达），按折价从深到浅取前N只 ----
    stage1 = df[df["PE动态"] < df["行业中位PE"]].copy()
    stage1 = stage1.sort_values("PE折价%", ascending=False).head(NEFF_PARAMS["STAGE1_N"])
    stage1 = filter_recent_listings(stage1)     # 腾讯快照路径补刀次新过滤（东财路径零开销）
    logger.info("初筛(PE<行业中位): %d 只 → 取折价最深的 %d 只进入二阶段",
                len(df[df["PE动态"] < df["行业中位PE"]]), len(stage1))

    # ---- 二阶段：核对PE-TTM与股息率 ----
    cand = stage2_enrich(stage1)
    n_no_pe = cand["PE_TTM"].isna().sum()
    if n_no_pe:
        logger.warning("%d 只股票PE-TTM缺失，退回用快照动态PE近似(口径差异约±10%%)", n_no_pe)
        cand["PE_TTM"] = cand["PE_TTM"].fillna(cand["PE动态"])
    cand = cand[cand["PE_TTM"].notna() & (cand["PE_TTM"] > 0)].copy()
    cand = cand[cand["股息率"] > NEFF_PARAMS["DIVIDEND_MIN"]].copy()      # 必须有分红
    logger.info("质量门槛(股息率>0): 剩余 %d 只", len(cand))

    # ---- 净利润同比>0（用全A业绩报表批量核对，1次接口） ----
    earn = fetch_earnings_with_fallback()
    if not earn.empty:
        cand = cand.merge(earn[["代码", "净利润同比"]], on="代码", how="left")
        before = len(cand)
        cand = cand[cand["净利润同比"] > NEFF_PARAMS["GROWTH_MIN"]].copy()
        logger.info("盈利门槛(最新净利同比>0): %d → %d 只", before, len(cand))
    else:
        cand["净利润同比"] = np.nan
        logger.warning("业绩数据缺失，跳过净利润过滤（TRR中增速项按0处理，结果偏保守）")
    cand["净利润同比"] = cand["净利润同比"].fillna(0.0)

    # ---- Step3 计算 TRR 总回报比并排名（Neff招牌指标，标准版>=1.5） ----
    cand["TRR"] = (cand["股息率"] + cand["净利润同比"]) / cand["PE_TTM"]
    # 口径说明："PE低于行业"约束在初筛已用动态PE口径落实（与行业中位同源同口径）；
    # 此处不再用PE_TTM重复约束——TTM与动态口径存在系统性差异(实测招行PE_TTM 6.9 vs
    # 动态5.6，若混用比较会误杀)，PE_TTM仅用于TRR计算与展示
    cand = cand[cand["TRR"] >= NEFF_PARAMS["TRR_MIN"]].copy()
    cand = cand.sort_values(["TRR", "PE折价%"], ascending=False).head(top_n)

    if cand.empty:
        print("\n⚠ 当前市场无满足Neff标准版全部条件的股票——低PE机会枯竭时，"
              "内夫的做法是保留现金耐心等待。可放宽 NEFF_PARAMS 后重试。")
        return pd.DataFrame()

    # ---- 组合构建建议：8~12只 / 单只8%~12% ----
    p = PORTFOLIO_PARAMS
    n_target = min(max(len(cand), p["MIN_HOLDINGS"]), p["MAX_HOLDINGS"])
    weight = min(1.0 / n_target, p["MAX_WEIGHT"])   # 等权但不超过12%，余额留现金
    cand = cand.copy()
    cand["建议权重%"] = round(weight * 100, 2)
    cand["建议金额(元)"] = round(p["TOTAL_CAPITAL"] * weight, 0)

    out_cols = ["代码", "名称", "行业", "现价", "PE动态", "PE_TTM", "行业中位PE",
                "PE折价%", "股息率", "净利润同比", "TRR", "总市值",
                "建议权重%", "建议金额(元)"]
    out = cand[out_cols].reset_index(drop=True)
    out["总市值"] = (out["总市值"] / 1e8).round(1)          # 元 → 亿元
    out_file = os.path.join(OUTPUT_DIR, f"筛选结果_{date.today():%Y%m%d}.csv")
    out.to_csv(out_file, index=False, encoding="utf-8-sig")  # utf-8-sig: Excel打开不乱码

    # ---- 控制台报表 ----
    rows = [[r["代码"], r["名称"], r["行业"], f"{r['现价']:.2f}", f"{r['PE_TTM']:.1f}",
             f"{r['行业中位PE']:.1f}", f"{r['PE折价%']:.0f}%", f"{r['股息率']:.2f}%",
             f"{r['净利润同比']:.1f}%", f"{r['TRR']:.2f}", f"{r['总市值']:.0f}亿",
             f"{r['建议权重%']:.1f}%", f"{r['建议金额(元)']:,.0f}"] for _, r in out.iterrows()]
    if not quiet:
        print_table(f"Neff候选名单 TOP{len(out)}（总资金 {p['TOTAL_CAPITAL']:,} 元）",
                    ["代码", "名称", "行业", "现价", "PE-TTM", "行业中位", "折价",
                     "股息率", "净利同比", "TRR", "市值", "建议权重", "建议金额"],
                    rows)
        print(f"\n✔ 完整结果已保存: {out_file}")
        print("  提示: TRR=(股息率+净利增速)/PE，是内夫衡量『每一倍PE买到多少回报』的招牌指标；")
        print("  建议按候选顺序分2-3周建仓，避免一次性买在阶段高点。")
    return out


# ==============================================================================
# 第五部分：历史回测模块（季度调仓 + 四类卖出规则 + 绩效统计）
#
# 回测设计要点（务求"无未来函数"）：
#   * 各交易日的 PE-TTM / 股息率 取自乐咕历史估值序列（当时点的真实数据）；
#   * 盈利增速用 EPS_TTM = 不复权收盘价 / PE_TTM 反推，再算同比 —— 全部由
#     当日可见数据构成，杜绝"用未来财报选过去股票"的偏差；
#   * 调仓时点选在季报/年报披露截止日之后的季度首日，保证基本面信息已公开。
#
# 已知局限（务必阅读）：
#   * 幸存者偏差：股票池由"今天仍在上市"的股票构成，退市股未包含，
#     回测收益会略偏乐观，请仅作策略逻辑验证之用；
#   * 行业映射采用当前归属近似回测全程（个别调仓的行业归属可能已变）。
# ==============================================================================

def _bt_universe(spot: pd.DataFrame) -> pd.DataFrame:
    """回测股票池：在选股池条件基础上取流通市值最大的前 SAMPLE_SIZE 只。
    选大市值的理由：历史数据更完整、退市概率更低、成交假设更接近现实；
    SAMPLE_SIZE 默认800只（首次下载约20-40分钟，之后走缓存秒级加载）。"""
    df = prepare_stock_universe(spot)
    p = BACKTEST_PARAMS
    df = df[df["流通市值"] >= p["MIN_FLOAT_MV"]].copy()
    df = df.sort_values("流通市值", ascending=False).head(p["SAMPLE_SIZE"])
    logger.info("回测股票池: %d 只（流通市值>=50亿的前%d名）", len(df), p["SAMPLE_SIZE"])
    return df.reset_index(drop=True)


def _load_backtest_data(code: str, start: str, end: str, use_cache: bool):
    """加载单只股票回测四件套（PE-TTM历史/不复权收盘/前复权收盘/分红事件），
    每项独立缓存(首次下载后二次运行秒级加载)。
    返回 dict{pe, raw, qfq, events}（各项可为None），raw缺失才视为整体失败。"""
    pe_path = _cache_path("pe", f"{code}_{start}_{end}")
    raw_path = _cache_path("close_raw", f"{code}_{start}_{end}")
    qfq_path = _cache_path("close_qfq", f"{code}_{start}_{end}")
    ev_path = _cache_path("fenghong", code)
    # PE历史比回测起点多取420自然日：eps_yoy需要一年前的EPS做基数（热身期），
    # 否则回测头一年会因yoy缺失而无法选股
    pe_start = (pd.Timestamp(start) - pd.Timedelta(days=420)).strftime("%Y%m%d")

    def _get(path, fetcher):
        """缓存优先的单项加载器：无缓存则调接口并落盘。"""
        df = _read_cache(path) if use_cache else None
        if df is not None:
            return df
        df = fetcher()                    # 内部已含重试，失败返回None
        if df is not None and use_cache:
            df.to_csv(path, index=False, encoding="utf-8-sig")
        return df

    pe = _get(pe_path, lambda: fetch_pe_ttm_history(code, pe_start, end))
    raw = _get(raw_path, lambda: fetch_price_history(code, start, end, ""))
    qfq = _get(qfq_path, lambda: fetch_price_history(code, start, end, "qfq"))
    # 分红事件：无分红股票返回空表并缓存，避免每次运行都重复请求
    ev = _get(ev_path, lambda: fetch_dividend_events(code))
    if ev is None:
        ev = pd.DataFrame(columns=["除权除息日", "每股派息"])
        if use_cache and not os.path.exists(ev_path):
            ev.to_csv(ev_path, index=False, encoding="utf-8-sig")
    if raw is None or raw.empty:          # 价格是底线数据，缺失则该股退出回测池
        return None
    # 缓存读回时日期是字符串 → 统一转datetime（网络返回本就是datetime，幂等）
    for d in (pe, raw, qfq):
        if d is not None:
            d["日期"] = pd.to_datetime(d["日期"])
    ev["除权除息日"] = pd.to_datetime(ev["除权除息日"])
    return {"pe": pe, "raw": raw, "qfq": qfq, "events": ev}


def prepare_backtest_data(universe: pd.DataFrame, industry_map: pd.DataFrame):
    """批量下载/加载全部股票池数据 → 对齐到统一交易日历 → 派生策略指标。
    返回 (data_dict, industry_of, calendar)：
      data_dict[code] = DataFrame[close_raw, close_qfq, pe_ttm, dv_ratio, eps_ttm, eps_yoy]
      calendar        = DatetimeIndex 交易日历（样本内出现过的交易日并集）
    派生逻辑：
      * eps_ttm = 不复权价 / PE-TTM（时点数据反推，无未来函数）
      * eps_yoy = eps_ttm / 一年前eps_ttm - 1（shift244交易日，前1年为热身期）
      * dv_ratio = 分红事件流构造的TTM股息率(%)（见build_dividend_yield_series）
      * 前复权价缺失时(双源都挂)：用不复权价+分红事件构造全收益价格替代"""
    p = BACKTEST_PARAMS
    ensure_dirs()
    bundles, failed = {}, []
    codes = universe["代码"].tolist()
    t0 = time.time()
    for i, code in enumerate(codes, 1):
        bundle = _load_backtest_data(code, p["START_DATE"], p["END_DATE"], p["USE_CACHE"])
        if bundle is None:
            failed.append(code)
            continue
        bundles[code] = bundle
        if i % 25 == 0 or i == len(codes):
            speed = (time.time() - t0) / max(i, 1)
            logger.info("  回测数据进度: %d/%d（失败%d，预计剩余 %.0f 分钟）",
                        i, len(codes), len(failed), speed * (len(codes) - i) / 60)

    # 统一交易日历：样本内所有股票出现过的日期并集
    cal = sorted(set().union(*[set(b["raw"]["日期"]) for b in bundles.values()]))
    cal = pd.DatetimeIndex(cal)
    logger.info("回测区间交易日: %d 天；数据可用股票: %d/%d 只",
                len(cal), len(bundles), len(codes))

    data = {}
    for code, b in bundles.items():
        # 在"个股自身完整索引(价格∪PE)"上派生指标，再切回回测日历：
        # 若直接reindex到回测日历，PE热身期(回测起点前420天)会被丢弃，
        # 导致eps_yoy在回测头一年全是NaN、迟迟无法建仓（实测踩坑）
        raw_full = b["raw"].set_index("日期")["收盘"]
        pe_full = (b["pe"].set_index("日期")["pe_ttm"]
                   if b["pe"] is not None else pd.Series(dtype=float))
        idx_full = raw_full.index.union(pe_full.index).sort_values()
        raw_i = raw_full.reindex(idx_full).ffill()
        pe_i = pe_full.reindex(idx_full).ffill()
        pe_valid = pe_i.where(pe_i > 0)                   # 亏损期PE无意义→NaN
        eps_ttm = raw_i / pe_valid                        # 反推每股收益TTM(元)
        eps_yoy = eps_ttm / eps_ttm.shift(244) - 1.0      # ≈净利润同比(时点口径)
        eps_yoy = eps_yoy.replace([np.inf, -np.inf], np.nan)   # 防除零产生inf
        if b["qfq"] is not None:
            qfq_i = b["qfq"].set_index("日期")["收盘"].reindex(idx_full).ffill()
        else:
            # 双源前复权价都不可用：用不复权价+分红事件构造全收益价(cumprod)，
            # 除息日再投资假设与qfq口径等价；起点归一化不影响收益百分比
            ev_daily = (b["events"].groupby("除权除息日")["每股派息"].sum()
                        .reindex(idx_full).fillna(0.0))
            ret = (raw_i + ev_daily) / raw_i.shift(1) - 1.0
            ret = ret.replace([np.inf, -np.inf], np.nan).fillna(0.0)
            qfq_i = (1.0 + ret).cumprod()
            qfq_i.iloc[0] = 1.0
        dv_i = build_dividend_yield_series(b["events"], raw_i, idx_full)
        df_full = pd.DataFrame({"close_raw": raw_i, "close_qfq": qfq_i,
                                "pe_ttm": pe_i, "dv_ratio": dv_i,
                                "eps_ttm": eps_ttm, "eps_yoy": eps_yoy})
        data[code] = df_full.reindex(cal)                 # 切回统一回测日历

    industry_of = {}
    for _, r in industry_map.iterrows():     # 行业归属（当前口径，近似处理）
        industry_of[r["代码"]] = r["行业"]
    return data, industry_of, cal


def _industry_medians(pe_map: dict, industry_of: dict, min_members: int = 5):
    """计算某一调仓日的行业中位PE-TTM（成员数<5的行业回退用全市场中位数）。
    pe_map: {code: 当日PE_TTM}（仅>0的成员）。"""
    valid = {c: pe for c, pe in pe_map.items() if pe and pe > 0}
    if not valid:
        return {}
    market_med = float(np.median(list(valid.values())))
    by_ind = {}
    for c, pe in valid.items():
        by_ind.setdefault(industry_of.get(c, "未知"), []).append(pe)
    medians = {}
    for ind_name, vals in by_ind.items():
        medians[ind_name] = float(np.median(vals)) if len(vals) >= min_members else market_med
    medians["__market__"] = market_med
    return medians


def _select_at_date(t, data, industry_of, cal) -> pd.DataFrame:
    """某调仓日的Neff选股（全部使用t当日可见数据，无未来函数）。
    条件（标准版）：PE_TTM>0且<行业中位 × 1.1口径容忍 / 股息率>0 / EPS同比>0 / TRR>=1.5；
    按TRR降序返回候选表[代码, TRR, PE_TTM, 股息率, eps_yoy]。"""
    p, np_ = BACKTEST_PARAMS, NEFF_PARAMS
    rows = []
    for code, df in data.items():
        try:
            pe = df.at[t, "pe_ttm"]
            dv = df.at[t, "dv_ratio"]
            yoy = df.at[t, "eps_yoy"]
            px = df.at[t, "close_qfq"]
        except KeyError:
            continue
        if not (pd.notna(pe) and pd.notna(dv) and pd.notna(yoy) and pd.notna(px)):
            continue
        if pe <= 0 or dv <= np_["DIVIDEND_MIN"] or yoy <= np_["GROWTH_MIN"] or px <= 0:
            continue
        rows.append({"代码": code, "PE_TTM": pe, "股息率": dv, "eps_yoy": yoy})
    if not rows:
        return pd.DataFrame()
    snap = pd.DataFrame(rows)
    medians = _industry_medians(dict(zip(snap["代码"], snap["PE_TTM"])), industry_of)
    mkt = medians.get("__market__", np.nan)
    snap["行业中位"] = snap["代码"].map(lambda c: medians.get(industry_of.get(c), mkt))
    snap["TRR"] = (snap["股息率"] + snap["eps_yoy"] * 100) / snap["PE_TTM"]
    snap = snap[(snap["PE_TTM"] < snap["行业中位"] * 1.1) &
                (snap["TRR"] >= np_["TRR_MIN"])]
    return snap.sort_values("TRR", ascending=False).reset_index(drop=True)


def run_backtest():
    """回测主流程：日频遍历交易日 → 每日执行止损/止盈/回归兑现 → 调仓日执行
    基本面恶化卖出/超时轮换/重建组合 → 输出净值曲线与交易记录CSV + 绩效摘要。"""
    p, sp, pp, sell = BACKTEST_PARAMS, STOCK_POOL_PARAMS, PORTFOLIO_PARAMS, SELL_RULES
    ensure_dirs()
    print("\n" + "#" * 78)
    print("#  Neff低PE策略回测  区间:%s ~ %s  调仓:季度  止损:-15%%" %
          (p["START_DATE"], p["END_DATE"]))
    print("#" * 78)

    # ---- 数据准备 ----
    spot = fetch_spot_all_a()
    universe = _bt_universe(spot)
    imap = fetch_industry_map(use_cache=True)
    data, industry_of, cal = prepare_backtest_data(universe, imap)
    # 股票数下限随SAMPLE_SIZE自适应：用户调小样本时不应被固定阈值卡死
    min_required = min(50, len(universe))
    if len(data) < min_required:
        raise RuntimeError(f"可用股票仅{len(data)}只(需>={min_required})，请检查网络后重试")

    cal = cal[cal >= pd.Timestamp(p["START_DATE"])]
    rebal_months = set(p["REBALANCE_MONTHS"])
    # 调仓日 = 配置月份的首个交易日（季报披露基本完毕，信息可得）
    # guard: 只取日历范围内存在的月份，避免 next() 在无交易日时抛 StopIteration
    rebal_dates = set()
    for d in pd.date_range(p["START_DATE"], p["END_DATE"], freq="MS"):
        if d.month in rebal_months and d <= cal[-1]:
            rebal_dates.add(next(iter(cal[cal >= d])))

    # ---- 模拟交易状态 ----
    cash = float(PORTFOLIO_PARAMS["TOTAL_CAPITAL"])   # 初始资金
    portfolio = {}        # code -> dict(股数, 成本价qfq, 买入日, 负增长连击数)
    trades, nav_rows = [], []
    cal_list = list(cal)

    def price_of(code, t):
        """t日的前复权价（停牌沿用最近价）。"""
        return data[code].at[t, "close_qfq"] if t in data[code].index else np.nan

    def do_sell(code, t, reason):
        """按当日收盘价卖出全部持仓（含佣金+印花税），记录成交。
        简化假设：以信号当日收盘成交；实盘可改为次日开盘执行（影响很小）。"""
        nonlocal cash
        pos = portfolio.pop(code)
        px = price_of(code, t)
        if not (pd.notna(px) and px > 0):        # 数据终点（退市/长期停牌）按最近价处理
            px = pos["最后价"]
        amount = pos["股数"] * px
        fee = max(amount * p["COMMISSION"], p["MIN_COMMISSION"]) + amount * p["STAMP_TAX"]
        cash += amount - fee
        pnl = px / pos["成本价"] - 1
        trades.append({"代码": code, "买入日": pos["买入日"].date(), "买入价": round(pos["成本价"], 3),
                       "卖出日": t.date(), "卖出价": round(px, 3), "股数": pos["股数"],
                       "盈亏%": round(pnl * 100, 2), "持有交易日": cal_list.index(t) - pos["买入序"],
                       "卖出原因": reason})

    logger.info("开始逐日模拟：%d 个交易日，调仓日 %d 个", len(cal_list), len(rebal_dates))
    for ti, t in enumerate(cal_list):
        # ---------- 1) 每日风控：止损-15% / 止盈+50% / PE回归兑现 ----------
        for code in list(portfolio):
            pos = portfolio[code]
            px = price_of(code, t)
            if pd.notna(px) and px > 0:
                pos["最后价"] = px
                pnl = px / pos["成本价"] - 1
                if pnl <= pp["STOP_LOSS"]:                       # ★ 硬性止损(-15%)
                    do_sell(code, t, "止损-15%")
                elif pnl >= sell["TAKE_PROFIT_GAIN"]:            # 价值回归止盈
                    do_sell(code, t, f"止盈+{sell['TAKE_PROFIT_GAIN']:.0%}")
                else:
                    # PE回升至行业中位×1.2 → 低估红利已兑现（Neff式卖出）
                    pe_now = data[code].at[t, "pe_ttm"] if t in data[code].index else np.nan
                    snap_med = None   # 占位：当日行业中位懒计算成本高，改用调仓日缓存在持仓里
                    if pos.get("行业中位") and pd.notna(pe_now) and pe_now > 0:
                        if pe_now >= pos["行业中位"] * sell["PE_REGRESSION_MULT"]:
                            do_sell(code, t, "PE回归兑现")

        # ---------- 2) 调仓日：基本面恶化/超时轮换卖出 + 组合重建 ----------
        if t in rebal_dates:
            # 2a) 卖出信号检查（用当日EPS同比/持有时长）
            for code in list(portfolio):
                pos = portfolio[code]
                dfc = data[code]
                eps_now = dfc.at[t, "eps_ttm"] if t in dfc.index else np.nan
                yoy_now = dfc.at[t, "eps_yoy"] if t in dfc.index else np.nan
                if sell["LOSS_MAKING_SELL"] and pd.notna(eps_now) and eps_now <= 0:
                    do_sell(code, t, "净利润转亏")
                    continue
                if sell["NEG_GROWTH_SELL"] and pd.notna(yoy_now):
                    if yoy_now < 0:
                        pos["负增长连击"] = pos.get("负增长连击", 0) + 1
                        if pos["负增长连击"] >= 2:               # 连续两个检查期下滑
                            do_sell(code, t, "连续两期净利下滑")
                            continue
                    else:
                        pos["负增长连击"] = 0
                if (t - pos["买入日"]).days > sell["MAX_HOLD_DAYS"]:   # 超时轮换
                    do_sell(code, t, "超时轮换(2年)")

            # 2b) 重建组合：老持仓仍达标者保留（降低换手，符合耐心持有），空位由新高TRR候选补足
            cands = _select_at_date(t, data, industry_of, cal)
            if cands.empty:
                logger.info("%s 调仓日无合格候选，空仓等待", t.date())
            else:
                medians = _industry_medians(dict(zip(cands["代码"], cands["PE_TTM"])), industry_of)
                mkt = medians.get("__market__", np.nan)
                held = [c for c in portfolio if c in set(cands["代码"])]     # 仍达标的老持仓
                fresh = [c for c in cands["代码"] if c not in portfolio]     # 新候选
                n_target = min(max(len(cands), pp["MIN_HOLDINGS"]), pp["MAX_HOLDINGS"])
                weight = min(1.0 / n_target, pp["MAX_WEIGHT"])
                # 更新老持仓的PE兑现锚（用最新行业中位数）
                for c in held:
                    portfolio[c]["行业中位"] = medians.get(industry_of.get(c), mkt)
                equity_now = cash + sum(pos["股数"] * price_of(c, t)
                                        for c, pos in portfolio.items())
                free_slots = n_target - len(held)
                for code in fresh:
                    if free_slots <= 0:
                        break
                    if code not in data or portfolio.get(code):
                        continue
                    px = price_of(code, t)
                    if not (pd.notna(px) and px > 0):
                        continue
                    budget = min(equity_now * weight, cash)   # 单只预算=总资产×权重(≤12%)，受现金约束
                    shares = int(budget / px / 100) * 100      # A股整手(100股)约束
                    if shares <= 0:
                        continue
                    amount = shares * px
                    fee = max(amount * p["COMMISSION"], p["MIN_COMMISSION"])
                    if amount + fee > cash:                    # 现金不足则放弃（保守，不加杠杆）
                        continue
                    cash -= amount + fee
                    portfolio[code] = {"股数": shares, "成本价": px, "买入日": t,
                                       "买入序": ti, "最后价": px,
                                       "行业中位": medians.get(industry_of.get(code), mkt),
                                       "负增长连击": 0}
                    free_slots -= 1
                logger.info("%s 调仓: 持仓%d只(目标%d) 候选%d 现金%.0f",
                            t.date(), len(portfolio), n_target, len(cands), cash)

        # ---------- 3) 记录当日净值 ----------
        def _mark(c, pos):
            """持仓盯市价：当日有价用当日，无价(停牌/数据缺口)沿用最后有效价。"""
            px = price_of(c, t)
            return px if pd.notna(px) else pos["最后价"]
        equity = cash + sum(pos["股数"] * _mark(c, pos) for c, pos in portfolio.items())
        nav_rows.append({"日期": t.date(), "总资产": round(equity, 2)})

    # ---- 绩效统计与输出 ----
    nav = pd.DataFrame(nav_rows).set_index("日期")
    nav0 = nav["总资产"].iloc[0]
    nav["策略净值"] = nav["总资产"] / nav0 if nav0 else np.nan
    bench = fetch_index_history(p["BENCHMARK"], p["START_DATE"], p["END_DATE"])
    bench["dt"] = pd.to_datetime(bench["日期"])
    bench = bench.set_index("dt")["收盘"].apply(to_num)
    nav["基准净值"] = bench.reindex(nav.index).ffill()
    nav["基准净值"] = nav["基准净值"] / nav["基准净值"].dropna().iloc[0]

    def perf(nv: pd.Series):
        """年化收益/波动/夏普/最大回撤（244个交易日/年）。"""
        ret = nv.pct_change().dropna()
        years = len(nv) / 244
        ann = nv.iloc[-1] ** (1 / years) - 1 if years > 0 else np.nan
        vol = ret.std() * np.sqrt(244)
        sharpe = (ann - p["RISK_FREE"]) / vol if vol > 0 else np.nan
        mdd = (nv / nv.cummax() - 1).min()
        return ann, vol, sharpe, mdd

    ann, vol, sharpe, mdd = perf(nav["策略净值"])
    b_ann, b_vol, _, b_mdd = perf(nav["基准净值"].dropna())
    tr = pd.DataFrame(trades)
    sells = tr[tr["卖出原因"].notna()] if not tr.empty else pd.DataFrame()
    win_rate = (sells["盈亏%"] > 0).mean() if not sells.empty else np.nan
    stop_cnt = (sells["卖出原因"].str.startswith("止损")).sum() if not sells.empty else 0

    # 净值曲线CSV（含回撤列，便于用户自行画图）
    nav["策略回撤%"] = (nav["策略净值"] / nav["策略净值"].cummax() - 1) * 100
    nav_out = nav[["策略净值", "基准净值", "策略回撤%"]].round(4)
    nav_out.to_csv(os.path.join(OUTPUT_DIR, "回测净值曲线.csv"), encoding="utf-8-sig")
    tr.to_csv(os.path.join(OUTPUT_DIR, "回测交易记录.csv"), index=False, encoding="utf-8-sig")

    summary = pd.DataFrame([
        ["回测区间", f"{p['START_DATE']} ~ {p['END_DATE']}"],
        ["股票池", f"流通市值前{p['SAMPLE_SIZE']}只(幸存者偏差见说明)"],
        ["初始资金(元)", f"{PORTFOLIO_PARAMS['TOTAL_CAPITAL']:,}"],
        ["期末总资产(元)", f"{nav['总资产'].iloc[-1]:,.0f}"],
        ["策略累计收益", f"{(nav['策略净值'].iloc[-1] - 1) * 100:.1f}%"],
        ["策略年化收益", f"{ann * 100:.2f}%"],
        ["策略年化波动", f"{vol * 100:.2f}%"],
        ["夏普比率(rf=2%)", f"{sharpe:.2f}"],
        ["策略最大回撤", f"{mdd * 100:.1f}%"],
        ["基准(沪深300)年化", f"{b_ann * 100:.2f}%"],
        ["基准最大回撤", f"{b_mdd * 100:.1f}%"],
        ["年化超额(vs基准)", f"{(ann - b_ann) * 100:.2f}个百分点"],
        ["成交笔数(卖出)", f"{len(sells)}"],
        ["单笔胜率", f"{win_rate * 100:.1f}%" if pd.notna(win_rate) else "-"],
        ["止损触发次数", f"{stop_cnt}"],
        ["平均持有交易日", f"{sells['持有交易日'].mean():.0f}" if not sells.empty else "-"],
    ], columns=["指标", "数值"])
    summary.to_csv(os.path.join(OUTPUT_DIR, "回测绩效摘要.csv"), index=False, encoding="utf-8-sig")

    print_table("回测绩效摘要", ["指标", "数值"],
                summary.values.tolist(), aligns=["l", "r"])
    if not sells.empty:
        print_table("卖出原因分布", ["原因", "次数", "平均盈亏%"],
                    sells.groupby("卖出原因").agg(次数=("盈亏%", "size"),
                                              平均盈亏=("盈亏%", "mean")).round(1).reset_index()
                    .values.tolist())
    print(f"\n✔ 回测明细已保存: 回测净值曲线.csv / 回测交易记录.csv / 回测绩效摘要.csv → {OUTPUT_DIR}")
    print("  ⚠ 回测含幸存者偏差，仅供策略逻辑验证，不构成投资建议。")


# ==============================================================================
# 第六部分：持仓监控模块（四大卖出信号 + 仓位偏离检查 + 补仓建议）
#
# 输入: neff_output/holdings.csv（由 template 命令生成模板，用户填真实持仓）
#   列: 代码,名称,买入日期(YYYY-MM-DD),买入价,持股数,备注
# 输出: 每只持仓的操作建议（按信号优先级）+ 组合层面的仓位诊断 + CSV留档
# ==============================================================================

def _growth_and_eps_series(period: str) -> pd.DataFrame:
    """提取某报告期全A的 净利润同比(%) 与 每股收益(元)，返回以代码为索引的表。
    监控用最新两期数据判断"基本面恶化"：每股收益<=0 → 转亏；
    连续两期净利润同比<0 → 持续下滑。"""
    df = fetch_earnings_bulk(period)
    if df is None or df.empty:
        return pd.DataFrame(columns=["净利润同比", "每股收益"])
    code_col = find_col(df, ["股票代码"])
    # 同样必须精确匹配"净利润-同比增长"，避免撞上净利润额列（实测踩坑）
    growth_col = find_col(df, ["净利润-同比增长"]) or \
        find_col(df, ["净利润同比增长"]) or \
        find_col(df, ["同比增长"], exclude=["营业收入", "环比"])
    eps_col = find_col(df, ["每股收益"], exclude=["净资产", "经营"])
    if not code_col or not (growth_col or eps_col):
        logger.warning("报告期 %s 业绩表字段不完整: %s", period, list(df.columns))
        return pd.DataFrame(columns=["净利润同比", "每股收益"])
    # 注意：这里必须用 .values 对齐位置，否则 DataFrame(默认RangeIndex)与
    # 自定义代码索引发生隐式对齐，会导致整列变 NaN（曾踩坑）
    out = pd.DataFrame({
        "净利润同比": to_num(df[growth_col]).values if growth_col else np.nan,
        "每股收益": to_num(df[eps_col]).values if eps_col else np.nan,
    }, index=df[code_col].astype(str).str.zfill(6).values)
    out = out[~out.index.duplicated(keep="first")]
    return out


def make_holdings_template():
    """生成持仓明细模板（含两行示例，抄格式填成真实持仓后另存/改名为 holdings.csv）。"""
    ensure_dirs()
    demo = pd.DataFrame([
        {"代码": "600519", "名称": "贵州茅台", "买入日期": "2026-01-06",
         "买入价": 1450.00, "持股数": 100, "备注": "示例行→请替换为真实持仓"},
        {"代码": "000333", "名称": "美的集团", "买入日期": "2026-03-10",
         "买入价": 62.50, "持股数": 1600, "备注": "示例行→请替换为真实持仓"},
    ])[HOLDINGS_COLUMNS]
    demo.to_csv(TEMPLATE_FILE, index=False, encoding="utf-8-sig")
    print(f"✔ 持仓模板已生成: {TEMPLATE_FILE}")
    print("  使用步骤: 1)把示例行替换为你的真实持仓(可增删行)")
    print(f"           2)另存为 {HOLDINGS_FILE}（或直接改名）")
    print("           3)执行 python neff_value_strategy.py monitor 即可监控")


def load_holdings(path: str = None) -> pd.DataFrame:
    """读取并校验持仓文件：列不齐/为空时给出明确指引而非报错崩溃。"""
    path = path or HOLDINGS_FILE
    if not os.path.exists(path):
        print(f"\n✘ 未找到持仓文件: {path}")
        print("  请先执行 python neff_value_strategy.py template 生成模板，")
        print("  填入真实持仓后再运行 monitor。")
        return pd.DataFrame()
    df = pd.read_csv(path, dtype={"代码": str})
    df["代码"] = df["代码"].astype(str).str.strip().str.lstrip("=").str.zfill(6)
    missing = [c for c in HOLDINGS_COLUMNS if c not in df.columns]
    if missing:
        print(f"✘ 持仓文件缺少列: {missing}，请按模板格式修改")
        return pd.DataFrame()
    df = df.dropna(subset=["代码", "买入价", "持股数"]).reset_index(drop=True)
    df["买入日期"] = pd.to_datetime(df["买入日期"], errors="coerce")
    df = df[df["买入日期"].notna()]
    df["买入价"] = to_num(df["买入价"])
    df["持股数"] = to_num(df["持股数"])
    return df


def run_monitor():
    """持仓监控主流程：
    信号优先级: ①止损-15%(强制) ②净利润转亏(强制) ③连续两期净利下滑
                ④回归止盈(+50%或PE回归) ⑤超时轮换(2年) ⑥正常持有；
    另检查单只权重是否在8%~12%区间、组合是否满足8~12只，不足给出补仓候选。"""
    ensure_dirs()
    p, sell = PORTFOLIO_PARAMS, SELL_RULES
    print("\n" + "#" * 78)
    print("#  Neff持仓监控  (止损-15%% / 回归止盈+50%%或PE回归 / 基本面恶化 / 超时轮换)")
    print("#" * 78)

    holdings = load_holdings()
    if holdings.empty:
        return
    today = pd.Timestamp(date.today())

    # ---- 并行准备三类数据：行情快照 / 行业估值锚 / 最新两期业绩 ----
    spot = fetch_spot_all_a()
    uni = prepare_stock_universe(spot)[["代码", "名称", "现价", "PE动态"]]
    uni = attach_industry_pe(uni)                       # 附带行业中位PE(动态口径)
    spot_idx = uni.set_index("代码")
    period_now = latest_report_period()
    period_prev = prev_report_period(period_now)
    fin_now = _growth_and_eps_series(period_now)
    fin_prev = _growth_and_eps_series(period_prev)
    logger.info("业绩基准期: 最新=%s 上一期=%s", period_now, period_prev)

    rows, forced = [], []
    for _, h in holdings.iterrows():
        code = h["代码"]
        cost = float(h["买入价"])
        px_series = spot_idx["现价"].get(code, np.nan)
        px = float(px_series) if pd.notna(px_series) else np.nan
        name = spot_idx["名称"].get(code, h["名称"]) if "名称" in spot_idx.columns else h["名称"]
        days = int((today - h["买入日期"]).days)
        row = {"代码": code, "名称": name,
               "现价": round(px, 2) if pd.notna(px) else None,
               "买入价": cost, "持股数": int(h["持股数"]),
               "盈亏%": round((px / cost - 1) * 100, 2) if pd.notna(px) else None,
               "持有天数": days}
        if pd.isna(px):
            row.update({"卖出信号": "数据缺失", "建议动作": "查日志，人工核实行情"})
            rows.append(row)
            continue

        # ---- 四大卖出信号（按优先级取第一个命中的）----
        signal, action = "正常持有", "耐心持有，等待价值回归"
        mv = px * float(h["持股数"])
        weight = mv / p["TOTAL_CAPITAL"]
        pnl = px / cost - 1
        g_now = fin_now["净利润同比"].get(code, np.nan) if not fin_now.empty else np.nan
        g_prev = fin_prev["净利润同比"].get(code, np.nan) if not fin_prev.empty else np.nan
        eps_now = fin_now["每股收益"].get(code, np.nan) if not fin_now.empty else np.nan
        pe_now = spot_idx["PE动态"].get(code, np.nan)
        ind_med = spot_idx["行业中位PE"].get(code, np.nan)

        if pnl <= p["STOP_LOSS"]:                                   # ① 硬性止损
            signal, action = "【强制】止损-15%", "明日开盘卖出，纪律优先，勿抱侥幸"
            forced.append(code)
        elif pd.notna(eps_now) and eps_now <= 0 and sell["LOSS_MAKING_SELL"]:   # ② 转亏
            signal, action = "【强制】净利润转亏", "低PE前提已破坏，无论盈亏立即清仓"
            forced.append(code)
        elif (sell["NEG_GROWTH_SELL"] and pd.notna(g_now) and pd.notna(g_prev)
              and g_now < 0 and g_prev < 0):                        # ③ 连续两期下滑
            signal, action = "【强制】连续两期净利下滑", "基本面持续恶化，建议清仓"
            forced.append(code)
        elif pnl >= sell["TAKE_PROFIT_GAIN"] or \
                (pd.notna(pe_now) and pd.notna(ind_med) and
                 pe_now >= ind_med * sell["PE_REGRESSION_MULT"]):   # ④ 回归止盈
            signal, action = "回归止盈", "价值已回归，建议分批止盈兑现（Neff式卖出）"
        elif days > sell["MAX_HOLD_DAYS"]:                          # ⑤ 超时轮换
            signal, action = "超时轮换", "持有满2年未兑现，轮出换入新候选"
        else:                                                       # ⑥ 正常持有
            if pd.notna(g_now) and g_now < 0:
                action = "持有但警惕:最新净利增速转负，下期再负将触发清仓"
        row.update({"卖出信号": signal, "建议动作": action,
                    "当前权重%": round(weight * 100, 2),
                    "PE动态": round(pe_now, 1) if pd.notna(pe_now) else None,
                    "行业中位PE": round(ind_med, 1) if pd.notna(ind_med) else None,
                    "净利同比%": round(g_now, 1) if pd.notna(g_now) else None,
                    "市值(元)": round(mv, 0)})
        # 仓位偏离提醒（8%~12%纪律带，超出/低于都提示）
        if weight > p["MAX_WEIGHT"] + 0.005:
            row["建议动作"] += f"｜权重{weight:.0%}超12%上限，建议减持"
        elif weight < p["MIN_WEIGHT"] - 0.005:
            row["建议动作"] += f"｜权重{weight:.0%}低于8%下限，可补足"
        rows.append(row)

    mon = pd.DataFrame(rows)
    mon_file = os.path.join(OUTPUT_DIR, f"持仓监控_{date.today():%Y%m%d}.csv")
    mon.to_csv(mon_file, index=False, encoding="utf-8-sig")

    print_table("持仓信号明细", ["代码", "名称", "现价", "买入价", "盈亏%", "持有天数",
                             "当前权重%", "卖出信号", "建议动作"],
                [[r["代码"], r["名称"], r["现价"], r["买入价"], r["盈亏%"],
                  r["持有天数"], r["当前权重%"], r["卖出信号"], r["建议动作"]]
                 for _, r in mon.iterrows()],
                aligns=["l", "l", "r", "r", "r", "r", "r", "l", "l"])

    # ---- 组合层面诊断：只数与总仓位 ----
    n = len(holdings)
    invested = mon["市值(元)"].dropna().sum()
    print(f"\n◇ 组合诊断: 持仓{n}只（要求8~12只）｜持仓市值 {invested:,.0f} 元"
          f"｜现金比例约 {max(0, 1 - invested / p['TOTAL_CAPITAL']):.0%}")
    if n < p["MIN_HOLDINGS"]:
        need = p["MIN_HOLDINGS"] - n
        print(f"◇ 持仓不足{p['MIN_HOLDINGS']}只 → 以下 {need} 只补仓候选来自最新Neff筛选:")
        # 优先复用今天的选股结果，避免重复计算；没有则现场跑一次(quiet)
        today_file = os.path.join(OUTPUT_DIR, f"筛选结果_{date.today():%Y%m%d}.csv")
        if os.path.exists(today_file):
            picks = pd.read_csv(today_file, dtype={"代码": str})
        else:
            picks = run_screening(quiet=True)
        if picks is not None and not picks.empty:
            held_codes = set(holdings["代码"])
            picks = picks[~picks["代码"].isin(held_codes)].head(need)
            print_table("补仓候选（按TRR降序）",
                        ["代码", "名称", "行业", "PE-TTM", "TRR", "股息率", "建议金额(元)"],
                        [[r["代码"], r["名称"], r["行业"], f"{r['PE_TTM']:.1f}",
                          f"{r['TRR']:.2f}", f"{r['股息率']:.2f}%",
                          f"{r['建议金额(元)']:,.0f}"] for _, r in picks.iterrows()])
        else:
            print("  暂无合格候选 → 保留现金耐心等待（内夫：宁可错过，不可买错）")
    if forced:
        print(f"\n★ 今日有 {len(forced)} 只触发强制卖出信号，请勿拖延执行: {', '.join(forced)}")
    print(f"\n✔ 监控结果已保存: {mon_file}")


# ==============================================================================
# 第七部分：命令行入口
# ==============================================================================

def main():
    """命令行分发。无参数时打印帮助。任何未捕获异常都落日志并给出排查指引。"""
    parser = argparse.ArgumentParser(
        prog="neff_value_strategy",
        description="约翰·内夫低PE价值投资策略（全A股）三合一脚本：选股/回测/持仓监控",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
               "  python neff_value_strategy.py screen     # Neff选股\n"
               "  python neff_value_strategy.py backtest   # 5年回测(首次约20-40分钟)\n"
               "  python neff_value_strategy.py template   # 生成持仓模板\n"
               "  python neff_value_strategy.py monitor    # 持仓监控\n"
               "  python neff_value_strategy.py all        # 选股+监控\n")
    parser.add_argument("command", nargs="?", choices=["screen", "backtest", "monitor",
                                                       "template", "all"],
                        help="要执行的命令")
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "screen":
            run_screening()
        elif args.command == "backtest":
            run_backtest()
        elif args.command == "monitor":
            run_monitor()
        elif args.command == "template":
            make_holdings_template()
        elif args.command == "all":
            run_screening()
            run_monitor()
    except KeyboardInterrupt:
        print("\n用户中断，已安全退出。")
    except Exception as e:  # noqa: BLE001 —— 顶层兜底：给用户指路而不是甩堆栈
        logger.exception("执行 [%s] 出现未处理异常", args.command)
        print(f"\n✘ 执行失败: {e}")
        print(f"  详细原因已记录到日志: {LOG_FILE}，请查看最后几行定位问题。")
        sys.exit(1)


if __name__ == "__main__":
    main()
