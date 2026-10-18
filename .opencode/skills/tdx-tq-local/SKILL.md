---
name: tdx-tq-local
display_name: 通达信TQ-Local
version: 1.0.12
description: TdxQuant是由通达信软件提供的证券行情分析和量化投研平台。本Skill使用本地通达信客户端的HTTP服务直接调用tqcenter接口, 不再生成Python文件。
---

# Tdx Quant Local Skill

> 本文档改写自 tqcenter.py 接口说明, 当前调用方式为向本机 HTTP 服务发送 JSON-RPC 请求
> 地址: `http://127.0.0.1:17709/`

本 Skill 的执行方式已经从“生成 Python 文件并运行 tqcenter.py”改为“按 tqcenter 接口名构造 JSON-RPC 请求并发送到 HTTP 服务”。

---

## 执行前检查流程

### 第0步：检查 TdxW.exe 是否运行

检查进程列表中是否有 `TdxW.exe`：用户的通达信安装目录是：`C:\new_tdxqh\TdxW.exe`

```bash
tasklist 2>/dev/null | grep -i "TdxW"
```

- 如果 `TdxW.exe` 未运行 → 提示用户先启动通达信客户端并登录
- 如果 `TdxW.exe` 已在运行 → 进入第四步

### 第1步：验证 HTTP 服务连通性

向 `http://127.0.0.1:17709/` 发送测试请求确认 HTTP 服务可用：

```bash
curl -s --connect-timeout 3 -X POST "http://127.0.0.1:17709/" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{"id":1,"method":"get_match_stkinfo","params":{"key_word":"茅台"}}'
```

- 如果返回正常 JSON-RPC 响应 → 可以开始执行用户请求
- 如果连接失败 → 提示用户确认通达信客户端已完全启动并登录后进入到主界面

---

## 核心规则

1. **执行前必须完成上述两步检查流程（第零步检查 + 第1步验证HTTP服务连通性），任意一步未通过则不得继续。**
2. 不要生成 Python 策略文件执行 tqcenter 指令。
3. 不要导入 `tqcenter.py`, 不要调用 `tq.initialize()` 或 `tq.close()`。
4. 所有接口都通过 HTTP POST 发送到 `http://127.0.0.1:17709/`。
5. JSON-RPC 请求格式固定为:

```json
{
  "id": 1,
  "method": "接口名",
  "params": {
    "参数名": "参数值"
  }
}
```

6. `method` 对应 tqcenter 原接口名, 例如 `get_market_data`, `get_stock_list`, `stock_account`。
7. `params` 对应原 tqcenter 接口入参, 不需要额外包一层 `tq.`。
8. 请求体必须是标准 JSON: 字段和值之间使用 `:`, 字符串使用双引号, 不要使用 Python 字典的单引号或 `=`。
9. 返回结果是 JSON-RPC 响应, 正常结果在 `result` 字段中, 错误信息在 `error` 字段中。
10. 交易类接口需要 `account_id` 时, 默认传 `0`; 只有当用户明确指定账号和账号类型时, 才先调用 `stock_account` 获取返回的 `account_id`, 再把该 `account_id` 传入后续查询、下单或撤单接口。
11. 当接口返回结果没有股票名但展示内容需要股票名时, 若已有股票代码, 优先调用 `get_stock_info` 查询股票名, 不要根据记忆或代码前缀猜测名称。
12. 当用户只输入股票名而没有输入股票代码时, 优先调用 `get_match_stkinfo` 以股票名检索股票代码, 再用匹配到的标准代码调用后续接口。
13. 当用户取最新涨幅等，优先调用`get_more_info`中的ZAF等。
14. 需要获取某个数据前，先遍历每个接口的参数和返回字段，确认该数据在哪个接口的哪个字段里；如果不确定数据在哪个接口里，直接询问用户应该调用哪个接口获取该数据，不要盲猜或根据历史记忆调用某个接口。
15. 文档网址为 `help.tdx.com.cn/quant/`

---

## HTTP 请求格式

### PowerShell 示例

```powershell
$body = @{
  id = 1
  method = "get_market_data"
  params = @{
    stock_list = @("688318.SH")
    count = 5
    dividend_type = "none"
    period = "1d"
  }
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Uri "http://127.0.0.1:17709/" -Method Post -ContentType "application/json; charset=utf-8" -Body $body
```

### curl 示例

```bash
curl -s -X POST "http://127.0.0.1:17709/" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{"id":1,"method":"get_market_data","params":{"stock_list":["688318.SH"],"count":5,"dividend_type":"none","period":"1d"}}'
```

### Python 仅作为 HTTP 客户端示例

可以用 Python 发送 HTTP 请求, 但只能作为通用 HTTP 客户端, 不允许导入或运行 `tqcenter.py`。

```python
import json
import urllib.request

payload = {
    "id": 1,
    "method": "get_market_data",
    "params": {
        "stock_list": ["688318.SH"],
        "count": 5,
        "dividend_type": "none",
        "period": "1d",
    },
}
req = urllib.request.Request(
    "http://127.0.0.1:17709/",
    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    headers={"Content-Type": "application/json; charset=utf-8"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=60) as resp:
    result = json.loads(resp.read().decode("utf-8"))
print(result)
```

---

## 典型调用

### 获取 688318.SH 最近五日 K 线

```json
{
  "id": 1,
  "method": "get_market_data",
  "params": {
    "stock_list": ["688318.SH"],
    "count": 5,
    "dividend_type": "none",
    "period": "1d"
  }
}
```

### 获取全部 A 股列表

```json
{
  "id": 1,
  "method": "get_stock_list",
  "params": {
    "market": "5"
  }
}
```

### 获取实时行情快照

```json
{
  "id": 1,
  "method": "get_market_snapshot",
  "params": {
    "stock_code": "688318.SH"
  }
}
```

### 打开688318的个股分析页面 或 打开688318的走势图 或 打开688318

```json
{
  "id": 1,
  "method": "exec_to_tdx",
  "params": {
    "url": "http://www.treeid/breed_1#688318"
  }
}
```

### 打开排行 或 进入排行

```json
{
  "id": 1,
  "method": "exec_to_tdx",
  "params": {
    "url": "http://www.treeid/SORT67"
  }
}
```

### 打开网站(举例为打开百度网站)

```json
{
  "id": 1,
  "method": "exec_to_tdx",
  "params": {
    "url": "http://www.treeid/dlghttp://baidu.com"
  }
}
```

### 打开主力期货合约

|ZXG			|自选股列表|
|ETF			|ETF基金|
|HK				|显示港股|
|QH				|显示期货|
|MAINQH		|显示为主力期货合约|

```json
{
  "id": 1,
  "method": "exec_to_tdx",
  "params": {
    "url": "http://www.treeid/MAINQH"
  }
}
```

### 交易账号选择规则

- 用户未指定账号时, 所有需要 `account_id` 的交易接口默认传 `0`, 不要先调用 `stock_account`。
- 用户明确指定账号和账号类型时, 先调用 `stock_account` 获取账户句柄, 再把响应中的 `result.Value` 作为后续接口的 `account_id`。
- 用户只说“查询持仓”“查询资产”“买入/卖出/撤单”但未指定账号时, 直接使用 `account_id: 0`。
- 用户指定“账号 1190306953, STOCK 账户”这类信息时, 流程是: `stock_account` -> `query_stock_positions`/`query_stock_asset`/`order_stock`/`cancel_order_stock`。

### 股票代码与名称补全规则

- 当用户输入股票名但没有输入股票代码时, 优先调用 `get_match_stkinfo` 检索股票代码, 参数 `key_word` 填用户输入的股票名。
- `get_match_stkinfo` 返回多个候选时, 优先选择名称完全匹配或最接近用户输入的结果; 无法判断唯一结果时, 向用户展示候选并要求确认。
- 获得标准股票代码后, 再用该代码调用 `get_market_data`, `get_stock_info`, `get_market_snapshot` 等后续接口。
- 当返回数据只有股票代码而没有股票名, 且回答、表格或图表需要显示股票名时, 优先使用已有股票代码调用 `get_stock_info` 获取名称。
- 不要根据历史记忆、代码前缀或板块规则猜测股票名; `get_stock_info` 失败或未返回名称时, 保留股票代码并说明名称不可用。
- 多只股票需要补全名称时, 只对最终需要展示的股票代码调用 `get_stock_info`, 避免对全量结果做不必要的逐只查询。

股票名查代码示例:

```json
{
  "id": 1,
  "method": "get_match_stkinfo",
  "params": {
    "key_word": "寒武纪"
  }
}
```

股票代码查名称示例:

```json
{
  "id": 1,
  "method": "get_stock_info",
  "params": {
    "stock_code": "688318.SH"
  }
}
```

### 查询交易账户

```json
{
  "id": 1,
  "method": "stock_account",
  "params": {
    "account": "1190306953",
    "account_type": "STOCK"
  }
}
```

### 查询持仓

```json
{
  "id": 1,
  "method": "query_stock_positions",
  "params": {
    "account_id": 0
  }
}
```

### 下单

```json
{
  "id": 1,
  "method": "order_stock",
  "params": {
    "account_id": 0,
    "stock_code": "688318.SH",
    "order_type": 0,
    "order_volume": 100,
    "price_type": 0,
    "price": 130.0
  }
}
```

---

## 股票代码格式

- 上交所: `600000.SH`
- 深交所: `000001.SZ`
- 北交所: `430047.BJ`
- 港股: `00700.HK`
- 美股: `AAPL.US`
- 新三板: `430047.NQ`
- 股票期权: `10004073.SZO` / `10004073.SHO`
- 国内期货: `代码.CFF` / `.SHF` / `.DCE` / `.CZC` / `.INE` / `.GFE`
- 中证指数: `000300.CSI`
- 开放式基金净值: `代码.OF`

---

## 常用参数

### K 线周期 `period`

| 值 | 含义 |
|----|------|
| `1m` | 1 分钟 |
| `5m` | 5 分钟 |
| `15m` | 15 分钟 |
| `30m` | 30 分钟 |
| `1h` | 60 分钟 |
| `1d` | 日线 |
| `1w` | 周线 |
| `1M` | 月线 |

### 复权类型 `dividend_type`

| 值 | 含义 |
|----|------|
| `none` | 不复权 |
| `front` / `qfq` | 前复权 |
| `back` / `hfq` | 后复权 |

### 时间格式

- 仅日期: `YYYYMMDD`, 例如 `20260605`
- 含时间: `YYYYMMDDHHMMSS`, 例如 `20260605150000`

---

## tqconst 常量与中文别名

HTTP 请求中不直接写 `tqconst.PRICE_SJ` 这类 Python 表达式, 应写入对应整数值。用户用中文描述时, 按下表转换。

### 股票买卖 `order_type`

| 中文别名 | tqconst 名称 | 数值 | 说明 |
|----------|--------------|------|------|
| 买入 | `STOCK_BUY` | 0 | 普通股票买入 |
| 卖出 | `STOCK_SELL` | 1 | 普通股票卖出 |

### 信用交易 `order_type`

| 中文别名 | tqconst 名称 | 数值 | 说明 |
|----------|--------------|------|------|
| 担保品买入 | `CREDIT_BUY` | 0 | 信用账户担保品买入 |
| 担保品卖出 | `CREDIT_SELL` | 1 | 信用账户担保品卖出 |
| 融资买入 | `CREDIT_FIN_BUY` | 69 | 融资买入 |
| 融券卖出 | `CREDIT_SLO_SELL` | 70 | 融券卖出 |
| 买券还券 | `CREDIT_COV_BUY` | 71 | 买券还券 |
| 卖券还款 | `CREDIT_STK_REPAY` | 76 | 卖券还款 |

### ETF 交易 `order_type`

| 中文别名 | tqconst 名称 | 数值 | 说明 |
|----------|--------------|------|------|
| 基金申购 | `ETF_PURCHASE` | 45 | ETF 或基金申购 |
| 基金赎回 | `ETF_REDEMPTION` | 46 | ETF 或基金赎回 |

### 期货 `order_type`

| 中文别名 | tqconst 名称 | 数值 | 说明 |
|----------|--------------|------|------|
| 期货开多 | `FUTURE_OPEN_LONG` | 101 | 开多仓 |
| 期货开空 | `FUTURE_OPEN_SHORT` | 102 | 开空仓 |
| 期货平多 | `FUTURE_CLOSE_LONG` | 103 | 平多仓 |
| 期货平空 | `FUTURE_CLOSE_SHORT` | 104 | 平空仓 |

### 期权 `order_type`

| 中文别名 | tqconst 名称 | 数值 | 说明 |
|----------|--------------|------|------|
| 期权开多 | `OPTION_OPEN_LONG` | 201 | 期权开多 |
| 期权开空 | `OPTION_OPEN_SHORT` | 202 | 期权开空 |
| 期权平多 | `OPTION_CLOSE_LONG` | 203 | 期权平多 |
| 期权平空 | `OPTION_CLOSE_SHORT` | 204 | 期权平空 |

### 报价类型 `price_type`

