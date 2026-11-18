# -*- coding: utf-8 -*-
"""商品期货板块复盘:当日全市场快照 + 六大板块拆解 + 持仓量日增减 TOP10

内容(4 张扩展图,编号规则见 strategies/plot_paths.py;本脚本占用 23–26,09–22 已被其他脚本占用):
    23 全市场主力合约今日涨跌幅全景(横条,红涨绿跌)
    24 六大板块平均涨跌幅(柱状,叠加板块内涨/跌家数与全市场均值)
    25 近 5 个交易日六大板块累计表现(成员归一化后等权平均,起点=100)
    26 主力合约持仓量日增减 TOP10(增仓红 / 减仓绿,在 32 个主流活跃品种中统计)

数据源(全走新浪,不经东方财富——clist 接口在本机被限流):
    - 主力连续清单:AKShare ak.futures_display_main_sina()(仅 symbol/exchange/name 三列,
      剔除中金所 cffex 金融期货)
    - 实时快照:新浪 hq.sinajs.cn 批量 nf_ 行情(与 futures_top5_chart.py 同源,字段按索引解析):
      [8]=最新价 [9]=均价 [10]=昨结算 [13]=持仓量 [14]=成交量 [17]=行情日期
      涨跌幅 = 最新价 / 昨收盘 - 1(应口径要求采用昨收盘基准;昨结算列保留备查)
    - 昨收盘:ak.futures_main_sina(symbol="XX0", start_date=近 7 天, end_date=今日)窄窗口日线,
      取"日期 < 今日"最后一根的收盘价(新浪 T 日 bar 结算后才生成,今日 bar 不可用);
      逐品种请求间 sleep(0.3) 防限流;取不到的品种涨跌幅置空并记录,不得用昨结算顶替。
    - 日线:ak.futures_main_sina(symbol="XX0")。新浪 T 日日 bar 在结算后才发布,盘后即时点
      最新一根通常是 T-1,故"近 5 个交易日"收盘序列 = 最近 4 根日 bar 收盘价 + 今日实时
      最新价拼接(若日 bar 已含今日则直接取最近 5 根);逐品种请求间 sleep(0.5) 防限流。

板块映射:品种代码(字母部分)→ 六大板块,静态字典,覆盖新浪能取到的全部商品主力品种。
    归类口径(产业链习惯):焦炭/焦煤/铁合金归黑色;氧化铝归有色;纯碱/纸浆/聚酯链归能化;
    棕榈油归农产品(油脂);工业硅/多晶硅/碳酸锂归新能源金属/新材料;
    集运指数 EC 为运价指数、非商品,不纳入任何板块(快照与全景图仍保留)。

输出:
    - reports/YYYYMMDD/23_sector.png / 24_sector_avg.png / 25_sector_5d.png / 26_oi_change.png
    - strategies/output/futures/YYYYMMDD_snapshot.csv(当日全市场快照表)
运行:.venv/bin/python strategies/futures/futures_sector_review.py
"""

from __future__ import annotations

import datetime as dt
import os
import sys
import time
import warnings

import akshare as ak
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import requests
from matplotlib.patches import Patch

# 将 strategies/ 目录加入 sys.path,确保能导入共享模块 plot_paths
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plot_paths import report_image_path

warnings.filterwarnings("ignore")
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC","Noto Sans SC","Microsoft YaHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False

matplotlib.rcParams["text.color"] = "#27254c"
matplotlib.rcParams["axes.labelcolor"] = "#27254c"
matplotlib.rcParams["axes.titlecolor"] = "#27254c"
matplotlib.rcParams["xtick.color"] = "#27254c"
matplotlib.rcParams["ytick.color"] = "#27254c"

UP_COLOR = "#F36"    # 红涨
DOWN_COLOR = "#0C9"  # 绿跌
BLUE = "#99F"
YELLOW = "#FC3"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "output", "futures")

EXCLUDE_EXCHANGE = {"cffex"}  # 剔除金融期货
EXCHANGE_ZH = {
    "dce": "大商所", "czce": "郑商所", "shfe": "上期所",
    "ine": "上期能源", "gfex": "广期所", "cffex": "中金所",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://vip.stock.finance.sina.com.cn/",
}

