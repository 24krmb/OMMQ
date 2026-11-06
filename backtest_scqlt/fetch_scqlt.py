# -*- coding: utf-8 -*-
"""细分龙头(XFLT)自定义板块等权指数回测 —— 阶段1:批量拉取成分股近5年日线前复权收盘价"""
import json, os, sys, time, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
TMP = r"C:\Users\Administrator\AppData\Local\Temp\opencode"
URL = "http://127.0.0.1:17709/"
START, END = "20211020", "20261028"   # 起点提前数日用于计算首个回测日收益
BATCH = 12
MAXK = 16000                            # 单次响应K线上限保护

def req(method, params, timeout=120):
    payload = {"id": 1, "method": method, "params": params}
    r = urllib.request.Request(URL, data=json.dumps(payload).encode(),
                               headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(r, timeout=timeout).read().decode())

# ---- 交易日历 ----
cal_path = os.path.join(BASE, "calendar.json")
if not os.path.exists(cal_path):
    d = req("get_trading_calendar", {"market": "SH", "start_time": START, "end_time": END})
    dates = d["result"]["Date"]
    json.dump(dates, open(cal_path, "w"))
    print(f"[日历] {len(dates)} 个交易日 {dates[0]}~{dates[-1]}", flush=True)

# ---- 成分股 ----
codes = json.load(open(os.path.join(TMP, "scqlt_codes.json"), encoding="utf-8"))
n = len(codes)
print(f"[成分股] 共 {n} 只", flush=True)

csv_path = os.path.join(BASE, "quotes_long.csv")
err_path = os.path.join(BASE, "fetch_errors.json")
errors = []
t0 = time.time()

# 断点续传:已在 CSV 中的股票跳过
done = set()
if os.path.exists(csv_path):
    with open(csv_path, encoding="utf-8") as f:
        f.readline()
        for line in f:
            done.add(line.split(",", 1)[0])
todo = [c for c in codes if c not in done]
print(f"[续传] 已完成 {len(done)} 只, 待取 {len(todo)} 只", flush=True)

with open(csv_path, "a" if done else "w", encoding="utf-8") as csv:
    if not done:
        csv.write("code,date,close\n")
    for bi in range(0, len(todo), BATCH):
        batch = todo[bi:bi + BATCH]
        l2 = f"{bi + len(batch):04d}"
        try:
            resp = req("get_market_data", {
                "stock_list": batch, "period": "1d", "start_time": START, "end_time": END,
                "count": -1, "dividend_type": "front", "field_list": ["Date", "Close"],
                "fill_data": False})
            val = resp.get("result", {}).get("Value") or {}
        except Exception as e:
            errors.append({"batch_start": bi, "error": str(e)})
            print(f"[批 {l2}] 请求失败: {e}", flush=True)
            continue
        got = 0
        for code, v in val.items():
            if v.get("ErrorId") not in (0, "0", None):
                errors.append({"code": code, "error": str(v.get("ErrorId"))}); continue
            if v.get("KlinePaged") and v.get("Date") is None:
                errors.append({"code": code, "error": "paged-incomplete"}); continue
            dates, closes = v.get("Date"), v.get("Close")
            if not dates or not closes:
                errors.append({"code": code, "error": "empty"}); continue
            rows = [f"{code},{d_},{c}" for d_, c in zip(dates, closes)]
            csv.write("\n".join(rows) + "\n")
            got += 1
        csv.flush()
        miss = [c for c in batch if c not in val]
        for c in miss:
            errors.append({"code": c, "error": "not_returned"})
        print(f"[批 {l2}/{len(todo):04d}] 成功 {got} 只 缺失 {len(miss)}, 用时 {time.time()-t0:.0f}s", flush=True)

json.dump(errors, open(err_path, "w"), ensure_ascii=False)
print(f"[完成] 缺失/异常 {len(errors)} 个, 总耗时 {time.time()-t0:.0f}s", flush=True)