| 中文别名 | tqconst 名称 | 数值 | 说明 |
|----------|--------------|------|------|
| 自填价格 | `PRICE_MY` | 0 | 使用 `price` 参数中的价格 |
| 限价 | `PRICE_MY` | 0 | 与自填价格等价 |
| 市价 | `PRICE_SJ` | 1 | 市价委托 |
| 涨停价 | `PRICE_ZTJ` | 2 | 涨停价 / 笼子上限价 |
| 笼子上限价 | `PRICE_ZTJ` | 2 | 与涨停价等价 |
| 跌停价 | `PRICE_DTJ` | 3 | 跌停价 / 笼子下限价 |
| 笼子下限价 | `PRICE_DTJ` | 3 | 与跌停价等价 |

### 委托状态 `WTSTATUS_*`

| 中文别名 | tqconst 名称 | 数值 | 说明 |
|----------|--------------|------|------|
| 无效单 | `WTSTATUS_NULL` | 0 | 无效委托 |
| 未成交 | `WTSTATUS_NOCJ` | 1 | 未成交 |
| 部分成交 | `WTSTATUS_PARTCJ` | 2 | 部分成交 |
| 全部成交 | `WTSTATUS_ALLCJ` | 3 | 全部成交 |
| 部分撤单 | `WTSTATUS_BCBC` | 4 | 部分撤单 |
| 全部撤单 | `WTSTATUS_ALLCD` | 5 | 全部撤单 |

### 下单示例: 市价买入

用户说“市价买入 688318.SH 100 股”时, `order_type` 写 0, `price_type` 写 1。

```json
{
  "id": 1,
  "method": "order_stock",
  "params": {
    "account_id": 0,
    "stock_code": "688318.SH",
    "order_type": 0,
    "order_volume": 100,
    "price_type": 1,
    "price": 0
  }
}
```

## 接口名映射规则

HTTP 的 `method` 直接使用 tqcenter 原函数名。调用时把原 tqcenter 函数入参放入 `params`。标准 HTTP 客户端也可以通过 `tools/call` 调用同名工具。

### 通用返回结构

- HTTP 正常时返回 JSON-RPC 对象, 成功结果在 `result` 中, 失败结果在 `error` 中。
- TPyth 底层接口通常返回 `result.ErrorId` 和 `result.Value`; `ErrorId` 为 `"0"` 表示成功。
- 下列“返回字段”默认描述 `result.Value` 内部数据; 若底层直接返回数组、字符串或整数, HTTP 仍会包在 `result` 中。
- 用户只输入股票名时先用 `get_match_stkinfo` 查代码; 返回缺股票名但需要展示时再用 `get_stock_info` 补名称。

### 行情与基础数据

#### `get_market_data`: K线/分钟线/历史行情

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| field_list | N | List[str] | 需返回的字段列表；空列表返回所有字段 |
| stock_list | Y | List[str] | 股票代码列表 |
| period | Y | str | K线周期，如 `1m`, `5m`, `15m`, `30m`, `60m`, `1d`, `1w`, `1mon`, `1q`, `1hy`, `1y` |
| start_time | N | str | 开始时间，常用 `YYYYMMDD` 或 `YYYY-MM-DD` |
| end_time | N | str | 结束时间；未传则默认当前时间 |
| count | N | int | `count>0`：取截止 `end_time` 最近 n 条；`count<=0`：使用 `start_time/end_time` 区间 |
| dividend_type | N | str | 复权类型：`none` 不复权、`front`/`qfq` 前复权、`back`/`hfq` 后复权 |
| fill_data | N | bool | 是否向前填充缺失数据，默认 `True` |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| Date | str | 日期 |
| Time | str | 时间，分钟线/分时数据常见 |
| Open | str | 开盘价（元） |
| High | str | 最高价（元） |
| Low | str | 最低价（元） |
| Close | str | 收盘价（元） |
| Volume | str | 成交量（股） |
| Amount | str | 成交额（万元） |
| ForwardFactor | str | 前复权因子，通常仅不复权数据中返回 |

#### `get_market_snapshot`: 实时行情快照

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| stock_code | Y | str | 单只证券代码 |
| field_list | N | List[str] | 指定返回字段；空列表返回所有可用字段 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
|ItemNum	|str	|快照笔数|
|LastClose|str	|前收盘价|
|Open			|str	|开盘价|
|Max			|str	|最高价|
|Min			|str	|最低价|
|Now			|str	|现价|
|Volume		|str	|总手|
|NowVol		|str	|现手|
|Amount		|str	|总成交金额|
|Inside		|str	|内盘 板块指数时为跌停家数|
|Outside	|str	|外盘 板块指数时为涨停家数|
|TickDiff	|str	|笔涨跌|
|InOutFlag|str	|内外盘标志 0:Buy 1:Sell 2:Unknown|
|Jjjz			|str	|基金净值|
||||
|Buyp			|List[str]	|五个买价|
|Buyv			|List[str]	|对应的五个买盘量|
|Sellp			|List[str]	|五个卖价|
|Sellv			|List[str]	|对应的五个卖盘量|
|UpHome			|str	|上涨家数 对于指数有效|
|DownHome		|str	|下跌家数 对于指数有效|
||||
|Before5MinNow		|str	|5分钟前价格|
|Average		|str	|均价|
|XsFlag			|str	|小数位数|
|Zangsu			|str	|涨速|
|ZAFPre3		|str	|3日涨幅|


#### `get_stock_info`: 证券基础信息

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| stock_code | Y | str | 单只证券代码 |
| field_list | N | List[str] | 指定返回字段；空列表返回全部基础信息 |

**返回字段：**

|数据|默认返回|数据类型|数据说明|
|:----- |:-------|:-----|----- |
|Name			|Y	|str	|证券名称|
|Unit			|Y	|str	|交易单位|
|VolBase		|Y	|str	|量比的基量|
|MinPrice		|Y	|str	|最小价格变动|
|XsFlag			|Y	|str	|价格小数位数|
|Fz[8]			|Y	|List[str]	|开收市时间（4段）|
|DelayMin		|Y	|str	|延时分钟数|
|QHVolBaseRate	|Y	|str	|期货期权的每手乘数|
|HKVolBaseRate	|Y	|str	|港股/日股/新加坡股 每手股数|
|BelongHS300	|Y	|str	|是否属于沪深300|
|BelongHasKQZ	|Y	|str	|是否含可转债|
|BelongRZRQ		|Y	|str	|是否是融资融券标的|
|BelongHSGT		|Y	|str	|是否属于沪深股通|
|IsHKGP			|Y	|str	|是否是港股|
|IsQH			|Y	|str	|是否是期货|
|IsQQ			|Y	|str	|是否是期权|
|IsSTGP			|Y	|str	|是否是ST股票|
|IsQuitGP		|Y	|str	|是否是退市整理板股票|
|TodayDRFlag	|Y	|str	|当天是否有除权除息(沪深京)|
|HSStockKind	|Y	|str	|沪深京品种类型 0:指数,1:A股主板,2:北证A股,3:创业板,4:科创板,5:B股,6:债券,7:基金,8:权证,9:其它,10:非沪深京品种|
||||
|ActiveCapital	|Y	|str	|流通股本(万股)|
|J_zgb			|Y	|str	|总股本(万股)|
|J_bg			|Y	|str	|B股(万股)|
|J_hg			|Y	|str	|H股(万股)|
|J_zzc			|Y	|str	|总资产(万元)|
|J_ldzc			|Y	|str	|流动资产(万元)|
|J_gdzc			|Y	|str	|固定资产(万元)|
|J_wxzc			|Y	|str	|无形资产(万元)|
|J_ldfz			|Y	|str	|流动负债(万元)|
|J_cqfz			|Y	|str	|少数股东权益(万元)|
|J_zbgjj		|Y	|str	|资本公积金(万元)|
|J_jzc			|Y	|str	|股东权益/净资产(万元)|
|J_yysy			|Y	|str	|营业收入(万元)|
|J_yycb			|Y	|str	|营业成本(万元)|
|J_yszk			|Y	|str	|应收账款(万元)|
|J_yyly			|Y	|str	|营业利润(万元)|
|J_tzsy			|Y	|str	|投资收益(万元)|
|J_jyxjl		|Y	|str	|经营现金净流量(万元)|
|J_zxjl			|Y	|str	|总现金净流量(万元)|
|J_ch			|Y	|str	|存货(万元)|
|J_lyze			|Y	|str	|利润总额(万元)|
|J_shly			|Y	|str	|税后利润(万元)|
|J_jly			|Y	|str	|净利润(万元)|
|J_wfply		|Y	|str	|未分配利益(万元)|
|J_jyl			|Y	|str	|净资产收益率|
|J_mgwfp		|Y	|str	|每股未分配|
|J_mgsy			|Y	|str	|每股收益（折算为全年）|
|J_mgsy2		|Y	|str	|季报每股收益 (财报中提供的每股收益)|
|J_mggjj		|Y	|str	|每股公积金|
|J_mgjzc		|Y	|str	|每股净资产|
|J_mgjzc2		|Y	|str	|季报每股净资产 (财报中提供的每股收益)|
|J_gdqyb		|Y	|str	|股东权益比|
|J_gdrs			|Y	|str	|股东人数|
|J_HalfYearFlag	|Y	|str	|报告期月份(3,6,9,12)|
|J_start		|Y	|str	|上市日期|
||||
|tdx_dycode		|Y	|str	|通达信地域代码|
|tdx_dyname		|Y	|str	|通达信地域|
|rs_hycode_sim	|Y	|str	|通达信行业代码|
|rs_hyname		|Y	|str	|通达信行业|
|blockzscode	|Y	|str	|所属的行业板块指数代码|
|underly_setcode|Y	|str	|标的市场代码(比如：当前ETF跟踪的指数市场)|
|underly_code	|Y	|str	|标的代码(比如：当前ETF跟踪的指数代码)|

#### `get_match_stkinfo`: 按名称/拼音/代码模糊查证券

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| key_word | Y | str | 查询关键字；用户输入股票名时把股票名填入此参数 |

**返回字段：**

|名称|类型|数值|说明|
|:----- |:-------|:-----|----- |
|Code		|Y	|str	|证券代码|
|Name		|Y	|str	|证券名称|

#### `get_stock_list`: 获取系统证券列表

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| market | N | str | 市场或系统分类；常用 `5` 获取全部 A 股 |
| list_type | N | int | `0` 只返回代码；`1` 返回代码和名称 |

- list_type = 0 只返回代码，list_type = 1 返回代码和名称

```
默认为全部A股, market为：
    0:自选股 1:持仓股
    5:所有A股 6:上证指数成份股 7:上证主板 8:深证主板 9:重点指数
    10:所有板块指数 11:缺省行业板块 12:概念板块 13:风格板块 14:地区板块 15:缺省行业分类+概念板块 16:研究行业一级 17:研究行业二级 18:研究行业三级
    21:含H股 22:含可转债 23:沪深300 24:中证500 25:中证1000 26:国证2000 27:中证2000 28:中证A500
    30:REITs 31:ETF基金 32:可转债 33:LOF基金 34:所有可交易基金 35:所有沪深基金 36:T+0基金
    49:金融类企业 50:沪深A股 51:创业板 52:科创板 53:北交所
    101:国内期货 102:港股 103:美股
	91:ETF追踪的指数
	92:国内期货主力合约
```

**返回字段：**
| 字段 | 类型 | 说明 |
|------|------|------|
| Code | str | 成分股代码 |
| Name | str | 成分股名称, list_type = 1时返回|

#### `get_sector_list`: 获取板块列表

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| list_type | N | int | 板块分类类型 |

- list_type = 0 只返回代码，list_type = 1 返回代码和名称

**返回字段：**
| 字段 | 类型 | 说明 |
|------|------|------|
| Code | str | 成分股代码 |
| Name | str | 成分股名称, list_type = 1时返回|

#### `get_user_sector`: 获取用户自定义板块

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| 无 | N | - | 不需要参数 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| Code | str | 用户板块代码 |
| Name | str | 用户板块名称 |

#### `get_stock_list_in_sector`: 获取板块成分股

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| block_code | Y | str | 板块代码或板块名称 |
| block_type | N | int | 板块类型，默认 `0` |
| list_type | N | int | `0` 返回代码；`1` 返回代码和名称 |

- 获取A股成份股时支持板块名称或板块代码两种方式传入
- block_type=0 表示传入板块指数代码或板块指数名称（默认）
- block_type=1 表示传入自定义板块简称 需要是客户端中预先定义好自定义板块的简称 如果是ZXG表示是自选股；TJG表示是临时条件股
- list_type = 0 只返回代码，list_type = 1 返回代码和名称

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| Code | str | 成分股代码 |
| Name | str | 成分股名称, list_type = 1时返回|

#### `get_trading_calendar`: 获取交易日历

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| market | Y | str | 市场代码 |
| start_time | Y | str | 开始日期 |
| end_time | Y | str | 结束日期 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| Value | List[str] | 交易日期列表|

#### `get_trading_dates`: 获取交易日期

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| market | Y | str | 市场代码 |
| start_time | Y | str | 开始日期 |
| end_time | Y | str | 结束日期 |
| count | N | int | 返回数量|