# nf_ 字段索引:0=合约名, 1=时间, 8=最新价, 9=均价, 10=昨结算, 13=持仓量, 14=成交量, 17=行情日期
IDX_NAME, IDX_TIME, IDX_CURRENT, IDX_AVG, IDX_SETTLE, IDX_OI, IDX_VOL, IDX_DATE = 0, 1, 8, 9, 10, 13, 14, 17

SECTORS = ["黑色建材", "有色", "贵金属", "能源化工", "农产品", "新能源金属/新材料"]
SECTOR_COLOR = {
    "黑色建材": "#666666", "有色": "#FC3", "贵金属": "#F36",
    "能源化工": "#99F", "农产品": "#0C9", "新能源金属/新材料": "#9B59B6",
}

# 品种代码 -> 板块(六大板块,归类口径见文件头注释)
SECTOR_MAP: dict[str, str] = {
    # 黑色建材:黑色产业链(螺纹/热卷/铁矿/双焦/铁合金)+ 建材(玻璃/动力煤/线材/原木)
    "RB": "黑色建材", "HC": "黑色建材", "I": "黑色建材", "J": "黑色建材", "JM": "黑色建材",
    "SF": "黑色建材", "SM": "黑色建材", "FG": "黑色建材", "ZC": "黑色建材", "WR": "黑色建材",
    "LG": "黑色建材",
    # 有色:工业金属及其原料(氧化铝);SS 不锈钢、BC 国际铜同属有色
    "CU": "有色", "AL": "有色", "ZN": "有色", "PB": "有色", "NI": "有色", "SN": "有色",
    "SS": "有色", "AO": "有色", "BC": "有色",
    # 贵金属
    "AU": "贵金属", "AG": "贵金属",
    # 能源化工:油气燃料/橡胶/聚酯链/烯烃/煤化工/纯碱/烧碱/纸浆(轻工中游加工,归此口径)
    "SC": "能源化工", "LU": "能源化工", "FU": "能源化工", "BU": "能源化工", "PG": "能源化工",
    "RU": "能源化工", "NR": "能源化工", "BR": "能源化工", "TA": "能源化工", "MA": "能源化工",
    "PP": "能源化工", "L": "能源化工", "V": "能源化工", "EG": "能源化工", "EB": "能源化工",
    "SP": "能源化工", "UR": "能源化工", "SA": "能源化工", "SH": "能源化工", "PX": "能源化工",
    "PF": "能源化工", "PR": "能源化工",
    # 农产品:油脂油料/谷物/软商品/禽畜/果蔬(棕榈油为油脂,归此)
    "A": "农产品", "B": "农产品", "M": "农产品", "Y": "农产品", "P": "农产品", "C": "农产品",
    "CS": "农产品", "RR": "农产品", "LH": "农产品", "JD": "农产品", "SR": "农产品",
    "CF": "农产品", "CY": "农产品", "OI": "农产品", "RM": "农产品", "RS": "农产品",
    "AP": "农产品", "CJ": "农产品", "PK": "农产品",
    # 新能源金属/新材料:光伏(工业硅/多晶硅)+ 电池(碳酸锂)
    "SI": "新能源金属/新材料", "LC": "新能源金属/新材料", "PS": "新能源金属/新材料",
    # 2025 年以来新上市品种补录
    "AD": "有色",        # 铸造铝合金(上期所)
    "PD": "贵金属", "PT": "贵金属",               # 钯 / 铂(广期所)
    "BZ": "能源化工", "PL": "能源化工", "OP": "能源化工",  # 纯苯 / 丙烯 / 胶版印刷纸
    "SO": "农产品",      # 葵花籽油(郑商所)
    "FB": "黑色建材",    # 纤维板(大商所,木质建材)
    # 注:EC 集运欧线为运价指数(非商品),不纳入板块
}

# 图 11/12 的主流活跃品种(约 30 个,覆盖六大板块;逐品种取日线,量控制在防限流范围)
LIQUID = [
    "RB", "HC", "I", "J", "JM", "FG",            # 黑色建材
    "CU", "AL", "ZN", "PB", "NI", "SN",          # 有色
    "AU", "AG",                                   # 贵金属
    "SC", "FU", "BU", "RU", "TA", "MA", "PP", "L",  # 能源化工
    "M", "Y", "P", "C", "SR", "CF", "LH",        # 农产品
    "SI", "LC", "PS",                             # 新能源金属/新材料
]


