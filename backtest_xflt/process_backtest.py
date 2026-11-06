# -*- coding: utf-8 -*-
"""细分龙头(XFLT)等权指数回测 —— 阶段2:等权合成、收益与最大回撤、绘图"""
import json, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.abspath(__file__))
R_RED, G_GREEN, B_BLUE, Y_YELLOW, GRAY = "#F36", "#0C9", "#99F", "#FC3", "#999999"

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

BT_START = "20211028"      # 近5年首个交易日
TRADING_DAYS = 244

# ---------- 读数 ----------
cal = json.load(open(os.path.join(BASE, "calendar.json")))
df = pd.read_csv(os.path.join(BASE, "quotes_long.csv"), dtype={"code": str, "date": str})
wide = df.pivot_table(index="date", columns="code", values="close", aggfunc="last").sort_index()
wide = wide[~wide.index.duplicated(keep="last")]
wide = wide.reindex(cal).ffill()   # 对齐日历;停牌沿用前值→当日收益0(上市前/退市后保持NaN)
print(f"[close矩阵] 交易日 {wide.shape[0]}, 成分股 {wide.shape[1]}", flush=True)

# ---------- 等权·每日再平衡 ----------
ret = wide / wide.shift(1) - 1
ret_bt = ret.loc[ret.index >= BT_START]
valid_cnt = ret_bt.notna().sum(axis=1)          # 每日有效成分股数
port_ret = ret_bt.mask(valid_cnt < 100).mean(axis=1).dropna()
anchor = [d for d in cal if d < port_ret.index[0]][-1]   # 净值锚:回测起点前一交易日
print(f"[板块收益] 起始 {port_ret.index[0]}, 有效成分股中位数 {int(valid_cnt.median())}", flush=True)

# ---------- 基准:沪深300 ----------
hs = json.load(open(os.path.join(BASE, "hs300.json")))
hs_close = pd.Series(hs["Close"], index=hs["Date"], dtype=float).sort_index()
hs_ret = hs_close.pct_change().loc[hs_ret_idx := [d for d in hs_close.index if d >= port_ret.index[0] and d in port_ret.index]]

# ---------- 统计 ----------
def nav_stats(r):
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

p_nav, p_dd, p_st = nav_stats(port_ret)
b_nav, b_dd, b_st = nav_stats(hs_ret)
p_nav_ser, b_nav_ser = p_nav, b_nav
print(f"[区间] {p_nav.index[0]} ~ {p_nav.index[-1]} | 板块 {len(p_nav)}天 基准 {len(b_nav)}天", flush=True)

def fmt(st):
    d = {}
    for k, v in st.items():
        if isinstance(v, float) and ("收益" in k or "回撤" in k and isinstance(v, float)):
            d[k] = f"{v*100:.2f}%" if abs(v) < 5 else round(v, 4)
        elif isinstance(v, float):
            d[k] = round(v, 4)
        else:
            d[k] = v
    return d
print("细分龙头:", json.dumps(fmt(p_st), ensure_ascii=False), flush=True)
print("沪深300 :", json.dumps(fmt(b_st), ensure_ascii=False), flush=True)

# 相对净值
idx = p_nav.index.intersection(b_nav.index)
rel = (p_nav.loc[idx] / b_nav.loc[idx])

# 年度收益
def yearly(nv):
    nr = nv.pct_change().dropna()
    y = pd.to_datetime(pd.Series(nr.index), format="%Y%m%d").dt.year.values
    return pd.Series(nr.values, index=y).groupby(level=0).apply(lambda s: (1 + s).prod() - 1)
py, by = yearly(p_nav), yearly(b_nav)

# ---------- 图1:净值 + 相对净值 + 最大回撤附图 ----------
fig, (ax1, axm, ax2) = plt.subplots(3, 1, figsize=(12.5, 9.2), sharex=True,
                                    gridspec_kw={"height_ratios": [2.4, 1.0, 1.3]}, dpi=150)
x = pd.to_datetime(pd.Series(p_nav.index), format="%Y%m%d")
xb = pd.to_datetime(pd.Series(b_nav.index), format="%Y%m%d")
ax1.plot(x, p_nav.values, color=R_RED, lw=1.8, label=f"细分龙头等权指数(不含分红再投, {wide.shape[1]}只)  终值 {p_nav.iloc[-1]:.2f}")
ax1.plot(xb, b_nav.values, color=B_BLUE, lw=1.5, label=f"沪深300  终值 {b_nav.iloc[-1]:.2f}")
ax1.axhline(1.0, color=GRAY, lw=0.8, ls="--")
ax1.set_title(f"细分龙头(自定义板块 XFLT)近5年等权指数回测   {p_nav.index[0]} 至 {p_nav.index[-1]}(起点净值=1)", fontsize=13)
ax1.set_ylabel("净值(起点=1)")
ax1.legend(loc="upper left", frameon=False, fontsize=9)
ax1.grid(alpha=0.25)