- 需要先在客户端下载上证指数（999999）的盘后数据 目前仅支持A股
- count > 0时，限制返回从结束日期往前最近的count个在限定时间段中的交易日

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| Value | List[str] | 交易日期列表|

#### `get_relation`: 获取证券所属板块/关联品种

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| stock_code | Y | str | 证券代码 |

**返回字段：**

|数据|默认返回|数据类型|数据说明|
|:----- |:-------|:-----|----- |
|BlockCode	|Y	|str	|板块代码|
|BlockName	|Y	|str	|板块名称|
|BlockType	|Y	|str	|板块类型|
|GPNume		|Y	|str	|成份股数量|

#### `get_pricevol`: 获取价量分布/量价数据

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| stock_list | Y | List[str] | 股票代码列表 |

**返回字段：**

|名称|类型|数值|说明|
|:----- |:-------|:-----|----- |
|LastClose		|Y	|str	|前收盘价|
|Now			|Y	|str	|现价|
|Volume			|Y	|str	|成交量|

#### `get_divid_factors`: 获取除权除息数据

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| stock_code | Y | str | 股票代码 |
| start_time | N | str | 开始日期 |
| end_time | N | str | 结束日期 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| Date | str | 除权除息日期 |
| Type | str/int | 类型 |
| Bonus | str | 每 10 股分红 |
| AllotPrice | str | 配股价 |
| ShareBonus | str | 送股比例 |
| Allotment | str | 配股比例 |

#### `get_more_info`: 获取更多证券信息

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| stock_code | Y | str | 证券代码 |
| field_list | N | List[str] | 指定返回字段 |

**返回字段：**

|数据|默认返回|数据类型|数据说明|
|:----- |:-------|:-----|----- |
|MainBusiness	|Y	|str	|主营构成|
|SafeValue		|Y	|str	|安全分|
|ShineValue		|Y	|str	|亮点数|
|ShapeValue		|Y	|str	|短期形态+中期形态+长期形态 编号|
||||
|TPFlag			|Y	|str	|停牌标识|
|ZTPrice		|Y	|str	|涨停价|
|DTPrice		|Y	|str	|跌停价|
|HqDate			|Y	|str	|行情日期|
||||
|fHSL			|Y	|str	|换手率|
|fLianB			|Y	|str	|量比|
|Wtb			|Y	|str	|委比|
|Zsz			|Y	|str	|总市值(亿)|
|Ltsz			|Y	|str	|流通市值(亿)|
||||
|vzangsu		|Y	|str	|量涨速|
|Fzhsl			|Y	|str	|分钟换手率|
|FzAmo			|Y	|str	|2分钟金额(万元)|
|VOpenZAF		|Y	|str	|抢筹涨幅|
||||
|ZAF			|Y	|str	|涨幅|
|ZAFYesterday	|Y	|str	|昨日涨幅|
|ZAFPre2D		|Y	|str	|前天涨幅|
|ZAFPre5		|Y	|str	|5日涨幅|
|ZAFPre10		|Y	|str	|10日涨幅|
|ZAFPre20		|Y	|str	|20日涨幅|
|ZAFPre30		|Y	|str	|30日涨幅|
|ZAFPre60		|Y	|str	|60日涨幅|
|ZAFYear		|Y	|str	|年初至今涨幅|
|ZAFPreMyMonth	|Y	|str	|涨幅(本月来)|
|ZAFPreOneYear	|Y	|str	|涨幅(一年来)|
||||
|Zjl			|Y	|str	|主买净额(万元)|
|Zjl_HB			|Y	|str	|主力净流入(万元)|
||||
|TotalBVol		|Y	|str	|总买量|
|TotalSVol		|Y	|str	|总卖量|
|BCancel		|Y	|str	|总撤买量|
|SCancel		|Y	|str	|总撤卖量|
|L2TicNum		|Y	|str	|L2逐笔成交数|
|L2OrderNum		|Y	|str	|L2逐笔委托数|
||||
|FCAmo			|Y	|str	|封单额(万元)|
|FCb			|Y	|str	|封成比|
|OpenAmo		|Y	|str	|开盘金额(万元)(A股和板块指数有效)|
|OpenZTBuy		|Y	|str	|竞价涨停买入金额(万元)|
||||
|OpenAmoPre1	|Y	|str	|昨开盘金额(万元)|
|OpenVolPre1	|Y	|str	|昨开盘量|
|CJJEPre1		|Y	|str	|昨成交额(万元)|
|CJJEPre3		|Y	|str	|3日成交额(万元)|
|FDEPre1		|Y	|str	|昨封单额(万元)|
|FDEPre2		|Y	|str	|前封单额(万元)|
||||
|ZTGPNum		|Y	|str	|板块指数的涨停家数|
|LastStartZT	|Y	|str	|几天|
|LastZTHzNum	|Y	|str	|几板|
|EverZTCount	|Y	|str	|连板天|
|ConZAFDateNum	|Y	|str	|连涨天数|
|YearZTDay		|Y	|str	|年涨停天数|
||||
|MA5Value		|Y	|str	|5日均价|
|HisHigh		|Y	|str	|52周最高|
|HisLow			|Y	|str	|52周最低|
|IPO_Price		|Y	|str	|发行价|
||||
|More_YJL		|Y	|str	|ETF,LOF溢价率|
|BetaValue		|Y	|str	|贝塔系数|
|DynaPE			|Y	|str	|动态市盈率|
|MorePE			|Y	|str	|市盈率(港股:动,其他扩展:静)|
|StaticPE_TTM	|Y	|str	|市盈率(TTM)|
|DYRatio		|Y	|str	|股息率|
|PB_MRQ			|Y	|str	|市净率(MRQ)|
||||
|IsT0Fund		|Y	|str	|是否是T+0基金|
|IsZCZGP		|Y	|str	|是否是注册制A股|
|IsKzz			|Y	|str	|是否是可转债|
|Kzz_HSCode		|Y	|str	|可转债对应的正股代码|
|QHMainYYMM		|Y	|str	|主力合约关联的月份(期货),主力和次主力|
||||
|FreeLtgb		|Y	|str	|自由流通股本(万)|
|Yield			|Y	|str	|应计利息(债券),占款天数(回购)|
|KfEarnMoney	|Y	|str	|扣非净利润(万元)|
|RDInputFee		|Y	|str	|研发费用(万元)|
|CashZJ			|Y	|str	|货币资金(万元)|
|PreReceiveZJ	|Y	|str	|合同负债(万元)|
|OtherQYJzc		|Y	|str	|其它权益工具(万元)|
|StaffNum		|Y	|str	|员工人数|
||||
|RecentGGJYDate		|Y	|str	|最近北上大额交易日|
|RecentHGDate		|Y	|str	|最近回购预案日|
|RecentIncentDate	|Y	|str	|最近股权激励预案日|
|NoticeDate_Recent	|Y	|str	|最近业绩预告日|
|RecentReleaseDate	|Y	|str	|最近解禁日|
|RecentDZDate		|Y	|str	|最近定增日|
|ReportDate			|Y	|str	|最近财报公告日期|
|ZTDate_Recent		|Y	|str	|近2年最近涨停板日期|
|DTDate_Recent		|Y	|str	|近2年最近跌停板日期|
|TopDate_Recent		|Y	|str	|近2年最近龙虎榜日期|
|StopJYDate_Recent	|Y	|str	|最近停牌日期|

#### `get_gb_info`: 获取股本信息

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| stock_code | Y | str | 股票代码 |
| date_list | Y | List[str] | 日期列表，通常为 `YYYYMMDD`，按从小到大排序 |
| count | Y | int | 需要获取的日期数量 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
|Date |double | |日期|
|Zgb |double | |总股本|
|Ltgb |double | |流通股本|

#### `get_gb_info_by_date`: 按日期区间取股本信息

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| stock_code | Y | str | 股票代码 |
| start_date | Y | str | 开始日期 |
| end_date | Y | str | 结束日期 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
|Date |double | |日期|
|Zgb |double | |总股本|
|Ltgb |double | |流通股本|

#### `get_kzz_info`: 获取可转债信息

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| stock_code | N | str | 可转债或正股代码；空表示按底层默认范围返回 |
| field_list | N | List[str] | 指定返回字段 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
|SetCode	|str | 证券市场|
|KZZCode	|str | 可转债代码|
|HSCode	|str | 正股代码|
|ZGPrice	|str | 转股价格|
|CurRate	|str | 当期利率|
|RestScope	|str | 剩余规模(万)|
|PutBack	|str | 回售触发价|
|ForceRedeem	|str | 强赎触发价|
|ZGDate	|str | 转股日|
|EndPrice	|str | 到期价|
|EndDate	|str | 到期日期|
|ZGRate	|str | 转股比率%|
|RealValue	|str | 纯债价值|
|ExpireYield	|str | 到期收益率%|
|KZZScore	|str | 可转债评级|
|HSScore	|str | 主体评级|
|RedeemDate	|str | 赎回登记日期|
|RedeemPrice	|str | 赎回价格|
|PutDate	|str | 回售申报起始日期|
|PutPrice	|str | 回售价格|
|ZGCode	|str | 转股代码|
||||
|AGPrice	|str | 正股当前价格|
|KZZPrice	|str | 可转债当前价格|
|KZZYj	|str | 溢价率|
|ZGValue	|str | 转股价值|

#### `get_ipo_info`: 获取新股/新债申购信息

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| ipo_type | N | int | `0` 新股申购；`1` 新发债；`2` 两者都返回 |
| ipo_date | N | int | `0` 只返回今天；`1` 今天及以后 |

- ipo_type=0 表示获取新股申购信息
- ipo_type=1 表示获取新发债信息
- ipo_type=2 表示获取新股和新发债信息
- ipo_date=0 表示只获取今天信息
- ipo_date=1 表示获取今天及以后信息

**返回字段：**
|数据|默认返回|数据类型|数据说明|
|:----- |:-------|:-----|----- |
|Code	|Y	|str	|证券代码|
|Name	|Y	|str	|证券名称|
|SGDate	|Y	|str	|申购日期|
|SGPrice|Y	|str	|申购价格|
|SGCode	|Y	|str	|申购代码|
|MaxSG	|Y	|str	|申购上限|
|PE_Issue		|Y	|str	|发行市盈率|

#### `get_trackzs_etf_info`: 获取跟踪指数 ETF 信息

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| zs_code | Y | str | 指数代码，如 `000300.CSI` |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
|Code	|str | 证券代码|
|Name	|str | 证券名称|
|NowPrice	|str | 现价|
|PreClose	|str | 昨收|
|IOPV	|str | 净值|
|Zgb	|str | 净额（万份）|
|Sz	|str | 规模（亿元）|

### 刷新、下载与本地交互

#### `refresh_cache`: 刷新行情缓存

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| market | N | str | 市场范围，默认 `AG` |
| force | N | bool | 是否强制刷新；`False` 时可能因间隔不足跳过 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| ErrorId | str | 错误码，`0` 表示成功 |
| Value | str/Object | 刷新结果或状态信息 |

#### `refresh_kline`: 刷新 K 线缓存

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| stock_list | Y | List[str] | 需要刷新的股票代码列表,一次最多一百条 |
| period | Y | str | K 线周期，1d为日线、1m为一分钟线、5m为五分钟线，只支持这三种，其它周期的数据均由这三种数据生成|

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| ErrorId | str | 错误码，`0` 表示成功 |
| Value | str/Object | 刷新结果或状态信息 |

#### `download_file`: 下载/拉取文件类数据

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| stock_code | N | str | down_type=1 时为 A 股代码; down_type=2 时为 ETF 代码; down_type=3,4 时无效 |
| down_time | N | str | down_type=1 时为年份 (`YYYY`); down_type=2 时为日期 (`YYYYMMDD`); down_type=3,4 时无效 |
| down_type | N | int | 下载类型，默认 `1` |

- down_type=1: 下载10大股东数据，`stock_code` 为 A 股代码，`down_time` 为年份（如 `2024`）
  → 文件名: `{HomePath}\PYPlugins\data\holders{Code}_{year}.json`
  （例: `holders600519_2024.json`，含指定年份所有10大股东和流通股东数据）
- down_type=2: 下载ETF申赎清单，`stock_code` 为 ETF 代码，`down_time` 为具体日期（如 `20240617`）
  → 文件名: `{HomePath}\PYPlugins\data\etfpcf{Code}_{date}.json`
  （例: `etfpcf510300_20240617.json`）
- down_type=3: 下载最新舆情信息文件，`stock_code` / `down_time` 均无效
  → 文件名: `{HomePath}\PYPlugins\data\sentiment.json`
- down_type=4: 下载综合信息文件（股票综合信息），`stock_code` / `down_time` 均无效
  → 文件名: `{HomePath}\PYPlugins\data\miscinfo.json`
- `{HomePath}` 为通达信客户端安装目录

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| ErrorId | str | 错误码，`0` 表示成功 |
| Value | str/Object | 下载结果、文件状态或底层返回信息 |

#### 下载后如何找到文件

