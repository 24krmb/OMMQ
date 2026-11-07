# -*- coding: utf-8 -*-
"""自定义板块等权指数回测(参数化,合并原 backtest_xflt / backtest_scqlt 两套重复脚本)

流程(与原两阶段脚本一致):
    fetch    经通达信 tqcenter 取交易日历、板块成分、成分股前复权收盘、沪深300基准,
             断点续传写入 backtest/data/<board>/quotes_long.csv
    process  等权·每日再平衡合成净值,计算收益/回撤统计并出图,
             产物写入 backtest/output/<board>/
    all      依次执行 fetch + process

用法(需本机通达信客户端已启动,建议在项目根目录执行):
    .\\.venv\\Scripts\\python.exe backtest/equal_weight_backtest.py all --board xflt
    .\\.venv\\Scripts\\python.exe backtest/equal_weight_backtest.py all --board scqlt
    .\\.venv\\Scripts\\python.exe backtest/equal_weight_backtest.py fetch --board xflt --years 3
    .\\.venv\\Scripts\\python.exe backtest/equal_weight_backtest.py process --board xflt --end 20261028

成分股来源(按优先级):
    1. --codes-file 指定的 JSON(字符串列表);
    2. 通达信自定义板块(tq.get_stock_list_in_sector),成功后缓存到 backtest/data/<board>/;
    3. 上次缓存的 backtest/data/<board>/<board>_codes.json。

口径(与原版一致):
    - 个股:前复权收盘价;
    - 组合:等权、每日再平衡;单日有效成分股 < --min-valid(默认 100)视为数据不足,该日剔除;
    - 基准:沪深300(000300.SH);
    - 按"当前"板块成分回溯,存在幸存者偏差;不计交易成本;结果仅供研究,不构成投资建议。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

BACKTEST_DIR = os.path.dirname(os.path.abspath(__file__))

BOARD_NAMES = {"xflt": "细分龙头", "scqlt": "稀缺龙头"}
BOARD_BLOCKS = {"xflt": "XFLT", "scqlt": "XQLT"}   # 数据目录键 -> 通达信自定义板块代码
BENCH_CODE, BENCH_NAME = "000300.SH", "沪深300"
TRADING_DAYS = 244
R_RED, G_GREEN, B_BLUE, Y_YELLOW, GRAY = "#F36", "#0C9", "#99F", "#FC3", "#999999"

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans SC", "PingFang SC"]
plt.rcParams["axes.unicode_minus"] = False


# --------------------------------------------------------------------------- 通用
def board_paths(board: str) -> tuple[str, str]:
    """返回 (数据目录 backtest/data/<board>/, 产物目录 backtest/output/<board>/)。"""
    data_dir = os.path.join(BACKTEST_DIR, "data", board)
    out_dir = os.path.join(BACKTEST_DIR, "output", board)
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    return data_dir, out_dir


def norm_date(x) -> str:
    """任意日期表达 -> 'YYYYMMDD' 字符串。"""
    if isinstance(x, (date, datetime)):
        return f"{x:%Y%m%d}"
    s = str(x).strip()[:10].replace("-", "").replace("/", "")
    return s[:8]


def load_tq():
    """引导通达信 tqcenter 模块(与 strategies/stock/sector_equal_weight_curve.py 同一方式)。"""
    for root in (r"C:\new_tdxqh", r"C:\new_tdx", r"D:\new_tdx", r"E:\new_tdx"):
        p = os.path.join(root, "PYPlugins", "user")
        if os.path.exists(os.path.join(p, "tqcenter.py")):
            sys.path.insert(0, p)
            break
    else:
        raise FileNotFoundError(
            "未找到通达信 PYPlugins/user/tqcenter.py,请检查通达信安装目录或用 --codes-file 指定成分股。")
    from tqcenter import tq
    tq.initialize(os.path.join(p, "tqcenter.py"))   # 连接路径须为已存在的文件
    return tq


def resolve_dates(args) -> tuple[str, str, list[str], list[str]]:
    """计算 (cal_start, bt_start, cal, cal_after_bt)。bt_start = end 前推 N 年的首个交易日。"""
    end = norm_date(args.end or date.today())
    end_dt = datetime.strptime(end, "%Y%m%d").date()
    bt_dt = end_dt - relativedelta(years=args.years)
    cal_start = (bt_dt - timedelta(days=10)).strftime("%Y%m%d")
    tq = load_tq()
    raw = tq.get_trading_calendar(market="SH", start_time=cal_start, end_time=end)
    cal = sorted({norm_date(d) for d in raw})
    if not cal:
        raise RuntimeError("交易日历为空,请确认通达信客户端已启动并登录。")
    after = [d for d in cal if d >= bt_dt.strftime("%Y%m%d")]
    if not after:
        raise RuntimeError(f"回测起点 {bt_dt:%Y%m%d} 之后无交易日,请检查 --years/--end。")
    return cal_start, after[0], cal, after


# --------------------------------------------------------------------------- fetch
def get_members(tq, args, data_dir: str) -> list[str]:
    """成分股清单:--codes-file > 通达信板块 > 本地缓存。"""
    cache_path = os.path.join(data_dir, f"{args.board}_codes.json")
    if args.codes_file:
        with open(args.codes_file, encoding="utf-8") as f:
            codes = json.load(f)
        print(f"[成分股] 来自 {args.codes_file},共 {len(codes)} 只", flush=True)
    else:
        block = BOARD_BLOCKS.get(args.board, args.board.upper())
        try:
            raw = tq.get_stock_list_in_sector(block, block_type=1, list_type=1)
            codes = [x["Code"] for x in raw if isinstance(x, dict) and x.get("Code")]
            if not codes:
                known = ", ".join(f"{s.get('Code')}({s.get('Name')})" for s in tq.get_user_sector())
                raise RuntimeError(f"板块 {block} 无成分股;可用自定义板块:{known}")
        except Exception as exc:
            if os.path.exists(cache_path) and not args.refresh:
                with open(cache_path, encoding="utf-8") as f:
                    codes = json.load(f)
                print(f"[成分股] 板块读取失败({exc}),回退缓存 {len(codes)} 只", flush=True)
            else:
                raise RuntimeError(f"读取板块 {block} 成分失败:{exc}") from exc
    codes = list(dict.fromkeys(codes))
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(codes, f, ensure_ascii=False)
    print(f"[成分股] 共 {len(codes)} 只(已缓存 {os.path.relpath(cache_path, BACKTEST_DIR)})", flush=True)
    return codes


def fetch_close(tq, codes: list[str], start: str, end: str, batch: int) -> tuple[pd.DataFrame, list[str]]:
    """批量拉取前复权收盘,返回 (日期YYYYMMDD×代码 DataFrame, 失败代码清单)。"""
    frames, failed = [], []
    total, t0 = len(codes), time.time()
    for i in range(0, total, batch):
        part = codes[i:i + batch]
        df = None
        for attempt in range(3):
            try:
                data = tq.get_market_data(
                    field_list=["Close"], stock_list=part, period="1d",
                    start_time=start, end_time=end, count=-1,
                    dividend_type="front", fill_data=False)
                df = data.get("Close")
                if df is not None and not df.empty:
                    break
            except Exception as exc:  # 网络/接口抖动,重试
                if attempt == 2:
                    print(f"  [警告] 批次 {i}-{i + len(part)} 失败: {exc}", flush=True)
            time.sleep(0.5)
        if df is None or df.empty:
            failed.extend(part)
        else:
            df.index = [norm_date(d) for d in df.index]
            frames.append(df.astype(float))
            failed.extend([c for c in part if c not in set(df.columns)])
        print(f"  [拉取] {min(i + batch, total)}/{total}  ({time.time() - t0:.0f}s)", flush=True)
    if not frames:
        raise RuntimeError("全部行情拉取失败,请检查通达信客户端与数据下载状态。")
    close = pd.concat(frames, axis=1).sort_index()
    close = close.loc[:, ~close.columns.duplicated()]
    close.index.name = "date"
    return close, failed


def cmd_fetch(args) -> None:
    tq = load_tq()
    data_dir, _ = board_paths(args.board)
    cal_start, bt_start, cal, _after = resolve_dates(args)
    end = norm_date(args.end or date.today())
    print(f"[日历] {len(cal)} 个交易日 {cal[0]}~{cal[-1]},回测起点 {bt_start}", flush=True)
    with open(os.path.join(data_dir, "calendar.json"), "w", encoding="utf-8") as f:
        json.dump(cal, f)

    codes = get_members(tq, args, data_dir)

    csv_path = os.path.join(data_dir, "quotes_long.csv")
    err_path = os.path.join(data_dir, "fetch_errors.json")
    if args.refresh and os.path.exists(csv_path):
        os.remove(csv_path)
        print("[refresh] 已删除旧 quotes_long.csv,全量重拉", flush=True)

    # 断点续传:已在 CSV 中的股票跳过
    done: set[str] = set()
    if os.path.exists(csv_path):
        with open(csv_path, encoding="utf-8") as f:
            f.readline()
            for line in f:
                done.add(line.split(",", 1)[0])
    todo = [c for c in codes if c not in done]
    print(f"[续传] 已完成 {len(done)} 只, 待取 {len(todo)} 只", flush=True)

    t0 = time.time()
    errors: list[dict] = []
    if todo:
        with open(csv_path, "a" if done else "w", encoding="utf-8") as f:
            if not done:
                f.write("code,date,close\n")
            close, failed = fetch_close(tq, todo, cal_start, end, args.batch)
            for code in close.columns:
                s = close[code].dropna()
                if s.empty:
                    errors.append({"code": code, "error": "empty"})
                    continue
                f.write("\n".join(f"{code},{d},{c:.6g}" for d, c in s.items()) + "\n")
            f.flush()
            for code in failed:
                errors.append({"code": code, "error": "not_returned"})
    else:
        print("[续传] 成分股数据已完整,跳过批量拉取", flush=True)

    # 基准:沪深300(存在则跳过)
    hs_path = os.path.join(data_dir, "hs300.json")
    if not os.path.exists(hs_path) or args.refresh:
        hs, _failed = fetch_close(tq, [BENCH_CODE], cal_start, end, batch=1)
        col = BENCH_CODE if BENCH_CODE in hs.columns else hs.columns[0]
        s = hs[col].dropna()
        with open(hs_path, "w", encoding="utf-8") as fp:
            json.dump({"Date": list(s.index), "Close": [float(v) for v in s.values]}, fp)
        print(f"[基准] {BENCH_NAME} {len(s)} 个交易日", flush=True)

    with open(err_path, "w", encoding="utf-8") as f:
        json.dump(errors, f, ensure_ascii=False)
    print(f"[完成] 回测起点 {bt_start},缺失/异常 {len(errors)} 个,总耗时 {time.time() - t0:.0f}s", flush=True)
    print("[下一步] 运行 process 阶段合成净值并出图", flush=True)


# --------------------------------------------------------------------------- process
def nav_stats(r: pd.Series, anchor: str):
    """净值、回撤序列与统计(与原版同一口径)。"""
    nav = (1 + r).cumprod()
    nav = pd.concat([pd.Series([1.0], index=[anchor]), nav])
    total_days = len(nav) - 1
    ann = nav.iloc[-1] ** (TRADING_DAYS / total_days) - 1
    vol = r.std() * np.sqrt(TRADING_DAYS)
    sharpe = (ann - 0.0) / vol if vol > 0 else np.nan      # 无风险利率按0近似
    peak = nav.cummax()
    dd = nav / peak - 1
    mdd_i = dd.idxmin()
    peak_i = nav.loc[:mdd_i].idxmax()
    rec = dd.loc[mdd_i:]
    rec_i = rec[rec >= -1e-9].index
    rec_i = rec_i[0] if len(rec_i) else None
    return nav.drop(nav.index.intersection([anchor])), dd.iloc[1:], {
        "累计收益": nav.iloc[-1] - 1, "年化收益": ann, "年化波动率": vol, "夏普比率": sharpe,
        "最大回撤": dd.min(), "最大回撤起点": peak_i, "最大回撤谷底": mdd_i,
        "最大回撤恢复日": rec_i if rec_i else "未恢复", "Calmar": (ann / abs(dd.min())) if dd.min() < 0 else np.nan,
        "当前回撤": dd.iloc[-1], "交易日数": total_days}


def fmt_pct(st: dict) -> dict:
    d = {}
    for k, v in st.items():
        if isinstance(v, float) and ("收益" in k or "回撤" in k):
            d[k] = f"{v * 100:.2f}%"
        elif isinstance(v, float):
            d[k] = round(v, 4)
        else:
            d[k] = v
    return d


def yearly(nv: pd.Series) -> pd.Series:
    nr = nv.pct_change().dropna()
    y = pd.to_datetime(pd.Series(nr.index), format="%Y%m%d").dt.year.values
    return pd.Series(nr.values, index=y).groupby(level=0).apply(lambda s: (1 + s).prod() - 1)


def cmd_process(args) -> None:
    name = args.name or BOARD_NAMES.get(args.board, args.board)
    data_dir, out_dir = board_paths(args.board)

    cal_path = os.path.join(data_dir, "calendar.json")
    csv_path = os.path.join(data_dir, "quotes_long.csv")
    hs_path = os.path.join(data_dir, "hs300.json")
    for p in (cal_path, csv_path, hs_path):
        if not os.path.exists(p):
            raise SystemExit(f"缺少 {os.path.relpath(p, BACKTEST_DIR)},请先运行 fetch 阶段。")

    cal = json.load(open(cal_path))
    end = norm_date(args.end or cal[-1])
    bt_dt = datetime.strptime(end, "%Y%m%d").date() - relativedelta(years=args.years)
    after = [d for d in cal if d >= bt_dt.strftime("%Y%m%d")]
    if not after:
        raise SystemExit(f"回测起点 {bt_dt:%Y%m%d} 之后无交易日,请检查 --years/--end。")
    bt_start = after[0]
    df = pd.read_csv(csv_path, dtype={"code": str, "date": str})
    wide = df.pivot_table(index="date", columns="code", values="close", aggfunc="last").sort_index()
    wide = wide[~wide.index.duplicated(keep="last")]
    wide = wide.reindex(cal).ffill()   # 对齐日历;停牌沿用前值→当日收益0(上市前/退市后保持NaN)
    print(f"[close矩阵] 交易日 {wide.shape[0]}, 成分股 {wide.shape[1]}", flush=True)

    # 等权·每日再平衡
    ret = wide / wide.shift(1) - 1
    ret_bt = ret.loc[ret.index >= bt_start]
    valid_cnt = ret_bt.notna().sum(axis=1)          # 每日有效成分股数
    port_ret = ret_bt.mask(valid_cnt < args.min_valid).mean(axis=1).dropna()
    anchor = [d for d in cal if d < port_ret.index[0]][-1]   # 净值锚:回测起点前一交易日
    print(f"[板块收益] 起始 {port_ret.index[0]}, 有效成分股中位数 {int(valid_cnt.median())}", flush=True)

    # 基准:沪深300
    hs = json.load(open(hs_path))
    hs_close = pd.Series(hs["Close"], index=hs["Date"], dtype=float).sort_index()
    hs_idx = [d for d in hs_close.index if d >= port_ret.index[0] and d in port_ret.index]
    hs_ret = hs_close.pct_change().loc[hs_idx]

    p_nav, p_dd, p_st = nav_stats(port_ret, anchor)
    b_nav, b_dd, b_st = nav_stats(hs_ret, anchor)
    print(f"[区间] {p_nav.index[0]} ~ {p_nav.index[-1]} | 板块 {len(p_nav)}天 基准 {len(b_nav)}天", flush=True)
    print(f"{name}:", json.dumps(fmt_pct(p_st), ensure_ascii=False), flush=True)
    print(f"{BENCH_NAME} :", json.dumps(fmt_pct(b_st), ensure_ascii=False), flush=True)

    # 相对净值
    idx = p_nav.index.intersection(b_nav.index)
    rel = p_nav.loc[idx] / b_nav.loc[idx]

    py, by = yearly(p_nav), yearly(b_nav)

    # 图1:净值 + 相对净值 + 最大回撤附图
    fig, (ax1, axm, ax2) = plt.subplots(3, 1, figsize=(12.5, 9.2), sharex=True,
                                        gridspec_kw={"height_ratios": [2.4, 1.0, 1.3]}, dpi=150)
    x = pd.to_datetime(pd.Series(p_nav.index), format="%Y%m%d")
    xb = pd.to_datetime(pd.Series(b_nav.index), format="%Y%m%d")
    ax1.plot(x, p_nav.values, color=R_RED, lw=1.8,
             label=f"{name}等权指数(前复权, {wide.shape[1]}只)  终值 {p_nav.iloc[-1]:.2f}")
    ax1.plot(xb, b_nav.values, color=B_BLUE, lw=1.5, label=f"{BENCH_NAME}  终值 {b_nav.iloc[-1]:.2f}")
    ax1.axhline(1.0, color=GRAY, lw=0.8, ls="--")
    ax1.set_title(f"{name}(自定义板块 {args.board.upper()})近{args.years:g}年等权指数回测   "
                  f"{p_nav.index[0]} 至 {p_nav.index[-1]}(起点净值=1)", fontsize=13)
    ax1.set_ylabel("净值(起点=1)")
    ax1.legend(loc="upper left", frameon=False, fontsize=9)
    ax1.grid(alpha=0.25)

    xm = pd.to_datetime(pd.Series(rel.index), format="%Y%m%d")
    axm.plot(xm, rel.values, color=Y_YELLOW, lw=1.6, label=f"相对净值({name} / {BENCH_NAME})")
    axm.axhline(1.0, color=GRAY, lw=0.8, ls="--")
    axm.set_ylabel("相对净值")
    axm.fill_between(xm, rel.values, 1.0, where=rel.values >= 1.0, color=R_RED, alpha=0.25)
    axm.fill_between(xm, rel.values, 1.0, where=rel.values < 1.0, color=G_GREEN, alpha=0.35)
    axm.legend(loc="upper left", frameon=False, fontsize=9)
    axm.grid(alpha=0.25)

    ax2.fill_between(x, p_dd.values * 100, 0, color=G_GREEN, alpha=0.5, label=f"{name}回撤率")
    ax2.plot(x, p_dd.values * 100, color=G_GREEN, lw=1.0)
    ax2.plot(xb, b_dd.values * 100, color=B_BLUE, lw=1.2, label=f"{BENCH_NAME}回撤率")
    ax2.set_title(f"最大回撤率附图  深度:{abs(p_dd.min()) * 100:.1f}%"
                  f"({p_st['最大回撤起点']}~{p_st['最大回撤谷底']})")
    ax2.set_ylabel("回撤率 %(相对峰值)")
    ax2.set_xlabel("日期")
    ax2.legend(loc="lower right", frameon=False, fontsize=9)
    ax2.grid(alpha=0.25)
    fig.text(0.99, 0.005, "数据来源:通达信 tqcenter | 等权·每日再平衡 | 前复权 | 24K-Claw",
             ha="right", fontsize=8, color=GRAY)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "fig1_nav_drawdown.png"), bbox_inches="tight")
    plt.close(fig)
    print("[图1] 已保存", flush=True)

    # 图2:年度收益对比
    fig2, ax = plt.subplots(figsize=(9.5, 4.8), dpi=150)
    yy = sorted(set(py.index) | set(by.index))
    w = 0.38
    ax.bar([y - w / 2 for y in yy], [py.get(y, 0) * 100 for y in yy], width=w, color=R_RED,
           label=f"{name}(等权)")
    ax.bar([y + w / 2 for y in yy], [by.get(y, 0) * 100 for y in yy], width=w, color=B_BLUE,
           label=BENCH_NAME)
    for y in yy:
        pv, bv = py.get(y, 0) * 100, by.get(y, 0) * 100
        ax.text(y - w / 2, pv + (1 if pv >= 0 else -3.2), f"{pv:.1f}", ha="center", fontsize=8, color=R_RED)
        ax.text(y + w / 2, bv + (1 if bv >= 0 else -3.2), f"{bv:.1f}", ha="center", fontsize=8, color=B_BLUE)
    ax.axhline(0, color=GRAY, lw=0.8)
    ax.set_title(f"{name} vs {BENCH_NAME} 年度收益(%,{yy[-1]}为年初至今)")
    ax.set_ylabel("年度收益 %")
    ax.set_xlabel("年份")
    ax.set_xticks(yy)
    ax.legend(frameon=False)
    ax.grid(alpha=0.25, axis="y")
    fig2.text(0.99, 0.005, "数据来源:通达信 tqcenter | 24K-Claw", ha="right", fontsize=8, color=GRAY)
    fig2.tight_layout()
    fig2.savefig(os.path.join(out_dir, "fig2_yearly.png"), bbox_inches="tight")
    plt.close(fig2)
    print("[图2] 已保存", flush=True)

    # 导出统计与序列
    out = {"板块": f"{name}({args.board.upper()})", "方式": "等权·每日再平衡", "复权": "前复权",
           "成分股数": int(wide.shape[1]), "回测起点": p_nav.index[0], "回测终点": p_nav.index[-1],
           "每个交易日有效成分股中位数": int(valid_cnt.median()),
           "板块统计": {k: (v if not isinstance(v, float) else float(v)) for k, v in p_st.items()},
           BENCH_NAME: {k: (v if not isinstance(v, float) else float(v)) for k, v in b_st.items()},
           "年度收益_板块": {str(k): float(v) for k, v in py.items()},
           "年度收益_沪深300": {str(k): float(v) for k, v in by.items()}}
    with open(os.path.join(out_dir, "result_stats.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    seq = pd.DataFrame({"日期": p_nav.index,
                        "板块净值": p_nav.values,
                        "板块回撤率%": (p_dd.reindex(p_nav.index).values * 100).round(2)})
    seq.to_csv(os.path.join(out_dir, "nav_drawdown_series.csv"), index=False, encoding="utf-8-sig")
    print("[完成] 统计与曲线序列已保存", flush=True)


# --------------------------------------------------------------------------- 入口
def main() -> None:
    parser = argparse.ArgumentParser(description="自定义板块等权指数回测(通达信数据,参数化)")
    parser.add_argument("stage", nargs="?", default="all", choices=["fetch", "process", "all"],
                        help="执行阶段:fetch 取数 / process 合成出图 / all 全流程(默认)")
    parser.add_argument("--board", default="xflt", help="板块代码,默认 xflt(如 scqlt)")
    parser.add_argument("--name", default="", help="板块中文名,默认按内置表(xflt=细分龙头, scqlt=稀缺龙头)")
    parser.add_argument("--years", type=float, default=5.0, help="回溯年数,默认 5")
    parser.add_argument("--end", default="", help="结束日 YYYYMMDD,默认今天")
    parser.add_argument("--batch", type=int, default=12, help="单次请求股票数,默认 12")
    parser.add_argument("--min-valid", type=int, default=100, help="单日最少有效成分股,默认 100")
    parser.add_argument("--codes-file", default="", help="成分股 JSON 文件(字符串列表),优先于通达信板块")
    parser.add_argument("--refresh", action="store_true", help="fetch 忽略续传缓存全量重拉")
    args = parser.parse_args()

    if args.stage in ("fetch", "all"):
        cmd_fetch(args)
    if args.stage in ("process", "all"):
        cmd_process(args)


if __name__ == "__main__":
    main()