def fetch_quotes(symbols: list[str]) -> pd.DataFrame:
    """批量拉取 nf_ 实时行情(一次请求),按字段索引解析。"""
    subs = ",".join(f"nf_{s}" for s in symbols)
    url = f"https://hq.sinajs.cn/rn={int(time.time())}&list={subs}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.encoding = "gbk"

    rows: list[dict] = []
    for line in r.text.split(";"):
        if "hq_str_nf_" not in line:
            continue
        head, _, payload = line.partition("=")
        symbol = head.split("hq_str_nf_")[1].strip()
        parts = payload.strip().strip('"').split(",")
        if len(parts) <= IDX_DATE:
            continue

        def num(i: int) -> float:
            try:
                return float(parts[i])
            except ValueError:
                return float("nan")

        rows.append({
            "代码": symbol,
            "合约名": parts[IDX_NAME],
            "行情时间": parts[IDX_TIME],
            "行情日期": parts[IDX_DATE],
            "最新价": num(IDX_CURRENT),
            "均价": num(IDX_AVG),
            "昨结算": num(IDX_SETTLE),
            "持仓量": num(IDX_OI),
            "成交量": num(IDX_VOL),
        })
    return pd.DataFrame(rows)


def fetch_prev_closes(codes: list[str], today: dt.date) -> tuple[dict[str, float], list[str]]:
    """昨收盘:窄窗口日线取"日期 < 今日"最后一根收盘价(今日 bar 不可用)。

    返回 ({代码: 昨收盘}, 取不到的代码列表)。昨收盘是涨跌幅的分母,取不到时
    该品种涨跌幅必须置空,不得用昨结算顶替。
    """
    closes: dict[str, float] = {}
    failed: list[str] = []
    start = (today - dt.timedelta(days=7)).strftime("%Y%m%d")
    for code in codes:
        try:
            d = ak.futures_main_sina(symbol=code, start_date=start, end_date=f"{today:%Y%m%d}")
            d["日期"] = pd.to_datetime(d["日期"])
            d["收盘价"] = pd.to_numeric(d["收盘价"], errors="coerce")
            d = d[(d["日期"].dt.date < today) & d["收盘价"].notna()]
            if len(d):
                closes[code] = float(d["收盘价"].iloc[-1])
            else:
                failed.append(code)
        except Exception:  # noqa: BLE001
            failed.append(code)
        time.sleep(0.3)  # 防限流
    return closes, failed