`download_file` 下载的文件保存在 `{HomePath}\PYPlugins\data\` 目录下，其中 `{HomePath}` 为通达信客户端安装目录。

**查找策略：通过注册表找到所有可能的通达信安装目录，在每个目录的 `PYPlugins\data\` 下查找目标文件，取修改时间最新的那个。**

> 注意：一台机器可能安装了多个通达信版本（如 `new_tdx_64`、`new_tdx_600` 等），注册表可能只记录其中一个。`download_file` 会下载到**当前正在运行**的通达信客户端目录中，因此必须遍历注册表中**所有**已安装的通达信版本，逐个检查。

查找脚本（使用 Python + winreg）：

```python
import winreg
import os

# ========== 根据下载类型设置目标文件名 ==========
# down_type=1: f"holders{stock_code}_{down_time}.json"
# down_type=2: f"etfpcf{stock_code}_{down_time}.json"
# down_type=3: "sentiment.json"
# down_type=4: "miscinfo.json"
target_filename = "sentiment.json"   # ← 替换为实际文件名

# ========== 第一步：从注册表查找所有已安装的通达信版本 ==========
reg_paths = [
    r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\通达信金融终端64',
    r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\通达信专业版',
    r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\通达信金融终端(量化模拟)',
    r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\通达信金融终端(测试)',
]

install_dirs = []
for reg_path in reg_paths:
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
        try:
            loc = winreg.QueryValueEx(key, 'InstallLocation')[0]
            if loc and os.path.exists(loc):
                install_dirs.append(loc)
                print(f"[注册表] {loc}")
        except:
            pass
        try:
            # DisplayIcon 有时也指向安装目录
            icon = winreg.QueryValueEx(key, 'DisplayIcon')[0]
            icondir = os.path.dirname(icon)
            if icondir and os.path.exists(icondir) and icondir not in install_dirs:
                install_dirs.append(icondir)
                print(f"[DisplayIcon] {icondir}")
        except:
            pass
        winreg.CloseKey(key)
    except FileNotFoundError:
        continue

# ========== 第二步：在每个安装目录的 PYPlugins\data\ 下查找目标文件 ==========
found_files = []
for install_dir in install_dirs:
    expected_path = os.path.join(install_dir, 'PYPlugins', 'data', target_filename)
    if os.path.exists(expected_path):
        mtime = os.path.getmtime(expected_path)
        found_files.append((expected_path, mtime))
        print(f"[找到] {expected_path} (mtime={mtime})")
    else:
        print(f"[未找到] {expected_path}")

# ========== 第三步：取修改时间最新的文件 ==========
if found_files:
    found_files.sort(key=lambda x: x[1], reverse=True)
    print(f"\n共找到 {len(found_files)} 个候选：")
    for path, mtime in found_files:
        print(f"  {path}  (修改时间: {mtime})")
    print(f"\n使用最新文件: {found_files[0][0]}")
