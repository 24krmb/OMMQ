"""本地日线行情缓存:data/daily/ 按证券代码分文件(parquet)。
设计目标(README 目录约定):行情只拉一次,后续分析/回测直接读本地缓存,
脚本只做增量补齐,不做全量重复拉取。
用法(项目 .venv):
    .venv/bin/python quant/fetch_daily.py                      # 更新上证指数(默认)
    .venv/bin/python quant/fetch_daily.py --code sz399001      # 更新深证成指
    .venv/bin/python quant/fetch_daily.py --code sh600519      # 更新个股(不复权)
    .venv/bin/python quant/fetch_daily.py --code sh600519 --adjust hfq
    .venv/bin/python quant/fetch_daily.py --code sh000001 --refresh   # 忽略缓存全量重拉
指数字段:date / open / high / low / close / volume;
个股额外含 amount(成交额)与 qfq/hfq 复权可选。
文件命名:data/daily/{code}.parquet;个股复权序列为 {code}_{adjust}.parquet。
"""
from __future__ import annotations
import argparse
import time
from pathlib import Path
import akshare as ak
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "daily"
BASE_COLS = ["date", "open", "high", "low", "close", "volume"]
# ---------------------------------------------------------------------------
# 数据拉取
# ---------------------------------------------------------------------------
def fetch_index(symbol: str) -> pd.DataFrame:
    """拉取指数全历史日线。symbol 形如 sh000001 / sz399001。"""
    df = ak.stock_zh_index_daily(symbol=symbol)
    df = df[BASE_COLS]
    df["amount"] = float("nan")
    return df
def fetch_stock(symbol: str, adjust: str) -> pd.DataFrame:
    """拉取个股全历史日线。symbol 形如 sh600519 / sz000001。"""
    kwargs: dict = {"adjust": adjust} if adjust and adjust != "none" else {}
    df = ak.stock_zh_a_daily(symbol=symbol, **kwargs)
    if "amount" not in df.columns:
        df["amount"] = float("nan")
    cols = BASE_COLS + ["amount"]
    return df[cols]
# ---------------------------------------------------------------------------
# 合并落盘
# ---------------------------------------------------------------------------
def merge_history(existing: pd.DataFrame | None, new: pd.DataFrame) -> pd.DataFrame:
    """按日期合并:同一天以新拉取的数据为准(覆盖修正),保证有序去重。"""
    if existing is None or existing.empty:
        return new
    df = pd.concat([existing, new], ignore_index=True)
    df = df.sort_values("date").drop_duplicates(subset="date", keep="last")
    return df.reset_index(drop=True)
def update(code: str, adjust: str = "none", refresh: bool = False) -> Path:
    """更新单只证券的日线缓存,返回 parquet 文件路径。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # 指数:sh000/sh899/sh950 与 sz399 前缀;sz000 开头是个股(如 sz000001 平安银行)
    is_index = (code.startswith("sh") and code[2:5] in ("000", "899", "950")
                or code.startswith("sz") and code[2:5] == "399")
    name = code if (is_index or adjust in ("none", "")) else f"{code}_{adjust}"

    path = DATA_DIR / f"{name}.parquet"
    existing: pd.DataFrame | None = None
    if path.exists() and not refresh:
        existing = pd.read_parquet(path)
        print(f"  本地缓存 {len(existing)} 行(截至 {existing['date'].max().date()}),增量补齐…")
    elif path.exists():
        print("  --refresh:忽略本地缓存,全量重拉…")

    t0 = time.time()
    df = fetch_index(code) if is_index else fetch_stock(code, adjust)
    df["date"] = pd.to_datetime(df["date"])
    for col in ("open", "high", "low", "close", "volume", "amount"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    df = df.sort_values("date").drop_duplicates(subset="date", keep="last").reset_index(drop=True)

    merged = merge_history(existing, df)
    added = len(merged) if existing is None else len(merged) - len(existing)
    merged.to_parquet(path, index=False)
    print(f"  完成 {code} -> {path.relative_to(ROOT)}  共 {len(merged)} 行"
          f"(新增 {max(added, 0)},截至 {merged['date'].max().date()})"
          f"  耗时 {time.time() - t0:.1f}s")
    return path
def main() -> None:
    parser = argparse.ArgumentParser(description="拉取/增量更新日线行情缓存(data/daily/*.parquet)")
    parser.add_argument("--code", default="sh000001",
                        help="证券代码:指数 sh000001/sz399001,个股 sh600519/sz000001;默认上证指数")
    parser.add_argument("--adjust", default="none", choices=["none", "qfq", "hfq"],
                        help="个股复权类型,默认不复权(指数忽略)")
    parser.add_argument("--refresh", action="store_true", help="忽略本地缓存,全量重拉")
    args = parser.parse_args()
    update(args.code, args.adjust, args.refresh)
if __name__ == "__main__":
    main()