def build_snapshot(today: dt.date) -> pd.DataFrame:
    """当日全市场商品主力连续快照表(含 CSV 落盘)。"""
    disp = ak.futures_display_main_sina()
    disp = disp[~disp["exchange"].isin(EXCLUDE_EXCHANGE)].reset_index(drop=True)
    disp = disp.rename(columns={"symbol": "代码"})
    codes = disp["代码"].tolist()
    quotes = fetch_quotes(codes)
    closes, failed = fetch_prev_closes(codes, today)
    if failed:
        print(f"  [缺失] 昨收盘取不到、涨跌幅置空的品种: {', '.join(failed)}")

    df = disp.merge(quotes, on="代码", how="left")
    df["品种"] = df["代码"].str.rstrip("0123456789")
    df["品种名"] = df["name"].str.replace("连续", "", regex=False)
    df["交易所"] = df["exchange"].map(EXCHANGE_ZH).fillna(df["exchange"])
    df["昨收盘"] = df["代码"].map(closes)
    df["涨跌幅(%)"] = (df["最新价"] / df["昨收盘"] - 1) * 100

    cols = ["品种", "品种名", "代码", "交易所", "合约名", "行情日期", "行情时间",
            "最新价", "昨收盘", "昨结算", "均价", "涨跌幅(%)", "成交量", "持仓量"]
    df = df[cols].sort_values("代码").reset_index(drop=True)

    os.makedirs(OUT_DIR, exist_ok=True)
    csv_path = os.path.join(OUT_DIR, f"{today:%Y%m%d}_snapshot.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"快照已保存: {csv_path}(共 {len(df)} 个品种)")
    return df


def fetch_daily(code: str) -> pd.DataFrame:
    """单品种主力连续日线(日期/收盘价/持仓量)。"""
    df = ak.futures_main_sina(symbol=f"{code}0")
    df["日期"] = pd.to_datetime(df["日期"])
    df["收盘价"] = pd.to_numeric(df["收盘价"], errors="coerce")
    df["持仓量"] = pd.to_numeric(df["持仓量"], errors="coerce")
    return df.dropna(subset=["收盘价"]).reset_index(drop=True)


def build_liquid_series(snapshot: pd.DataFrame, today: dt.date):
    """逐品种取日线并拼接今日实时收盘,得近 5 个交易日收盘序列;同时取昨收持仓量。

    返回:
        px: {品种代码: 收盘价 Series(最近 5 个交易日,今日用实时最新价)}
        oi_prev: {品种代码: 上一交易日收盘持仓量(今日实时持仓与之相减得日增减)}
    """
    snap_idx = snapshot.set_index("品种")
    px: dict[str, pd.Series] = {}
    oi_prev: dict[str, float] = {}
    for code in LIQUID:
        try:
            df = fetch_daily(code)
        except Exception as e:  # noqa: BLE001
            print(f"  [跳过] {code}: {type(e).__name__}")
            time.sleep(0.5)
            continue

        # 收盘序列:日 bar 未含今日时,拼接今日实时最新价(若日 bar 已含今日则直接取最近 5 根)
        d = df[["日期", "收盘价"]].copy()
        if len(d) and d["日期"].iloc[-1].date() < today:
            try:
                cur = float(snap_idx.loc[code, "最新价"])
                if cur > 0:
                    d.loc[len(d)] = [pd.Timestamp(today), cur]
            except KeyError:
                pass
        d = d.tail(5)
        if len(d) >= 2:
            px[code] = pd.Series(d["收盘价"].values, index=pd.DatetimeIndex(d["日期"]))

        # 昨收持仓量:日 bar 已含今日时取倒数第二根,否则取最后一根
        if len(df) >= 2:
            has_today = df["日期"].iloc[-1].date() >= today
            oi_prev[code] = float(df["持仓量"].iloc[-2] if has_today else df["持仓量"].iloc[-1])

        time.sleep(0.5)  # 防限流
    return px, oi_prev


def sector_curves(px: dict[str, pd.Series]) -> pd.DataFrame:
    """板块累计指数:成员各自归一化(起点=100)后等权平均。"""
    curves: dict[str, pd.Series] = {}
    for sector in SECTORS:
        members = [c for c in px if SECTOR_MAP.get(c) == sector]
        norms = [px[c] / px[c].iloc[0] * 100 for c in members if px[c].iloc[0] > 0]
        if norms:
            # concat(axis=1) 按日期对齐各成员,再逐日等权平均(勿用 DataFrame(list),会把 Series 当行)
            curves[sector] = pd.concat(norms, axis=1).mean(axis=1)  # 等权平均
    return pd.DataFrame(curves)


def plot_panorama(ax, valid: pd.DataFrame) -> None:
    """图 23:全市场主力合约今日涨跌幅全景横条图。"""
    d = valid.sort_values("涨跌幅(%)").reset_index(drop=True)
    colors = [UP_COLOR if v >= 0 else DOWN_COLOR for v in d["涨跌幅(%)"]]
    ax.barh(d.index, d["涨跌幅(%)"], color=colors, height=0.72)
    ax.set_yticks(d.index)
    ax.set_yticklabels(d["品种名"], fontsize=8)
    ax.axvline(0, color="#888888", linewidth=0.8)
    ax.set_xlabel("涨跌幅 (%)(最新价/昨收盘-1)")
    ax.set_ylabel("品种(主力连续)")
    ax.margins(x=0.16)
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    for i, v in zip(d.index, d["涨跌幅(%)"]):
        ax.text(v + (0.06 if v >= 0 else -0.06) * d["涨跌幅(%)"].abs().max(), i, f"{v:+.2f}",
                va="center", ha="left" if v >= 0 else "right", fontsize=6.5)
    ax.legend(handles=[Patch(color=UP_COLOR, label="上涨"), Patch(color=DOWN_COLOR, label="下跌")],
              loc="lower right", fontsize=9)


def plot_sector_avg(ax, valid: pd.DataFrame) -> None:
    """图 24:六大板块平均涨跌幅柱状图(叠加涨跌家数与全市场均值)。"""
    rows = []
    for sec in SECTORS:
        d = valid[valid["板块"] == sec]["涨跌幅(%)"].dropna()
        if len(d):
            rows.append({"板块": sec, "均值": d.mean(),
                         "涨": int((d > 0).sum()), "跌": int((d < 0).sum())})
    rd = pd.DataFrame(rows)
    colors = [UP_COLOR if v >= 0 else DOWN_COLOR for v in rd["均值"]]
    bars = ax.bar(rd["板块"], rd["均值"], color=colors, width=0.55)
    for b, r in zip(bars, rd.itertuples()):
        ax.text(b.get_x() + b.get_width() / 2, r.均值,
                f"{r.均值:+.2f}%\n涨{r.涨}/跌{r.跌}",
                ha="center", va="bottom" if r.均值 >= 0 else "top", fontsize=10)
    m = valid["涨跌幅(%)"].mean()
    ax.axhline(m, color=BLUE, linestyle="--", linewidth=1.2, label=f"全市场均值 {m:+.2f}%")
    ax.axhline(0, color="#888888", linewidth=0.8)
    ax.margins(y=0.22)  # 给柱端两行注释留出空间,避免与轴标签重叠
    ax.set_ylabel("板块平均涨跌幅 (%)(品种算术平均)")
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.legend(fontsize=10)
    ax.legend(handles=[Patch(color=UP_COLOR, label="板块均线上涨"),
                       Patch(color=DOWN_COLOR, label="板块均线下跌"),
                       plt.Line2D([], [], color=BLUE, linestyle="--", label=f"全市场均值 {m:+.2f}%")],
              fontsize=9, loc="lower right")


def plot_sector_curves(ax, curves: pd.DataFrame, today: dt.date) -> None:
    """图 25:近 5 个交易日板块累计表现折线图。"""
    for sec in curves.columns:
        s = curves[sec].dropna()
        ax.plot(s.index, s.values, color=SECTOR_COLOR[sec], linewidth=1.8,
                marker="o", markersize=3.5, label=f"{sec} {s.iloc[-1] - 100:+.1f}%")
    ax.axhline(100, color="#888888", linewidth=0.8, linestyle="--")
    ax.set_ylabel("板块累计表现(起点=100,成员等权)")
    ax.set_xlabel("交易日")
    ax.grid(linestyle="--", alpha=0.35)
    ax.legend(fontsize=9, loc="best")
    ax.tick_params(axis="x", rotation=20, labelsize=8)


def plot_oi_change(ax, snapshot: pd.DataFrame, oi_prev: dict[str, float]) -> pd.DataFrame:
    """图 26:持仓量日增减 TOP10(增仓 TOP5 + 减仓 TOP5)。"""
    snap_idx = snapshot.set_index("品种")
    rows = []
    for code, prev in oi_prev.items():
        if not prev or prev <= 0 or code not in snap_idx.index:
            continue
        cur = float(snap_idx.loc[code, "持仓量"])
        if pd.isna(cur):
            continue
        rows.append({"品种": snap_idx.loc[code, "品种名"], "板块": SECTOR_MAP.get(code, "-"),
                     "增减": cur - prev, "增减幅": (cur - prev) / prev * 100})
    rd = pd.DataFrame(rows)
    if rd.empty:
        return rd
    top = pd.concat([rd.nlargest(5, "增减"), rd.nsmallest(5, "增减")]).sort_values("增减")
    colors = [UP_COLOR if v >= 0 else DOWN_COLOR for v in top["增减"]]
    ax.barh(top["品种"], top["增减"], color=colors, height=0.6)
    ax.axvline(0, color="#888888", linewidth=0.8)
    ax.set_xlabel("持仓量日增减(手,今日实时持仓-昨收持仓)")
    ax.set_ylabel("品种(主力连续)")
    ax.margins(x=0.22)
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    for y, (v, p) in enumerate(zip(top["增减"], top["增减幅"])):
        ax.text(v + (0.03 if v >= 0 else -0.03) * top["增减"].abs().max(), y,
                f"{v:+,.0f}手({p:+.1f}%)", va="center",
                ha="left" if v >= 0 else "right", fontsize=9)
    ax.legend(handles=[Patch(color=UP_COLOR, label="增仓"), Patch(color=DOWN_COLOR, label="减仓")],
              loc="lower right", fontsize=9)
    return rd.sort_values("增减", key=lambda s: s.abs(), ascending=False)


def main() -> None:
    today = dt.date.today()

    # 1) 当日快照(含 CSV 落盘);涨跌幅按昨收盘口径,昨收盘缺失的品种涨跌幅为空
    snapshot = build_snapshot(today)
    valid = snapshot[(snapshot["最新价"] > 0) & (snapshot["昨收盘"] > 0)].copy()
    stale = valid[valid["行情日期"] != f"{today:%Y-%m-%d}"]
    if len(stale):
        print(f"  [剔除] 行情日期非今日的品种: {', '.join(stale['品种名'])}")
    valid = valid[valid["行情日期"] == f"{today:%Y-%m-%d}"].copy()
    valid["板块"] = valid["品种"].map(SECTOR_MAP)
    unmapped = sorted(set(valid.loc[valid["板块"].isna(), "品种"]))
    if unmapped:
        print(f"  [提示] 未纳入六大板块的品种: {', '.join(unmapped)}")

    # 2) 主流活跃品种日线(图 11/12 共用)
    px, oi_prev = build_liquid_series(snapshot, today)
    curves = sector_curves(px)

    # 3) 出图
    fig, ax = plt.subplots(figsize=(13, max(10, 0.22 * len(valid))))
    plot_panorama(ax, valid)
    fig.suptitle(f"商品期货主力合约今日涨跌幅全景({today})　来源:OMMQ",
                 fontsize=16, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    out9 = report_image_path(23, "sector")
    fig.savefig(out9, dpi=150, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 6.5))
    plot_sector_avg(ax, valid)
    fig.suptitle(f"六大板块平均涨跌幅(主力合约)({today})　来源:OMMQ",
                 fontsize=16, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out10 = report_image_path(24, "sector_avg")
    fig.savefig(out10, dpi=150, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 7))
    plot_sector_curves(ax, curves, today)
    fig.suptitle(f"六大板块近 5 个交易日累计表现({today})　来源:OMMQ",
                 fontsize=16, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out11 = report_image_path(25, "sector_5d")
    fig.savefig(out11, dpi=150, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 6.5))
    oi_rank = plot_oi_change(ax, snapshot, oi_prev)
    fig.suptitle(f"主力合约持仓量日增减 TOP10(增仓 TOP5 + 减仓 TOP5)({today})　来源:OMMQ",
                 fontsize=16, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out12 = report_image_path(26, "oi_change")
    fig.savefig(out12, dpi=150, bbox_inches="tight")
    plt.close(fig)

    for out in (out9, out10, out11, out12):
        print(f"图表已保存: {out}")

    # 4) 控制台摘要(供报告引用)
    print("\n[板块平均涨跌幅]")
    for sec in SECTORS:
        d = valid[valid["板块"] == sec]["涨跌幅(%)"].dropna()
        if len(d):
            print(f"  {sec:10s} 均值 {d.mean():+.2f}%  涨{(d > 0).sum()}/跌{(d < 0).sum()}"
                  f"/平{(d == 0).sum()}(共 {len(d)})")
    mkt = valid["涨跌幅(%)"].dropna()
    print(f"  {'全市场':10s} 均值 {mkt.mean():+.2f}%  涨{(mkt > 0).sum()}/跌{(mkt < 0).sum()}"
          f"/平{(mkt == 0).sum()}(共 {len(mkt)})")
    if not curves.empty:
        print("\n[板块 5 日累计(归一化=100)]")
        for sec in curves.columns:
            print(f"  {sec:10s} {curves[sec].iloc[-1] - 100:+.2f}%")
    if oi_rank is not None and len(oi_rank):
        print("\n[持仓量日增减 TOP10(按绝对值)]")
        print(oi_rank.head(10).to_string(index=False,
              float_format=lambda v: f"{v:,.1f}"))


if __name__ == "__main__":
    main()