xm = pd.to_datetime(pd.Series(rel.index), format="%Y%m%d")
axm.plot(xm, rel.values, color=Y_YELLOW, lw=1.6, label="相对净值(细分龙头 / 沪深300)")
axm.axhline(1.0, color=GRAY, lw=0.8, ls="--")
axm.set_ylabel("相对净值")
axm.fill_between(xm, rel.values, 1.0, where=rel.values >= 1.0, color=R_RED, alpha=0.25)
axm.fill_between(xm, rel.values, 1.0, where=rel.values < 1.0, color=G_GREEN, alpha=0.35)
axm.legend(loc="upper left", frameon=False, fontsize=9)
axm.grid(alpha=0.25)

ax2.fill_between(x, p_dd.values * 100, 0, color=G_GREEN, alpha=0.5, label="细分龙头回撤率")
ax2.plot(x, p_dd.values * 100, color=G_GREEN, lw=1.0)
ax2.plot(xb, b_dd.values * 100, color=B_BLUE, lw=1.2, label="沪深300回撤率")
ax2.set_title(f"最大回撤率附图  深度:{abs(dd_min:=p_dd.min())*100:.1f}%({p_st['最大回撤起点']}~{p_st['最大回撤谷底']})")
ax2.set_ylabel("回撤率 %(相对峰值)")
ax2.set_xlabel("日期")
ax2.legend(loc="lower right", frameon=False, fontsize=9)
ax2.grid(alpha=0.25)
fig.text(0.99, 0.005, "数据来源:通达信 tqcenter | 等·每日再平衡 | 前复权 | 24K-Claw", ha="right", fontsize=8, color=GRAY)
fig.tight_layout()
fig.savefig(os.path.join(BASE, "fig1_nav_drawdown.png"), bbox_inches="tight")
plt.close(fig)
print("[图1] 已保存", flush=True)

# ---------- 图2:年度收益对比 ----------
fig2, ax = plt.subplots(figsize=(9.5, 4.8), dpi=150)
yy = sorted(set(py.index) | set(by.index))
w = 0.38
ax.bar([y - w / 2 for y in yy], [py.get(y, 0) * 100 for y in yy], width=w, color=R_RED, label="细分龙头(等权)")
ax.bar([y + w / 2 for y in yy], [by.get(y, 0) * 100 for y in yy], width=w, color=B_BLUE, label="沪深300")
for y in yy:
    pv, bv = py.get(y, 0) * 100, by.get(y, 0) * 100
    ax.text(y - w / 2, pv + (1 if pv >= 0 else -3.2), f"{pv:.1f}", ha="center", fontsize=8, color=R_RED)
    ax.text(y + w / 2, bv + (1 if bv >= 0 else -3.2), f"{bv:.1f}", ha="center", fontsize=8, color=B_BLUE)
ax.axhline(0, color=GRAY, lw=0.8)
ax.set_title("细分龙头 vs 沪深300 年度收益(%,2026为年初至今)")
ax.set_ylabel("年度收益 %")
ax.set_xlabel("年份")
ax.set_xticks(yy)
ax.legend(frameon=False)
ax.grid(alpha=0.25, axis="y")
fig2.text(0.99, 0.005, "数据来源:通达信 tqcenter | 24K-Claw", ha="right", fontsize=8, color=GRAY)
fig2.tight_layout()
fig2.savefig(os.path.join(BASE, "fig2_yearly.png"), bbox_inches="tight")
plt.close(fig2)
print("[图2] 已保存", flush=True)

# ---------- 导出 ----------
out = {"板块": "细分龙头(XFLT)", "方式": "等权·每日再平衡", "复权": "前复权",
       "成分股数": int(wide.shape[1]), "回测起点": p_nav.index[0], "回测终点": p_nav.index[-1],
       "每个交易日有效成分股中位数": int(valid_cnt.median()),
       "细分龙头": {k: (v if not isinstance(v, float) else float(v)) for k, v in p_st.items()},
       "沪深300": {k: (v if not isinstance(v, float) else float(v)) for k, v in b_st.items()},
       "年度收益_细分龙头": {str(k): float(v) for k, v in py.items()},
       "年度收益_沪深300": {str(k): float(v) for k, v in by.items()}}
json.dump(out, open(os.path.join(BASE, "result_stats.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# 净值与回撤序列导出(CSV,便于复查)
seq = pd.DataFrame({"日期": p_nav.index,
                    "细分龙头净值": p_nav.values,
                    "细分龙头回撤率%": (p_dd.reindex(p_nav.index).values * 100).round(2)})
seq.to_csv(os.path.join(BASE, "nav_drawdown_series.csv"), index=False, encoding="utf-8-sig")
print("[完成] 统计与曲线序列已保存", flush=True)
