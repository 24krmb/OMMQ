# peer_dupond.py

遵循约翰·内夫低PE价值投资理念的交易策略;

三合一脚本(选股+回测+持仓监控)· 全A股 · 标准版Neff筛选 · 三种卖出规则 · CSV+控制台输出 · 完整容错。

## 使用方法
```powershell
python neff_value_strategy.py screen     # Neff选股(输出候选+建议仓位)
python neff_value_strategy.py backtest   # 5年回测(首次约20-40分钟,之后走缓存)
python neff_value_strategy.py template   # 生成持仓模板 → 填好后再 monitor
python neff_value_strategy.py monitor    # 检查止损/止盈/恶化/轮换信号
```

## 下一步建议:

① 先跑 screen 看当前候选；

② 把顶部参数区的 TOTAL_CAPITAL 改成你的实际资金；

③ 回测时注意幸存者偏差声明。