else:
    # ========== 兜底：注册表未命中，回退到盘符搜索 ==========
    print("注册表未命中，回退到盘符搜索...")
    import glob
    search_roots = [r'C:\', r'D:\', r'E:\', r'F:\']
    fallback = []
    for root in search_roots:
        if not os.path.exists(root):
            continue
        pattern = os.path.join(root, '**', 'PYPlugins', 'data', target_filename)
        fallback.extend(glob.glob(pattern, recursive=True))
    if fallback:
        fallback.sort(key=lambda f: os.path.getmtime(f), reverse=True)
        for f in fallback[:5]:
            print(f"  {f}  (修改时间: {os.path.getmtime(f)})")
        print(f"\n使用最新文件: {fallback[0]}")
    else:
        print("未找到文件。请确认：")
        print("  1. 通达信客户端已安装且正在运行")
        print("  2. download_file(down_type=...) 已返回成功")
```

> **核心原则**：
> - **第一步：注册表找所有通达信安装目录**（用 `InstallLocation` 和 `DisplayIcon` 两个来源，可覆盖多版本安装场景）
> - **第二步：在每个安装目录的 `PYPlugins\data\` 精确路径检查目标文件**（不递归搜索，速度快且准确）
> - **第三步：取修改时间最新的文件**，因为刚下载完的就是最新的
> - **兜底：注册表完全未命中时**，才回退到全盘搜索 `PYPlugins\data\` 路径
> - **展示所有候选文件**，方便确认和排错

#### `send_message`: 向通达信发送文本消息

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| msg_str | Y | str | 消息文本 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| ErrorId | str | 错误码，`0` 表示成功 |
| Value | str/Object | 发送结果 |

#### `send_file`: 向通达信发送文件

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| file_path | Y | str | 本机文件路径 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| ErrorId | str | 错误码，`0` 表示成功 |
| Value | str/Object | 发送结果 |

#### `send_warn`: 发送预警数据

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| stock_list | Y | List[str] | 股票代码列表 |
| time_list | Y | List[str] | 时间列表 |
| price_list | Y | List[str] | 价格列表 |
| close_list | N | List[str] | 收盘价列表 |
| volum_list | N | List[str] | 成交量列表，沿用 tqcenter 参数名 |
| bs_flag_list | N | List[str] | 买卖标志列表 |
| warn_type_list | N | List[str] | 预警类型列表 |
| reason_list | N | List[str] | 预警原因列表 |
| count | Y | int | 记录数量 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| ErrorId | str | 错误码，`0` 表示成功 |
| Value | str/Object | 发送结果 |

#### `send_bt_data`: 发送回测数据

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| stock_code | Y | str | 股票代码 |
| time_list | Y | List[str] | 时间列表 |
| data_list | Y | List[List[str]] | 回测数据二维列表 |
| count | Y | int | 记录数量 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| ErrorId | str | 错误码，`0` 表示成功 |
| Value | str/Object | 发送结果 |

#### `send_user_block`: 写入/发送用户板块

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| block_code | Y | str | 用户板块代码/简称 |
| stock_list | Y | List[str] | 股票代码列表 |
| show | N | bool | 是否在通达信中显示 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| ErrorId | str | 错误码，`0` 表示成功 |
| Value | str/Object | 写入结果 |

#### `exec_to_tdx`: 调用通达信 URL/命令

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| url | Y | str | 通达信可识别的 URL 或命令字符串 |

若是功能串，请以 http://www.treeid 开头
|功能串|说明和示例|
|:----- |:-------|
|inhttp		|内部打开 比如：http://www.treeid/inhttp://.......	|
|dlghttp			|内部对话框打开 比如： http://www.treeid/dlghttp://.......&tdxmyietitle=标题&tdxmyiewidth=500&tdxmyieheight=300&noborder=0|
|localurl		|内部打开(非对话框) 比如：http://www.treeid/localurlc:\pa\tips.html.......|
|dlglocalurl		|内部打开(对话框) 比如：http://www.treeid/dlglocalurlc:\pa\tips.mht.......|
|code_			|进入某只股票(只传入代码)|
|breed_			|到某个品种(可以传入市场和代码,如果不清楚市场,在代码前加-即可进行模糊处理), 比如到财富趋势 http://www.treeid/breed_1#688318 市场：0#为深市 1#为沪市 2#为京市|
|zb_				|指标公式 比如：http://www.treeid/zb_MACD|
|exp_			|专家系统公式|
|padcode_		|进入用户定制版面,后面是版面简称|
|ZXG				|自选股列表|
|ETF				|ETF基金|
|HK				|显示港股|
|QH				|显示期货|
|MAINQH			|显示为主力期货合约|
|SORT67			|排行(67)|

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| ErrorId | str | 错误码，`0` 表示成功 |
| Value | str/Object | 执行结果 |

### 板块管理

#### `create_sector`: 创建自定义板块

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| block_code | Y | str | 板块简称 |
| block_name | Y | str | 板块显示名称 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| ErrorId | str | 错误码，`0` 表示成功 |
| Value | str/Object | 创建结果 |

#### `delete_sector`: 删除自定义板块

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| block_code | Y | str | 板块简称 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| ErrorId | str | 错误码，`0` 表示成功 |
| Value | str/Object | 删除结果 |

#### `rename_sector`: 重命名自定义板块

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| block_code | Y | str | 板块简称 |
| block_name | Y | str | 新板块显示名称 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| ErrorId | str | 错误码，`0` 表示成功 |
| Value | str/Object | 重命名结果 |

#### `clear_sector`: 清空自定义板块

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| block_code | Y | str | 板块简称 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| ErrorId | str | 错误码，`0` 表示成功 |
| Value | str/Object | 清空结果 |

### 专业数据

#### `get_financial_data`: 获取专业财务序列数据

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| stock_list | Y | List[str] | 股票代码列表 |
| field_list | Y | List[str] | 专业财务字段列表 |
| start_time | N | str | 开始日期 |
| end_time | N | str | 结束日期 |
| report_type | N | str |`announce_time`, `tag_time` |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
|announce_time |int | |公告日期|
|tag_time |int | |报告期|
|FN1 |double | |基本每股收益|
|FN2 |double | |扣除非经常性损益每股收益|
|FN3 |double | |每股未分配利润|
|FN4 |double | |每股净资产|
|FN5 |double | |每股资本公积金|
|FN6 |double | |净资产收益率|
|FN7 |double | |每股经营现金流量|
|FN8 |double | |货币资金|
|FN9 |double | |交易性金融资产|
|FN10 |double | |应收票据|
|FN11 |double | |应收账款|
|FN12 |double | |预付款项|
|FN13 |double | |其他应收款|
|FN14 |double | |应收关联公司款|
|FN15 |double | |应收利息|
|FN16 |double | |应收股利|
|FN17 |double | |存货|
|FN18 |double | |其中：消耗性生物资产|
|FN19 |double | |一年内到期的非流动资产|
|FN20 |double | |其他流动资产|
|FN21 |double | |流动资产合计|
|FN22 |double | |可供出售金融资产|
|FN23 |double | |持有至到期投资|
|FN24 |double | |长期应收款|
|FN25 |double | |长期股权投资|
|FN26 |double | |投资性房地产|
|FN27 |double | |固定资产|
|FN28 |double | |在建工程|
|FN29 |double | |工程物资|
|FN30 |double | |固定资产清理|
|FN31 |double | |生产性生物资产|
|FN32 |double | |油气资产|
|FN33 |double | |无形资产|
|FN34 |double | |开发支出|
|FN35 |double | |商誉|
|FN36 |double | |长期待摊费用|
|FN37 |double | |递延所得税资产|
|FN38 |double | |其他非流动资产|
|FN39 |double | |非流动资产合计|
|FN40 |double | |资产总计|
|FN41 |double | |短期借款|
|FN42 |double | |交易性金融负债|
|FN43 |double | |应付票据|
|FN44 |double | |应付账款|
|FN45 |double | |预收款项|
|FN46 |double | |应付职工薪酬|
|FN47 |double | |应交税费|
|FN48 |double | |应付利息|
|FN49 |double | |应付股利|
|FN50 |double | |其他应付款|
|FN51 |double | |应付关联公司款|
|FN52 |double | |一年内到期的非流动负债|
|FN53 |double | |其他流动负债|
|FN54 |double | |流动负债合计|
|FN55 |double | |长期借款|
|FN56 |double | |应付债券|
|FN57 |double | |长期应付款|
|FN58 |double | |专项应付款|
|FN59 |double | |预计负债 （非流动负债）|
|FN60 |double | |递延所得税负债|
|FN61 |double | |其他非流动负债|
|FN62 |double | |非流动负债合计|
|FN63 |double | |负债合计|
|FN64 |double | |实收资本（或股本）|
|FN65 |double | |资本公积|
|FN66 |double | |盈余公积|
|FN67 |double | |减：库存股|
|FN68 |double | |未分配利润|
|FN69 |double | |少数股东权益|
|FN70 |double | |外币报表折算价差|
|FN71 |double | |非正常经营项目收益调整|
|FN72 |double | |所有者权益（或股东权益）合计|
|FN73 |double | |负债和所有者（或股东权益）合计|
|FN98 |double | |销售商品、提供劳务收到的现金|
|FN99 |double | |收到的税费返还|
|FN100 |double | |收到其他与经营活动有关的现金|
|FN101 |double | |经营活动现金流入小计|
|FN102 |double | |购买商品、接受劳务支付的现金|
|FN103 |double | |支付给职工以及为职工支付的现金|
|FN104 |double | |支付的各项税费|
|FN105 |double | |支付其他与经营活动有关的现金|
|FN106 |double | |经营活动现金流出小计|
|FN107 |double | |经营活动产生的现金流量净额|
|FN108 |double | |收回投资收到的现金|
|FN109 |double | |取得投资收益收到的现金|
|FN110 |double | |处置固定资产、无形资产和其他长期资产收回的现金净额|
|FN111 |double | |处置子公司及其他营业单位收到的现金净额|
|FN112 |double | |收到其他与投资活动有关的现金|
|FN113 |double | |投资活动现金流入小计|
|FN114 |double | |购建固定资产、无形资产和其他长期资产支付的现金|
|FN115 |double | |投资支付的现金|
|FN116 |double | |取得子公司及其他营业单位支付的现金净额|
|FN117 |double | |支付其他与投资活动有关的现金|
|FN118 |double | |投资活动现金流出小计|
|FN119 |double | |投资活动产生的现金流量净额|
|FN120 |double | |吸收投资收到的现金|
|FN121 |double | |取得借款收到的现金|
|FN122 |double | |收到其他与筹资活动有关的现金|
|FN123 |double | |筹资活动现金流入小计|
|FN124 |double | |偿还债务支付的现金|
|FN125 |double | |分配股利、利润或偿付利息支付的现金|
|FN126 |double | |支付其他与筹资活动有关的现金|
|FN127 |double | |筹资活动现金流出小计|
|FN128 |double | |筹资活动产生的现金流量净额|
|FN129 |double | |四、汇率变动对现金的影响|
|FN130 |double | |四(2)、其他原因对现金的影响|
|FN131 |double | |五、现金及现金等价物净增加额|
|FN132 |double | |期初现金及现金等价物余额|
|FN133 |double | |期末现金及现金等价物余额|
|FN134 |double | |净利润|
|FN135 |double | |加：资产减值准备|
|FN136 |double | |固定资产折旧、油气资产折耗、生产性生物资产折旧|
|FN137 |double | |无形资产摊销|
|FN138 |double | |长期待摊费用摊销|
|FN139 |double | |处置固定资产、无形资产和其他长期资产的损失|
|FN140 |double | |固定资产报废损失|
|FN141 |double | |公允价值变动损失|
|FN142 |double | |财务费用|
|FN143 |double | |投资损失|
|FN144 |double | |递延所得税资产减少|
|FN145 |double | |递延所得税负债增加|
|FN146 |double | |存货的减少|
|FN147 |double | |经营性应收项目的减少|
|FN148 |double | |经营性应付项目的增加|
|FN149 |double | |其他|
|FN150 |double | |经营活动产生的现金流量净额2|
|FN151 |double | |债务转为资本|
|FN152 |double | |一年内到期的可转换公司债券|
|FN153 |double | |融资租入固定资产|
|FN154 |double | |现金的期末余额|
|FN155 |double | |减：现金的期初余额|
|FN156 |double | |加：现金等价物的期末余额|
|FN157 |double | |减：现金等价物的期初余额|
|FN158 |double | |现金及现金等价物净增加额|
|FN159 |double | |流动比率(非金融类指标)|
|FN160 |double | |速动比率(非金融类指标)|
|FN161 |double | |现金比率(%)(非金融类指标)|
|FN162 |double | |利息保障倍数(非金融类指标)|
|FN163 |double | |非流动负债比率(%)(非金融类指标)|
|FN164 |double | |流动负债比率(%)(非金融类指标)|
|FN166 |double | |有形资产净值债务率(%)|
|FN167 |double | |权益乘数(%)|
|FN168 |double | |股东的权益/负债合计(%)|
|FN169 |double | |有形资产/负债合计(%)|
|FN170 |double | |经营活动产生的现金流量净额/负债合计(%)(非金融类指标)|
|FN171 |double | |EBITDA/负债合计(%)(非金融类指标)|
|FN172 |double | |应收帐款周转率(非金融类指标)|
|FN173 |double | |存货周转率(非金融类指标)|
|FN174 |double | |运营资金周转率(非金融类指标)|
|FN175 |double | |总资产周转率(非金融类指标)|
|FN176 |double | |固定资产周转率(非金融类指标)|
|FN177 |double | |应收帐款周转天数(非金融类指标)|
|FN178 |double | |存货周转天数(非金融类指标)|
|FN179 |double | |流动资产周转率(非金融类指标)|
|FN180 |double | |流动资产周转天数(非金融类指标)|
|FN181 |double | |总资产周转天数(非金融类指标)|
|FN182 |double | |股东权益周转率(非金融类指标)|
|FN183 |double | |营业收入增长率(%)|
|FN184 |double | |净利润增长率(%)|
|FN185 |double | |净资产增长率(%)|
|FN186 |double | |固定资产增长率(%)|
|FN187 |double | |总资产增长率(%)|
|FN188 |double | |投资收益增长率(%)|
|FN189 |double | |营业利润增长率(%)|
|FN190 |double | |扣非每股收益同比(%)|
|FN191 |double | |扣非净利润同比(%)|
|FN192 |double | |暂无|
|FN193 |double | |成本费用利润率(%)|
|FN194 |double | |营业利润率(非金融类指标)|
|FN195 |double | |营业税金率(非金融类指标)|
|FN196 |double | |营业成本率(非金融类指标)|
|FN197 |double | |净资产收益率|
|FN198 |double | |投资收益率|
|FN199 |double | |销售净利率(%)|
|FN200 |double | |总资产净利率|
|FN201 |double | |净利润率(非金融类指标)|
|FN202 |double | |销售毛利率(%)(非金融类指标)|
|FN203 |double | |三费比重(非金融类指标)|
|FN204 |double | |管理费用率(非金融类指标)|
|FN205 |double | |财务费用率(非金融类指标)|
|FN206 |double | |扣除非经常性损益后的净利润|
|FN207 |double | |息税前利润(EBIT)|
|FN208 |double | |息税折旧摊销前利润(EBITDA)|
|FN209 |double | |EBITDA/营业总收入(%)(非金融类指标)|
|FN210 |double | |资产负债率(%)|
|FN211 |double | |流动资产比率(非金融类指标)|
|FN212 |double | |货币资金比率(非金融类指标)|
|FN213 |double | |存货比率(非金融类指标)|
|FN214 |double | |固定资产比率|
|FN215 |double | |负债结构比(非金融类指标)|
|FN216 |double | |归属于母公司股东权益/全部投入资本(%)|
|FN217 |double | |股东的权益/带息债务(%)|
|FN218 |double | |有形资产/净债务(%)|
|FN219 |double | |每股经营性现金流(元)|
|FN220 |double | |营业收入现金含量(%)(非金融类指标)|
|FN221 |double | |经营活动产生的现金流量净额/经营活动净收益(%)|
|FN222 |double | |销售商品提供劳务收到的现金/营业收入(%)|
|FN223 |double | |经营活动产生的现金流量净额/营业收入|
|FN224 |double | |资本支出/折旧和摊销|
|FN225 |double | |每股现金流量净额(元)|
|FN226 |double | |经营净现金比率（短期债务）(非金融类指标)|
|FN227 |double | |经营净现金比率（全部债务）|
|FN228 |double | |经营活动现金净流量与净利润比率|
|FN229 |double | |全部资产现金回收率|
|FN230 |double | |营业收入|
|FN231 |double | |营业利润|
|FN232 |double | |归属于母公司所有者的净利润|
|FN233 |double | |扣除非经常性损益后的净利润|
|FN234 |double | |经营活动产生的现金流量净额|
|FN235 |double | |投资活动产生的现金流量净额|
|FN236 |double | |筹资活动产生的现金流量净额|
|FN237 |double | |现金及现金等价物净增加额|
|FN238 |double | |总股本|
|FN239 |double | |已上市流通A股|
|FN240 |double | |已上市流通B股|
|FN241 |double | |已上市流通H股|
|FN242 |double | |股东人数(户)|
|FN243 |double | |第一大股东的持股数量|
|FN244 |double | |十大流通股东持股数量合计(股)|
|FN245 |double | |十大股东持股数量合计(股)|
|FN246 |double | |机构总量（家）|
|FN247 |double | |机构持股总量(股)|
|FN248 |double | |QFII机构数|
|FN249 |double | |QFII持股量|
|FN250 |double | |券商机构数|
|FN251 |double | |券商持股量|
|FN252 |double | |保险机构数|
|FN253 |double | |保险持股量|
|FN254 |double | |基金机构数|
|FN255 |double | |基金持股量|
|FN256 |double | |社保机构数|
|FN257 |double | |社保持股量|
|FN258 |double | |私募机构数|
|FN259 |double | |私募持股量|
|FN260 |double | |财务公司机构数|
|FN261 |double | |财务公司持股量|
|FN262 |double | |年金机构数|
|FN263 |double | |年金持股量|
|FN264 |double | |十大流通股东持有的流通A股合计(股)[ 注：2019半年报之前，季度报告中，若股东持股除了流通A股、还有流通B股或流通H股，指标264取的是包含流通B股或流通H股的流通股数]|
|FN265 |double | |第一大流通股东持股量(股)|
|FN266 |double | |自由流通股(股)[注：1.自由流通股=已流通A股-持股5%以上股东的流通A股（一致行动人算一起）；2.指标按报告期展示，新股在上市日的下个报告期才有数据]|
|FN267 |double | |受限流通A股(股)|
|FN268 |double | |一般风险准备(金融类)|
|FN269 |double | |其他综合收益(利润表)|
|FN270 |double | |综合收益总额(利润表)|
|FN271 |double | |归属于母公司股东权益(资产负债表)|
|FN272 |double | |银行机构数(家)(机构持股)|
|FN273 |double | |银行持股量(股)(机构持股)|
|FN274 |double | |一般法人机构数(家)(机构持股)|
|FN275 |double | |一般法人持股量(股)(机构持股)|
|FN276 |double | |近一年净利润(元)|
|FN277 |double | |信托机构数(家)(机构持股)|
|FN278 |double | |信托持股量(股)(机构持股)|
|FN279 |double | |特殊法人机构数(家)(机构持股)|
|FN280 |double | |特殊法人持股量(股)(机构持股)|
|FN281 |double | |加权净资产收益率(每股指标)|
|FN282 |double | |扣非每股收益(单季度财务指标)|
|FN283 |double | |最近一年营业收入(万元)|
|FN284 |double | |国家队持股数量（万股)[注：本指标统计包含汇金公司、证金公司、外汇管理局旗下投资平台、国家队基金、国开、养老金以及中科汇通等国家队机构持股数量]|
|FN285 |double | |业绩预告-本期归母净利润同比增幅下限%[注：指标285至294展示未来一个报告期的数据。例，3月31日至6月29日这段时间内展示的是中报的数据；如果最新的财务报告后面有多个报告期的业绩预告/快报，只能展示最新的财务报告后面的一个报告期的业绩预告/快报]|
|FN286 |double | |业绩预告-本期归母净利润同比增幅上限%|
|FN287 |double | |业绩快报-归母净利润|
|FN288 |double | |业绩快报-扣非净利润|
|FN289 |double | |业绩快报-总资产|
|FN290 |double | |业绩快报-净资产|
|FN291 |double | |业绩快报-每股收益|
|FN292 |double | |业绩快报-摊薄净资产收益率|
|FN293 |double | |业绩快报-加权净资产收益率|
|FN294 |double | |业绩快报-每股净资产|
|FN295 |double | |应付票据及应付账款(资产负债表)|
|FN296 |double | |应收票据及应收账款(资产负债表)|
|FN297 |double | |递延收益(资产负债表-非流动负债)|
|FN298 |double | |其他综合收益(资产负债表)|
|FN299 |double | |其他权益工具(资产负债表)|
|FN300 |double | |其他收益(利润表)|
|FN301 |double | |资产处置收益(利润表)|
|FN302 |double | |持续经营净利润(利润表)|
|FN303 |double | |终止经营净利润(利润表)|
|FN304 |double | |研发费用(利润表)|
|FN305 |double | |其中:利息费用(利润表-财务费用)|
|FN306 |double | |其中:利息收入(利润表-财务费用)|
|FN307 |double | |近一年经营活动现金流净额|
|FN308 |double | |近一年归母净利润(万元)|
|FN309 |double | |近一年扣非净利润(万元)|
|FN310 |double | |近一年现金净流量(万元)|
|FN311 |double | |基本每股收益（单季度）|
|FN312 |double | |营业总收入(单季度)(万元)|
|FN313 |double | |业绩预告公告日期 [注：本指标展示未来一个报告期的数据。例,3月31日至6月29日这段时间内展示的是中报的数据；如果最新的财务报告后面有多个报告期的业绩预告/快报，只能展示最新的财务报告后面的一个报告期的业绩预告/快报的数据；公告日期格式为YYMMDD，例：190101代表2019年1月1日]|
|FN314 |double | |财报公告日期 [注：日期格式为YYMMDD,例：190101代表2019年1月1日]|
|FN315 |double | |业绩快报公告日期 [注：本指标展示未来一个报告期的数据。例,3月31日至6月29日这段时间内展示的是中报的数据；如果最新的财务报告后面有多个报告期的业绩预告/快报，只能展示最新的财务报告后面的一个报告期的业绩预告/快报的数据；公告日期格式为YYMMDD，例：190101代表2019年1月1日]|
|FN316 |double | |近一年投资活动现金流净额(万元)|
|FN317 |double | |业绩预告-本期归母净利润下限(万元)[注：指标317至318展示未来一个报告期的数据。例，3月31日至6月29日这段时间内展示的是中报的数据；如果最新的财务报告后面有多个报告期的业绩预告/快报，只能展示最新的财务报告后面的一个报告期的业绩预告/快报]|
|FN318 |double | |业绩预告-本期归母净利润上限(万元)|
|FN319 |double | |营业总收入TTM(万元)|
|FN320 |double | |员工总数(人)|
|FN321 |double | |每股企业自由现金流|
|FN322 |double | |每股股东自由现金流|
|FN323 |double | |近一年营业利润(万元)|
|FN324 |double | |净利润（单季度）(万元)|
|FN325 |double | |北上资金数（家）(机构持股）|
|FN326 |double | |北上资金持股量（股）(机构持股）|
|FN327 |double | |有息负债率|
|FN328 |double | |营业成本（单季度）(万元)|
|FN329 |double | |投入资本回报率（ROIC）(获利能力分析)|
|FN330 |double | |业绩快报-营业收入（本期）|
|FN331 |double | |业绩快报-营业收入（上期）|
|FN332 |double | |业绩快报-营业利润（本期）|
|FN333 |double | |业绩快报-营业利润（上期）|
|FN334 |double | |业绩快报-利润总额（本期）|
|FN335 |double | |业绩快报-利润总额（上期）|
|FN336 |double | |审计意见  [注：0-未审计,1-无保留意见,2-带强调事项段的无保留意见,3-保留意见,4-无法表示意见,5-否定意见及其他]|
|FN337 |double | |股利支付率（%）|
|FN338 |double | |近一年营业成本-非金融类(万元)|
|FN339 |double | |近一年营业成本-金融类(万元)|
|FN340 |double | |业绩预告-本期扣非后净利润下限(万元)|
|FN341 |double | |业绩预告-本期扣非后净利润上限(万元)|
|FN342 |double | |业绩预告-本期扣非后净利润同比增长下限（%）|
|FN343 |double | |业绩预告-本期扣非后净利润同比增长上限（%）|
|FN344 |double | |业绩预告-预告基本每股收益下限(元)|
|FN345 |double | |业绩预告-预告基本每股收益上限(元)|
|FN346 |double | |业绩预告-预告基本每股收益同比增长下限（%）|
|FN347 |double | |业绩预告-预告基本每股收益同比增长上限（%）|
|FN348 |double | |业绩预告-预告扣非后基本每股收益下限(元)|
|FN349 |double | |业绩预告-预告扣非后基本每股收益上限(元)|
|FN350 |double | |业绩预告-预告扣非后基本每股收益同比增长下限（%）|
|FN351 |double | |业绩预告-预告扣非后基本每股收益同比增长上限（%）|
|FN352 |double | |业绩预告-预告营业收入下限(万元)|
|FN353 |double | |业绩预告-预告营业收入上限(万元)|
|FN354 |double | |业绩预告-预告营业收入同比增长下限（%）|
|FN355 |double | |业绩预告-预告营业收入同比增长上限（%）|
|FN356 |double | |业绩预告-预告扣除后营业收入下限(万元)|
|FN357 |double | |业绩预告-预告扣除后营业收入上限(万元)|
|FN358 |double | |主营业务收入(内销)(万元)|
|FN359 |double | |主营业务收入(外销)(万元)|
|FN360 |double | |资管计划机构数(家)|
|FN361 |double | |资管计划持股量(股)|
|FN362 |double | |财务总评分|
|FN401 |double | |专项储备(万元)|
|FN402 |double | |结算备付金(万元)|
|FN403 |double | |拆出资金(万元)|
|FN404 |double | |发放贷款及垫款(万元)(流动资产科目)|
|FN405 |double | |衍生金融资产(万元)|
|FN406 |double | |应收保费(万元)|
|FN407 |double | |应收分保账款(万元)|
|FN408 |double | |应收分保合同准备金(万元)|
|FN409 |double | |买入返售金融资产(万元)|
|FN410 |double | |划分为持有待售的资产(万元)|
|FN411 |double | |发放贷款及垫款(万元)(非流动资产科目)|
|FN412 |double | |向中央银行借款(万元)|
|FN413 |double | |吸收存款及同业存放(万元)|
|FN414 |double | |拆入资金(万元)|
|FN415 |double | |衍生金融负债(万元)|
|FN416 |double | |卖出回购金融资产款(万元)|
|FN417 |double | |应付手续费及佣金(万元)|
|FN418 |double | |应付分保账款(万元)|
|FN419 |double | |保险合同准备金(万元)|
|FN420 |double | |代理买卖证券款(万元)|
|FN421 |double | |代理承销证券款(万元)|
|FN422 |double | |划分为持有待售的负债(万元)|
|FN423 |double | |预计负债(万元) （流动负债）|
|FN424 |double | |递延收益(万元)（流动负债科目，公告此科目的股票较少，大部分公司没有此数据）|
|FN425 |double | |其中:优先股(万元)(非流动负债科目)|
|FN426 |double | |永续债(万元)(非流动负债科目)|
|FN427 |double | |长期应付职工薪酬(万元)|
|FN428 |double | |其中:优先股(万元)(所有者权益科目)|
|FN429 |double | |永续债(万元)(所有者权益科目)|
|FN430 |double | |债权投资(万元)|
|FN431 |double | |其他债权投资(万元)|
|FN432 |double | |其他权益工具投资(万元)|
|FN433 |double | |其他非流动金融资产(万元)|
|FN434 |double | |合同负债(万元)|
|FN435 |double | |合同资产(万元)|
|FN436 |double | |其他资产(万元)|
|FN437 |double | |应收款项融资(万元)|
|FN438 |double | |使用权资产(万元)|
|FN439 |double | |租赁负债(万元)|
|FN440 |double | |发放贷款及垫款(万元)  [注：金融类科目]|
|FN441 |double | |应收款项(万元)  [注：证券类指标]|
|FN442 |double | |存出保证金(万元)  [注：证券类指标]|
|FN443 |double | |现金及存放中央银行款项(万元)  [注：金融类科目]|
|FN444 |double | |贵金属(万元)  [注：金融类科目]|
|FN445 |double | |以公允价值计量且其变动计入当期损益的金融资产(万元)  [注：金融类科目]|
|FN446 |double | |代理业务资产(万元)  [注：金融类科目]|
|FN447 |double | |应收款项类投资(万元)  [注：金融类科目]|
|FN448 |double | |同业及其它金融机构存放款项(万元)  [注：金融类科目]|
|FN449 |double | |以公允价值计量且其变动计入当期损益的金融负债(万元)  [注：金融类科目]|
|FN450 |double | |吸收存款(万元)  [注：金融类科目]|
|FN451 |double | |代理业务负债(万元)  [注：金融类科目]|
|FN452 |double | |其他负债(万元)  [注：金融类科目]|
|FN453 |double | |发放贷款及垫款(万元)  [注：金融类科目]|
|FN501 |double | |稀释每股收益(元)|
|FN502 |double | |营业总收入(万元)|
|FN503 |double | |汇兑收益(万元)|
|FN504 |double | |其中:归属于母公司综合收益(万元)|
|FN505 |double | |其中:归属于少数股东综合收益(万元)|
|FN506 |double | |利息收入(万元)|
|FN507 |double | |已赚保费(万元)|
|FN508 |double | |手续费及佣金收入(万元)|
|FN509 |double | |利息支出(万元)|
|FN510 |double | |手续费及佣金支出(万元)|
|FN511 |double | |退保金(万元)|
|FN512 |double | |赔付支出净额(万元)|
|FN513 |double | |提取保险合同准备金净额(万元)|
|FN514 |double | |保单红利支出(万元)|
|FN515 |double | |分保费用(万元)|
|FN516 |double | |其中:非流动资产处置利得(万元)|
|FN517 |double | |信用减值损失(万元)|
|FN518 |double | |净敞口套期收益(万元)|
|FN519 |double | |营业总成本(万元)|
|FN520 |double | |信用减值损失(万元、2019格式)|
|FN521 |double | |资产减值损失(万元、2019格式)|
|FN522 |double | |其他业务收入(万元)  [注：金融类科目]|
|FN523 |double | |业务及管理费(万元)  [注：金融类科目]|
|FN524 |double | |其他业务成本(万元)  [注：金融类科目]|
|FN561 |double | |加:其他原因对现金的影响2(万元)(现金的期末余额科目)|
|FN562 |double | |客户存款和同业存放款项净增加额(万元)|
|FN563 |double | |向中央银行借款净增加额(万元)|
|FN564 |double | |向其他金融机构拆入资金净增加额(万元)|
|FN565 |double | |收到原保险合同保费取得的现金(万元)|
|FN566 |double | |收到再保险业务现金净额(万元)|
|FN567 |double | |保户储金及投资款净增加额(万元)|
|FN568 |double | |处置以公允价值计量且其变动计入当期损益的金融资产净增加额(万元)|
|FN569 |double | |收取利息、手续费及佣金的现金(万元)|
|FN570 |double | |拆入资金净增加额(万元)|
|FN571 |double | |回购业务资金净增加额(万元)|
|FN572 |double | |客户贷款及垫款净增加额(万元)|
|FN573 |double | |存放中央银行和同业款项净增加额(万元)|
|FN574 |double | |支付原保险合同赔付款项的现金(万元)|
|FN575 |double | |支付利息、手续费及佣金的现金(万元)|
|FN576 |double | |支付保单红利的现金(万元)|
|FN577 |double | |其中:子公司吸收少数股东投资收到的现金(万元)|
|FN578 |double | |其中:子公司支付给少数股东的股利、利润(万元)|
|FN579 |double | |投资性房地产的折旧及摊销(万元)|
|FN580 |double | |信用减值损失(万元)|
|FN581 |double | |使用权资产折旧（万元）|
|FN582 |double | |收取利息和手续费净增加额(万元)  [注：金融类科目]|
|FN583 |double | |支付手续费的现金(万元)  [注：金融类科目]|
|FN584 |double | |发行债券支付的现金(万元)  [注：金融类科目]|

#### `get_financial_data_by_date`: 按年度/季度获取财务数据

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| stock_list | Y | List[str] | 股票代码列表 |
| field_list | Y | List[str] | 专业财务字段列表 |
| year | N | int | 年份；`0` 表示最新 |
| mmdd | N | int | 报告期月日，如 `331`, `630`, `930`, `1231`; `0` 表示最新 |

**返回字段：**
与 `get_financial_data` 接口返回字段相同

#### `get_gpjy_value`: 获取股票交易类专业序列数据

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| stock_list | Y | List[str] | 股票代码列表 |
| field_list | Y | List[str] | 专业数据字段列表 |
| start_time | N | str | 开始日期 |
| end_time | N | str | 结束日期 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
|GP01|double | |股东人数 股东户数(户)|
|GP02|double | |龙虎榜   买入总计(万元) 卖出总计(万元)[注：该指标展示20230717日之后的数据]|
|GP03|double | |融资融券1 融资余额(万元) 融券余量(股)|
|GP04|double | |大宗交易 成交均价(元) 成交额(万元)|
|GP05|double | |增减持1   成交均价(元) 变动股数(股)|
|GP06|double | |陆股通持股量  持股数量(股)[注：该指标展示20170317日之后的数据]|
|GP07|double | |陆股通市场成交净额  陆股通市场净买入(万元)[注：官方只公布了每日的前十名数据]|
|GP08|double | |龙虎榜机构(卖方)数据  卖方机构个数 机构卖出金额(万元)|
|GP09|double | |龙虎榜机构(买方)数据  买方机构个数 机构买入金额(万元)|
|GP10|double | |近3月机构调研情况  近3月机构调研次数 近3月调研机构数量|
|GP11|double | |融资融券2 融资买入额(万元) 融资偿还额(万元)|
|GP12|double | |融资融券3 融券卖出量(股) 融券偿还量(股)|
|GP13|double | |融资融券4 融资净买入(万元) 融券净卖出(股)|
|GP14|double | |涨停数据 涨停金额(即板上成交,万元) 开板次数[注：该指标展示20180319日之后的数据]|
|GP15|double | |涨跌停 涨跌停状态 封单金额(万元)[注：涨停取2,曾涨停取1,跌停取-2,曾跌停取-1;跌停和曾跌停时,封单金额取负值 该指标展示20160926日之后的数据]|
|GP16|double | |总市值 总市值(万元)|
|GP17|double | |龙虎榜营业部数据    买入金额(万元) 卖出金额(万元)|
|GP18|double | |龙虎榜沪深股通数据  买入金额(万元) 卖出金额(万元)|
|GP19|double | |每周股票质押数量    无限售股份质押数(万) 有限售股份质押数(万)[注：该指标展示20180316日之后的数据]|
|GP20|double | |每周股票质押比例    质押比例(%)[注：该指标展示20180316日之后的数据]|
|GP21|double | |股息率 股息率(%)|
|GP22|double | |涨跌停 封成比 封流比[注：该指标展示20180319日之后的数据]|
|GP23|double | |拟增减持 拟增持数量(万股) 拟减持数量(万股)|
|GP24|double | |涨停  首次涨停时间  涨停最大封单额(万) [注：首次涨停时间展示20160301之后的数据，涨停最大封单额展示20200730之后的数据]|
|GP25|double | |盘前盘后成交量  开盘成交量(手)  盘后固定成交量(手)  [注：盘后固定成交量只包含科创板和创业板]|
|GP26|double | |拟增减持金额  拟增持金额(万元)  拟减持金额(万元)|
|GP27|double | |人气排名  市场人气排名  行业人气排名  [注：行业排名为通达信二级研究行业排名]|
|GP28|double | |股票回购  回购均价(元)  回购数量(万股)|
|GP29|double | |证券信息  是否复牌日  是否更名日  [注：是否复牌日说明：0-不是复牌日，n(n>0)-停牌n个交易日之后的复牌日；是否更名日说明：0-未更名，1-常规更名，2-加ST，3-加*ST，4-摘帽，5-其他]|
|GP30|double | |分红送转  派息金额(万元)  送转数量(股)  [注：对应展示日期为除权除息日]|
|GP31|double | |转融券  期初余量(股)  期末余量(股)|
|GP32|double | |转融券  融出数量(股)  融出市值(元)|
|GP33|double | |跌停数据  跌停金额(万元)  开板次数 [注：该指标展示20180319日之后的数据,暂无跌停金额数据]|
|GP34|double | |跌停  首次跌停时间  跌停最大封单额(万) [注：首次跌停时间展示20160301之后的数据，跌停最大封单额展示20200730之后的数据]|
|GP35|double | |增减持2  增持数量(股) 减持数量(股)|
|GP36|double | |竞价涨停买  买入金额(万元) [注：该指标展示20241101日之后的数据]|
|GP37|double | |龙虎榜2  上榜类型连续交易日(天) [注：该指标展示上榜类型中指代的连续交易日类型]|
|GP38|double | |涨停相关1  近1年涨停次数  近1年溢价5%次数|
|GP39|double | |涨停相关2  近1年首板封板率(%)  近1年次日红盘率(%)|
|GP40|double | |涨停相关3  近1年连板率(%)  最后涨停时间|
|GP41|double | |股权登记日  配股股权登记日|
|GP42|double | |龙虎榜专业机构买卖净额  买方成交净额(万元)  卖方成交净额(万元)|
|GP43|double | |配股实施  配股价格(元)  配股数量(万股)|
|GP44|double | |股票评分  综合评分|
|GP45|double | |评级系数  评级系数|
|GP46|double | |拟询价转让  拟转让股数(万股)  拟转让占总股本(%)|
#### `get_gpjy_value_by_date`: 按日期获取股票交易类专业数据

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| stock_list | Y | List[str] | 股票代码列表 |
| field_list | Y | List[str] | 专业数据字段列表 |
| year | N | int | 年份；`0` 表示最新 |
| mmdd | N | int | 月日；`0` 表示最新 |

**返回字段：**
与 `get_gpjy_value` 接口返回字段相同

#### `get_bkjy_value`: 获取板块交易类专业序列数据

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| stock_list | Y | List[str] | 板块代码列表 |
| field_list | Y | List[str] | 专业数据字段列表 |
| start_time | N | str | 开始日期 |
| end_time | N | str | 结束日期 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
|BK5|double | |市盈率TTM   整体法  算术平均|
|BK6|double | |市净率MRQ   整体法  算术平均|
|BK7|double | |市销率TTM   整体法  算术平均|
|BK8|double | |市现率TTM   整体法  算术平均|
|BK9|double | |涨跌数   上涨家数  下跌家数|
|BK10|double | |板块总市值(亿元)   整体法  算术平均|
|BK11|double | |板块流通市值(亿元) 整体法  算术平均|
|BK12|double | |涨停数   涨停家数  曾涨停家数[注：该指标展示20160926日之后的数据]|
|BK13|double | |跌停数   跌停家数  曾跌停家数[注：该指标展示20160926日之后的数据]|
|BK14|double | |涨停数据  市场高度(不含ST股和未开板新股)  2板及以上涨停个数(不含ST股和未开板新股)[注：该指标展示20180319日之后的数据]|
|BK15|double | |融资融券  沪深京融资余额(万元)   沪深京融券余额(万元)|
|BK16|double | |陆股通资金流入  沪股通流入金额(亿元)  深股通流入金额(亿元) [注：该指标展示20170320日之后的数据]|
|BK17|double | |开盘成交数    开盘成交额(万元)  开盘成交量(万股)|
|BK18|double | |板块股息率(%)   算数平均  整体法|
|BK19|double | |板块自由流通市值(亿元)  整体法  算术平均|

#### `get_bkjy_value_by_date`: 按日期获取板块交易类专业数据

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| stock_list | Y | List[str] | 板块代码列表 |
| field_list | Y | List[str] | 专业数据字段列表 |
| year | N | int | 年份；`0` 表示最新 |
| mmdd | N | int | 月日；`0` 表示最新 |

**返回字段：**
与 `get_bkjy_value` 接口返回字段相同

#### `get_scjy_value`: 获取市场交易类专业序列数据

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| field_list | Y | List[str] | 市场专业数据字段列表 |
| start_time | N | str | 开始日期 |
| end_time | N | str | 结束日期 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
|SC01|double | |融资融券       沪深京融资余额(万元) 沪深京融券余额(万元)|
|SC02|double | |陆股通资金流入 沪股通流入金额(亿元) 深股通流入金额(亿元)[注：沪股通限制展示2000条数据，深股通展示自20161205以后的数据]|
|SC03|double | |沪深京涨停股个数 涨停股个数  曾涨停股个数 [注：该指标展示20160926日之后的数据]|
|SC04|double | |沪深京跌停股个数 跌停股个数  曾跌停股个数 [注：该指标展示20160926日之后的数据]|
|SC05|double | |上证50股指期货  净持仓(手)[注：该指标展示20171009日之后的数据]|
|SC06|double | |沪深300股指期货 净持仓(手) [注：该指标展示20171009日之后的数据]|
|SC07|double | |中证500股指期货 净持仓(手) [注：该指标展示20171009日之后的数据]|
|SC08|double | |ETF基金规模份额数据 ETF基金规模(亿份) ETF净申赎(亿份)|
|SC09|double | |沪月新开A股账户   沪月新开A股账户(万户) |
|SC10|double | |增减持统计    增持额(万元)  减持额(万元)[注：部分公司公告滞后,造成每天查看的数据可能会不一样] |
|SC11|double | |大宗交易      溢价的大宗交易额(万元) 折价的大宗交易额(万元)|
|SC12|double | |限售解禁      限售解禁计划额(亿元)  限售解禁股份实际上市金额(亿元)[注：该指标展示201802月之后的数据;部分股票的解禁日期延后，造成不同日期提取的某天的计划额可能不同]|
|SC13|double | |分红    市场总分红额(亿元)[注：除权派息日的A股市场总分红额] |
|SC14|double | |募资    市场总募资额(亿元)[注：发行日期/除权日期的首发、配股和增发的总募资额] |
|SC15|double | |打板资金    封板成功资金(亿元) 封板失败资金(亿元) [注：该指标展示20160926日之后的数据]|
|SC16|double | |龙虎榜    买入总金额(亿元) 卖出总金额(亿元)|
|SC17|double | |龙虎榜机构数据    买入金额(亿元) 卖出金额(亿元) |
|SC18|double | |龙虎榜营业部数据    买入金额(亿元) 卖出金额(亿元) |
|SC19|double | |龙虎榜沪深股通数据    买入金额(亿元) 卖出金额(亿元)|
|SC20|double | |陆股通净买入    沪股通净买入额(亿元) 深股通净买入额(亿元)|
|SC21|double | |每周无限售质押率    深市质押率(%) 沪市质押率(%)[注：该指标展示20180128日之后的数据]|
|SC22|double | |每周有限售质押率    深市质押率(%) 沪市质押率(%)[注：该指标展示20180128日之后的数据]|
|SC23|double | |连板家数    连板股个数(包含ST和未开板新股)  连板股个数(不含ST股和未开板新股）[注：该指标展示20180319日之后的数据]|
|SC24|double | |沪深京涨跌停股个数    涨停股个数(不含ST股和未开板新股) 跌停股个数（不含ST股）[注：该指标展示20160926日之后的数据]|
|SC25|double | |融资融券    沪深京融资买入额（万元）沪深京融券卖出量（万股）|
|SC26|double | |每周市场质押比     每周市场质押比例（%）[注：该指标展示20180316日之后的数据]|
|SC27|double | |央行公开市场净投放    央行公开市场净投放 (亿元) |
|SC28|double | |历史A股新高新低数  历史新高A股股票个数 历史新低A股股票个数(上市满一年的股票)|
|SC29|double | |120天A股新高新低数 120天新高A股股票个数 120天新低A股股票个数(上市满一年的股票)|
|SC30|double | |涨停数据  市场高度(不含ST股和未开板新股)  2板以上涨停个数(不含ST股和未开板新股)[注：该指标展示20180319日之后的数据]|
|SC31|double | |涨跌家数   涨家数（剔除停牌）  跌家数（剔除停牌）|
|SC32|double | |20天A股新高新低数 20天新高A股股票个数 20天新低A股股票个数(上市满一年的股票)|
|SC33|double | |市场总封单金额  涨停封单金额（亿元）跌停封单金额（亿元）[注：该指标展示20160926日之后的数据]|
|SC34|double | |涨跌股成交量    上涨股成交量(万手)  下跌股成交量(万手) |
|SC35|double | |涨停数据   换手板家数  回封率(%)  [注：两个指标都剔除了未开板新股，换手板家数展示20190605日之后的数据，回封率展示20180927日之后的数据]|
|SC36|double | |曾涨跌停股个数	曾涨停股个数(剔除ST股和未开板新股)	曾跌停股个数(剔除ST股) [注：该指标展示20160926日之后的数据]|
|SC37|double | |转融券  融出市值(亿元)  期末余额(亿元)|
|SC38|double | |ETF基金规模金额数据  ETF基金规模(亿元)  ETF净申赎(亿元)|
|SC39|double | |涨跌5%家数  涨幅大于等于5%家数  跌幅大于等于5%家数|
|SC40|double | |陆股通成交  陆股通成交总额(亿元) 陆股通成交总笔(万笔)|
|SC41|double | |中证1000股指期货 净持仓(手) [注：该指标展示20220722日之后的数据]|
|SC42|double | |沪深股通成交金额  沪股通成交总额(亿元)  深股通成交总额(亿元) |

#### `get_scjy_value_by_date`: 按日期获取市场交易类专业数据

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| field_list | Y | List[str] | 市场专业数据字段列表 |
| year | N | int | 年份；`0` 表示最新 |
| mmdd | N | int | 月日；`0` 表示最新 |

**返回字段：**
与 `get_scjy_value` 接口返回字段相同

#### `get_gp_one_data`: 获取单股/多股一次性专业数据

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| stock_list | Y | List[str] | 股票代码列表 |
| field_list | Y | List[str] | 专业数据字段列表 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
|GO1 |double | |发行价(元)|
|GO2 |double | |总发行数量(万股)|
|GO3 |double | |一致预期目标价(元)[注：一致预期值均为近半年内各家机构预测数值的平均值]|
|GO4 |double | |一致预期T年度|
|GO5 |double | |一致预期T年每股收益|
|GO6 |double | |一致预期T+1年每股收益|
|GO7 |double | |一致预期T+2年每股收益|
|GO8 |double | |一致预期T年净利润(万元)|
|GO9 |double | |一致预期T+1年净利润(万元)|
|GO10 |double | |一致预期T+2年净利润(万元)|
|GO11 |double | |一致预期T年营业收入(万元)|
|GO12 |double | |一致预期T+1年营业收入(万元)|
|GO13 |double | |一致预期T+2年营业收入(万元)|
|GO14 |double | |一致预期T年营业利润(万元)|
|GO15 |double | |一致预期T+1年营业利润(万元)|
|GO16 |double | |一致预期T+2年营业利润(万元)|
|GO17 |double | |一致预期T年每股净资产(元)|
|GO18 |double | |一致预期T+1年每股净资产(元)|
|GO19 |double | |一致预期T+2年每股净资产(元)|
|GO20 |double | |一致预期T年净资产收益率(%)|
|GO21 |double | |一致预期T+1年净资产收益率(%)|
|GO22 |double | |一致预期T+2年净资产收益率(%)|
|GO23 |double | |一致预期T年PE|
|GO24 |double | |一致预期T+1年PE|
|GO25 |double | |一致预期T+2年PE|
|GO26 |double | |最新解禁日(YYMMDD格式)|
|GO27 |double | |最新解禁数量（万股）|
|GO28 |double | |下一报告期的预约披露时间|
|GO29 |double | |最新持股机构家数|
|GO30 |double | |最新机构持股总量（万股）|
|GO31 |double | |最新持股基金家数|
|GO32 |double | |最新基金持股量（万股）|
|GO33 |double | |最新总股本（万股）|
|GO34 |double | |最新实际流通A股（万股）|
|GO35 |double | |最新业绩预告 报告期(YYMMDD格式)|
|GO36 |double | |最新业绩预告 本期归母净利润下限（万元）|
|GO37 |double | |最新业绩预告 本期归母净利润上限（万元）|
|GO38 |double | |最新业绩预告 本期归母净利润预计同比增减幅下限%|
|GO39 |double | |最新业绩预告 本期归母净利润预计同比增减幅上限%|
|GO40 |double | |最新业绩快报 报告期|
|GO41 |double | |最新业绩快报 归母净利润（万元）|
|GO42 |double | |分红募资 派现总额（万元）|
|GO43 |double | |分红募资 募资总额（万元）|
|GO44 |double | |最新业绩预告 本期扣非净利润下限(万元)|
|GO45 |double | |最新业绩预告 本期扣非净利润上限(万元)|
|GO46 |double | |最新业绩预告 本期扣非净利润预计同比增减幅下限%|
|GO47 |double | |最新业绩预告 本期扣非净利润预计同比增减幅上限%|

### 公式接口

#### `formula_set_data`: 设置公式计算用行情数据

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| stock_code | Y | str | 股票代码 |
| stock_period | N | str | 周期，默认 `1d` |
| stock_data | Y | List | 公式输入行情数据 |
| count | N | int | 数据条数 |
| dividend_type | N | int | 复权类型数值 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| ErrorId | str | 错误码，`0` 表示成功 |
| Value | str/Object | 设置结果 |

#### `formula_set_data_info`: 设置公式计算数据范围

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| stock_code | Y | str | 股票代码 |
| stock_period | N | str | 周期，默认 `1d` |
| start_time | N | str | 开始日期 |
| end_time | N | str | 结束日期 |
| count | N | int | 数据条数 |
| dividend_type | N | int | 复权类型数值 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| ErrorId | str | 错误码，`0` 表示成功 |
| Value | str/Object | 设置结果 |

#### `formula_get_data`: 获取当前公式输入数据

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| 无 | N | - | 不需要参数 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| Code | str | 股票代码 |
| Date | str | 日期 |
| Open | str | 开盘价（元） |
| High | str | 最高价（元） |
| Low | str | 最低价（元） |
| Close | str | 收盘价（元） |
| Volume | str | 成交量（股） |
| Amount | str | 成交额（万元） |

#### `formula_zb`: 指标公式计算

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| formula_name | Y | str | 指标公式名称 |
| formula_arg | N | str | 公式参数字符串 |
| xsflag | N | int | 小数位控制 |

**返回字段：**
| 字段 | 类型 | 说明 |
|------|------|------|
| Value | Object | 指标公式结果 |

#### `formula_xg`: 选股公式计算

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| formula_name | Y | str | 选股公式名称 |
| formula_arg | N | str | 公式参数字符串 |
| xsflag | N | int | 小数位控制 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| Value | Object | 指标公式结果 |

#### `formula_exp`: 专家公式计算

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| formula_name | Y | str | 专家公式名称 |
| formula_arg | N | str | 公式参数字符串 |
| xsflag | N | int | 小数位控制 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| Value | Object | 指标公式结果 |

#### `formula_process_mul_xg`: 批量选股公式

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| formula_name | Y | str | 选股公式名称 |
| formula_arg | N | str | 公式参数字符串 |
| return_count | N | int | 每只股票返回结果数量 |
| return_date | N | bool | 是否返回日期 |
| stock_list | Y | List[str] | 股票代码列表 |
| stock_period | N | str | 周期，默认 `1d` |
| start_time | N | str | 开始日期 |
| end_time | N | str | 结束日期 |
| count | N | int | 行情数据条数 |
| dividend_type | N | int | 复权类型数值 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| Code | str | 股票代码 |
| Date | str | 日期，若返回 |
| Value | Object | 批量选股结果 |

#### `formula_process_mul_zb`: 批量指标公式

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| formula_name | Y | str | 指标公式名称 |
| formula_arg | N | str | 公式参数字符串 |
| return_count | N | int | 每只股票返回结果数量 |
| return_date | N | bool | 是否返回日期 |
| xsflag | N | int | 小数位控制 |
| stock_list | Y | List[str] | 股票代码列表 |
| stock_period | N | str | 周期，默认 `1d` |
| start_time | N | str | 开始日期 |
| end_time | N | str | 结束日期 |
| count | N | int | 行情数据条数 |
| dividend_type | N | int | 复权类型数值 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| Code | str | 股票代码 |
| Date | str | 日期，若返回 |
| Value | Object | 批量选股结果 |

#### `formula_process_mul_exp`: 批量专家公式

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| formula_name | Y | str | 专家公式名称 |
| formula_arg | N | str | 公式参数字符串 |
| return_count | N | int | 每只股票返回结果数量 |
| return_date | N | bool | 是否返回日期 |
| xsflag | N | int | 小数位控制 |
| stock_list | Y | List[str] | 股票代码列表 |
| stock_period | N | str | 周期，默认 `1d` |
| start_time | N | str | 开始日期 |
| end_time | N | str | 结束日期 |
| count | N | int | 行情数据条数 |
| dividend_type | N | int | 复权类型数值 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| Code | str | 股票代码 |
| Date | str | 日期，若返回 |
| Value | Object | 批量选股结果 |

#### `formula_get_all`: 获取公式列表

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| formula_type | N | int | `0` 技术指标公式`1` 条件选股公式`2` 专家系统公式 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
|acCode	|str	|公式代码|
|acName	|str	|公式名称|
|isSys	|int	|是否为系统公式|

#### `formula_get_info`: 获取公式详情

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| formula_type | N | int | `0` 指标；`1` 选股；`2` 专家 |
| formula_code | Y | str | 公式代码 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
|acCode	|str	|公式代码|
|acName	|str	|公式名称|
|isSys	|int	|是否为系统公式|
|ParaNum|int	|入参数量|
|Para		|Set	|公式入参参数|
|ParaName	|Set	|公式入参名称|
|Min			|Set	|公式入参最小值|
|Max			|Set	|公式入参最大值|
|Default			|Set	|公式入参默认值|
|LineNum		|int	|出参数量|
|Line			|Set	|公式出参参数|
|LineName	|Set	|公式出参名称|

### 交易

- `account_id` 默认规则: 未指定账号时默认传 `0`; 指定账号和账号类型时, 先调用 `stock_account` 并使用其返回的 `Value` 作为 `account_id`。

#### `stock_account`: 获取交易账户句柄

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| account | Y | str | 资金账号 |
| account_type | N | str | 账号类型，默认 `stock` |

- account_type当前可选：'STOCK' 股票交易, 'CREDIT' 信用交易 'FUTURE' 期货交易 'OPTION' 期权交易。如果不设成参数，就是'STOCK'

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| Value | int | 账户句柄 `account_id` |

#### `query_stock_asset`: 查询资产

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| account_id | Y | int | 账户句柄；未指定账号时默认 `0` |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| Currency | str | 币种 |
| Balance  | str | 余额 |
| Cash | str | 可用余额 |
| Asset | str | 资产 |
| MarketValue  | str | 总市值 |
| TotalFreeze  | str | 期货冻结资金 |
| CloseProfit | str | 期货平仓盈亏 |
| CurrentEquity  | str | 期货动态权益 |
| PreviousEquity  | str | 期货静态权益 |
| ProfitLoss  | str | 期货持仓盈亏 |
| TotalMargin | str | 期货持仓保证金 |

#### `query_stock_orders`: 查询委托

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| account_id | Y | int | 账户句柄；未指定账号时默认 `0` |
| stock_code | N | str | 股票代码；空表示不按股票过滤 |
| cancelable_only | N | bool | 是否仅查询可撤委托 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
|Wtbh		|str	|委托编号|
|Code		|str	|股票代码|
|Time		|str	|时间，HHMMSS|
|BSFlag		|int	|买卖标志,0买 1卖 -1撤单|
|KPFlag		|int	|开平标志，0开仓1平仓2平今|
|WTFS		|str	|市价方式，根据沪深市场不一样|
|Status		|int	|委托状态|
|WtDate		|int	|撤单标志，为1表示已撤,为2表示是夜盘单|
|CjPric		|str	|成交价|
|CJVol		|str	|成交数量 如果是撤,则为负值|
|WtPrice	|str	|委托价|
|WtVol		|str	|委托数量 如果是撤,则为负值|

#### `query_stock_positions`: 查询持仓

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| account_id | Y | int | 账户句柄；未指定账号时默认 `0` |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| Code | str | 证券代码 |
| Cbj | str | 成本价 |
| TotalVol | str | 总持仓 |
| CanUseVol | str | 可用持仓 |
| BuyPosition | str | 多头持仓（期货或期权）|
| BuyAvgPrice | str | 多头持仓均价（期货或期权）|
| BuyProfitLoss | str | 多头持仓盈亏（期货或期权）|
| SellPosition | str | 空头持仓（期货或期权）|
| SellAvgPrice | str | 空头持仓均价（期货或期权）|
| SellProfitLoss | str | 空头持仓盈亏（期货或期权）|
| TodayBuyPosition | str | 当日买入持仓（期货或期权）|
| TodaySellPosition | str | 当日卖出持仓（期货或期权）|

#### `order_stock`: 下单

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| account_id | Y | int | 账户句柄；未指定账号时默认 `0` |
| stock_code | Y | str | 股票代码 |
| order_type | Y | int | `0` 买入；`1` 卖出 |
| order_volume | Y | int | 委托数量 |
| price_type | Y | int | `0` 自填价；`1` 市价；`2` 涨停/笼子上限；`3` 跌停/笼子下限 |
| price | N | float | 委托价格；市价可传 `0` |
| notify | N | int | 是否通知，默认 `0` |

- order_type可选类型： STOCK_BUY买(0)，STOCK_SELL卖(1)，CREDIT_BUY担保品买入(0)，CREDIT_SELL担保品卖出(1) ，CREDIT_FIN_BUY融资买入(69)，CREDIT_SLO_SELL融券卖出(70)，CREDIT_COV_BUY(71)，CREDIT_STK_REPAY(76)，ETF相关，FUNTURE相关，OPTION相关
- price_type可选类型：PRICE_MY自填价格(0)，PRICE_SJ市价(1)，PRICE_ZTJ涨停价(2)，PRICE_DTJ跌停价(3)

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
|Value		|int	|成功标志，0失败，1待用户确认，2成功|
|Wtbh			|str	|委托编号，只有成功时才会返回|
|Msg			|str	|返回提示信息|

#### `cancel_order_stock`: 撤单

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| account_id | Y | int | 账户句柄；未指定账号时默认 `0` |
| stock_code | Y | str | 股票代码 |
| order_id | Y | str | 委托编号 |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
|Value		|int	|成功标志，0失败，1成功|
|Msg			|str	|返回提示信息|


### tqcenter 有但当前 HTTP 不应直接调用的函数

这些函数存在于 `tqcenter.py`, 但不是 TPyth HTTP 的直接 method, 或者属于本地 Python 工具函数:

- 生命周期/本地辅助: `initialize`, `close`, `filter_dict_by_fields`, `price_df`, `print_to_tdx`, `formula_format_data`。
- 订阅/回调相关: `subscribe_hq`, `unsubscribe_hq`, `subscribe_quote`, `get_subscribe_hq_stock_list`; 这类接口依赖持续连接、Python 回调或本地订阅状态, 当前 skill 不应直接通过一次性 HTTP 调用。

---

## 返回处理

成功响应示例:

```json
{
  "id": 1,
  "result": {
    "ErrorId": "0",
    "Value": {}
  }
}
```

错误响应示例:

```json
{
  "id": 1,
  "error": {
    "code": -32600,
    "message": "HTTP请求JSON解析失败"
  }
}
```

处理规则:

1. 优先检查 HTTP 状态码是否为 200。
2. 再检查响应中是否存在 `error`。
3. 若存在 `result.ErrorId`, 只有 `"0"` 表示底层接口成功。
4. 中文响应按 UTF-8 解析。
5. 展示结果需要股票名但返回中没有股票名时, 优先用已有股票代码调用 `get_stock_info` 补全; 无法补全时显示股票代码。
6. 用户只提供股票名而后续接口需要股票代码时, 优先用 `get_match_stkinfo` 按股票名查代码; 多个候选无法唯一确定时先让用户确认。
7. 当用户取最新涨幅等，优先调用`get_more_info`中的ZAF等。
8. 需要获取某个数据前，先遍历每个接口的参数和返回字段，确认该数据在哪个接口的哪个字段里；如果不确定数据在哪个接口里，直接询问用户应该调用哪个接口获取该数据，不要盲猜或根据历史记忆调用某个接口。

---

## 故障排除

### 连接失败

- 确认通达信客户端已经运行。
- 确认 HTTP 服务监听在 `127.0.0.1:17709`。

### `HTTP请求JSON解析失败`

- 请求体必须是标准 JSON。
- 字符串必须使用双引号。
- 字段和值之间必须使用冒号 `:`, 不能使用等号 `=`。
- 不要发送 Python 字典格式, 例如 `{'id': 1}`。
- `Content-Length` 必须与 UTF-8 字节长度一致。

错误示例:

```json
{"params":{"account"="1190306953"}}
```

正确示例:

```json
{"params":{"account":"1190306953"}}
```

### 接口不存在

- 检查 `method` 是否为 tqcenter 原接口名。
- 不要写成 `tq.get_market_data`, 应写 `get_market_data`。

---

## 执行约束

当用户要求调用通达信 TQ 接口时, 应直接构造并发送 HTTP 请求。需要先向用户询问是否要生成示例脚本, 否则不要创建 Python 文件。即使使用 Python, 也只能作为 HTTP 客户端发送请求, 不得导入 `tqcenter`。
