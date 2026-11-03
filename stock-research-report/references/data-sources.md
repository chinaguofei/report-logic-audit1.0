# 数据源与取数细节

## ⭐ 数据源优先级总表（P07，2026-10-29 用户定稿：稳定最全最新者优先挖掘，常出问题的尽量不访问）

| 优先 | 数据源 | 用途 | 实战表现（迅捷兴 688655 + 西典新能 603312 双报告） |
|---|---|---|---|
| **首选** | 东财 datacenter 系列（`datacenter.eastmoney.com` / `datacenter-web.eastmoney.com`） | F10 财务（RPT_F10_FINANCE_MAINFINADATA）、股东户数（RPT_HOLDERNUM_DET / RPT_F10_EH_HOLDERNUM）、十大流通股东、送转 | 两份报告零故障；22 期追溯最全（含招股书口径）、字段齐、当日更新快 |
| **首选** | 腾讯行情 `qt.gtimg.cn`（快照）/ `web.ifzq.gtimg.cn`（K 线） | 行情快照、PE/PB 批量、日 K（前复权+不复权） | 全程稳定无一次失败；qt.gtimg 一次可批量多票（`q=sz301717,sh688800,...`） |
| **备用** | 东财 `push2.eastmoney.com`（快照）/ `push2his`（K 线） | 仅在腾讯缺字段时用 | **频繁限流**（两份报告均被掐过；被掐后等 60s 或直接换腾讯，勿反复重试） |
| **注意** | 东财业绩快报 `RPT_LICO_FN_CPD` | 累计业绩 | 次新股追溯不全（688655 缺 2021 前季度、603312 无 2021 季度）；扣非字段可能为空 → 一律以 F10 MAINFINADATA 为准，此接口只作交叉核 |
| **慎用** | 同花顺/雪球等非公开接口 | — | 未验证稳定性，不主动访问 |

**执行规则**：新报告取数先走「首选」两行；首选失败一次即切换同用途的另一个首选源（不重试备用超过 1 次）；把本次源表现记入报告 meta.source 溯源。

## 代码前缀规则

| 市场 | 行情接口 | K 线接口 | eastmoney SECUCODE |
|---|---|---|---|
| 深市 | `sz002536` | `sz002536` | `002536.SZ` |
| 沪市 | `sh600685` | `sh600685` | `600685.SH` |
| 港股 | `hk03696` | `hk03696` | `03696.HK` |

eastmoney SECUCODE **后缀必须大写、不带前缀**。写成 `sh688363` 会返回"返回数据为空"。

## 行情快照

```bash
curl -s "https://qt.gtimg.cn/q=sz002536" | iconv -f gbk -t utf-8
```

- **返回 GBK，必须 iconv 转码**
- 字段：名称、代码、现价、昨收、今开、成交量、涨跌幅、市值、PE、PB 等（`~` 分隔）
- 代码不存在时返回 `v_pv_none_match="1"`

## 日 K 线（前复权）

**A 股主源：东财 push2his kline（`fqt=1` 前复权，一次取全历史；腾讯为备源）**

```bash
curl -s "https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=0.002536&klt=101&fqt=1&beg=0&end=20500101&lmt=490&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61" -H "User-Agent: Mozilla/5.0" -H "Referer: https://quote.eastmoney.com/"
```

- secid 前缀：深市 `0.`、沪市 `1.`；klt=101 日线；fqt=1 前复权（估值通道用 `fqt=0` 不复权，勿混）
- 返回 `data.klines` 逗号拼接串：`日期,开,收,高,低,量(手),额,振幅,涨跌幅,涨跌额,换手` —— 列序为**开,收,高,低**（与腾讯不同）；量单位手，×100 换算成股
- **push2his 域限流频繁**（见文末「已知故障」，2026-09-27/28 两次实测不可达）→ 不可达时**直接用腾讯备源**，勿反复重试
- `draw_kline.py` 的 `_load_bars` 自动兼容东财/腾讯两种返回格式

**备源：腾讯 fqkline**

```bash
# A 股
curl -s "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz002536,day,,,490,qfq"
# 港股
curl -s "https://web.ifzq.gtimg.cn/appstock/app/hkfqkline/get?param=hk03696,day,,,490,qfq"
```

- A 股 JSON 取 `data.{code}.qfqday`；港股取 `hkfqkline`
- 每根为 `[日期, 开, 收, 高, 低, 成交量(手)]`

## 财务数据（A 股）

```
https://datacenter-web.eastmoney.com/api/data/v1/get
  reportName=RPT_F10_FINANCE_MAINFINADATA
  columns=SECUCODE,REPORT_DATE,TOTALOPERATEREVE,TOTALOPERATEREVETZ,PARENTNETPROFIT,
          PARENTNETPROFITTZ,XSMLL,XSJLL,KCFJCXSYJLR,KCFJCXSYJLRTZ,ROEJQ
  filter=(SECUCODE="002536.SZ")
  sortColumns=REPORT_DATE&sortTypes=-1&pageSize=20
```

关键字段：
- `TOTALOPERATEREVE` 营业总收入（累计）、`TOTALOPERATEREVETZ` 同比
- `PARENTNETPROFIT` 归母净利（累计）、`PARENTNETPROFITTZ` 同比
- `KCFJCXSYJLR` 扣非净利（累计）、`KCFJCXSYJLRTZ` 同比
- `XSMLL` 销售毛利率（累计）

**必须带 headers**：
```python
headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://emweb.securities.eastmoney.com/'}
```

单季度值 = 累计值差分；单季毛利率 = 累计毛利额差分推算。
扣非 TTM = 滚动四个季度扣非合计。

## 三表明细与财务甄别证据（2026-09-27 新增）

**坑：`RPT_F10_FN_*` 系列报表名不存在**（返回 code 9501「报表配置不存在」），别再试 F10_FN_INCOME / F10_FN_BALANCE / F10_FN_CASHFLOW。可用两条路：

1) **DMSK 摘要表**（快但字段少）：
```
reportName=RPT_DMSK_FN_INCOME / RPT_DMSK_FN_BALANCE / RPT_DMSK_FN_CASHFLOW
sortColumns=REPORT_DATE&sortTypes=-1
```
注意：摘要表里 GOODWILL / RESEARCH_EXPENSE / DEVELOP_EXPENSE 等明细字段为 None。质押数据用 `RPT_CSDC_LIST`（filter=(SECUCODE="603893.SH")，按 TRADE_DATE 排序，取 PLEDGE_RATIO 质押比例）。

2) **emweb 三表明细接口**（全字段，财务甄别第六章首选）：
```
https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/lrbAjaxNew?companyType=4&reportDateType=0&reportType=1&dates=2026-06-30,2026-03-31,...&code=SH603893
（zcfzbAjaxNew / xjllbAjaxNew 同理；code 前缀大写 SH/SZ；dates 逗号分隔多期）
```
拿得到 RESEARCH_EXPENSE（研发费用）、GOODWILL（商誉）、DEVELOP_EXPENSE（开发支出）、短期借款/长期借款/应付债券/一年内到期非流动负债、SALES_SERVICES（销售商品收现）等。`companyType=4` 为一般企业，返回空可试 3/2/1。

**审计意见没有公开接口**（穷举 12 个候选 reportName 均失败）→ 用 WebSearch 搜「{公司} {年份} 年报 审计意见 标准无保留」从年报 PDF 取关键句。

## 股东户数

```
reportName=RPT_F10_EH_HOLDERNUM
columns=SECUCODE,END_DATE,HOLDER_TOTAL_NUM,TOTAL_NUM_RATIO,HOLDER_TOTAL_NUMCHANGE,PRICE
filter=(SECUCODE="002536.SZ")
sortColumns=END_DATE&sortTypes=-1
```

**关键坑：**
1. **单页 50 条不够** —— 最新 50 条只含约 12 条临时披露记录。必须**翻 3 页**（pageSize=50，pageNumber=1/2/3）得 150 条，覆盖约 5 年。
2. 再**筛出季度末**：月 ∈ {03, 06, 09, 12} 且 日 ∈ {30, 31}，取 16 期。
3. 户数环比一律用**季度末 vs 上一季度末**。切勿用临时披露日（如 8/31 vs 8/20）计算 —— 曾因此写出错误的 "+25.8%"。

## 财务数据（港股）

```
reportName=RPT_HKF10_FN_MAININDICATOR
columns=SECUCODE,REPORT_DATE,OPERATE_INCOME,GROSS_PROFIT,HOLDER_PROFIT,
        OPERATE_INCOME_YOY,BASIC_EPS
filter=(SECUCODE="03696.HK")
```

**两个坑：**
1. **金额单位为人民币（CNY）**，但公司业绩会常以**美元**披露。矩阵须注明币种口径；用 PB / 股价交叉验证币种。
2. 港股仅披露半年报/年报 → 矩阵改**半年度口径 10 列**：`指标 / 26H1 / 25H2 / 25H1 / 24H2 / 24H1 / 23H2 / 23H1 / 22H2 / 22H1`。H2 = 年度值 − H1 值，加尾差注释。

## 同业对比数据

对每家同业重复调用 A 股财务接口（换 SECUCODE）。同业选取标准：同申万三级行业 + 业务可比 + 市值相近或行业龙头，通常 4 家。

## 估值通道（第九章第 4 节，2026-09-27 新增；2026-10-17 增加 PS/PB 分派）

### 估值指标选择（2026-10-17 用户定稿，硬规则）

**高成长科技公司用 PS（市销率），传统公司用 PB（市净率）。** 按下列顺序判定，命中即用：

| 顺序 | 判定条件 | 采用 |
|---|---|---|
| 1 | **亏损 且 属科技成长类**（最近完整年度归母或扣非 ≤ 0 → PE 失效，但收入规模仍是有效定价锚） | **PS 强制** |
| 2 | 行业属科技成长类 **且** 成长性达标（下列 3 项满足 ≥2） | **PS** |
| 3 | 其余：金融、房地产、建筑、钢铁煤炭有色化工、电力公用事业、交通运输、农林牧渔、食品饮料、家电、纺服、商贸零售、机械重工等重资产或成熟行业；**以及非科技类亏损股** | **PB** |
| 4 | 用户显式指定 | 按用户 |

- **⚠️ 第 1 条只看"亏损"是不够的（2026-10-17 实测修正）**：原第 1 条写"亏损 → PS 强制"，会与第 3 条正面冲突，把化工/钢铁/航运等周期行业亏损股错误导向 PS（实测案例：海新能科 300072，基础化工、连续两年亏损、净资产为正 51.46 亿元，被误套 PS）。
  - **非科技类亏损股的处置顺序**：先看净资产 → `BPS > 0` 用 **PB**（净资产为定价下限，亏损期 PB 依然可比）；`BPS ≤ 0` 才用 **PS**（净资产为负时 PB 无意义，只能退到收入端）。
  - 周期行业亏损往往意味着行业底部，此时 PB 处于历史低位恰是有效信号，用 PS 反而会掩盖"净资产打折"这一核心事实。
- **科技成长类行业**：半导体、电子元件、消费电子、计算机设备与软件、通信设备、互联网、人工智能、生物医药与医疗器械、新能源与储能、军工电子、新材料、高端装备与工业自动化。
- **成长性达标（最近年报或 TTM）**：营收 TTM 同比 ≥ 20%；研发费用率 ≥ 5%；毛利率 ≥ 30%。判定时必须**三项逐项列出实测值**，不得只写"达标"或"未达标"。
- 科技行业但成长性未达标（如营收增速仅 10%、研发费用率 3%）→ 按第 3 条用 **PB**，并在口径段注明"成长性未达科技成长阈值"及三项实测值。
- 银行/保险/券商：**PB**（净资产是定价核心，盈利波动或周期性强）；强周期资源股：**PB**（盈利大幅波动使 PE/PS 失真）。

配套要求（缺一不可）：
- 第九章第 4 节**标题随指标变化**：「4. 近五年估值通道分析（市销率 PS）」/「（市净率 PB）」
- 口径段必须写明**选用理由与关键证据**（如"营收 TTM 同比 +28%、研发费用率 12%、毛利率 45%，属高成长科技，采用 PS"；或"城商行，盈利与净资产高度相关，采用 PB"），**禁止只写公式不写理由**

```bash
# 1) F10 序列：BPS（PB 用）、TOTALOPERATEREVE 累计营收 + TOTAL_SHARE 股本（PS 用）、NOTICE_DATE 披露日
curl -s "https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_F10_FINANCE_MAINFINADATA&columns=SECUCODE,REPORT_DATE,REPORT_DATE_NAME,NOTICE_DATE,BPS,TOTAL_SHARE,TOTALOPERATEREVE&filter=(SECUCODE%3D%22688235.SH%22)&sortColumns=REPORT_DATE&sortTypes=-1&pageSize=24&pageNumber=1&source=WEB&client=WEB" -H "User-Agent: Mozilla/5.0" -H "Referer: https://emweb.securities.eastmoney.com/" -o val_bps_{代码}.json

# 2) 不复权日 K（估值通道必须用不复权价！前复权价算 PB/PS 会失真；1500 根覆盖近 5 年）
curl -s "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh688235,day,,,1500," -o val_k_{代码}.json
```

要点：
- `BPS` = 每股净资产（元）；`NOTICE_DATE` = 披露日，通道线在披露日后切换到新一期每股值（阶梯跳变来源）
- **PB(t)** = 不复权收盘价 / 当期 BPS
- **PS(t)** = 不复权收盘价 / 当期 SPS，`SPS = 营收 TTM / 总股本`；**营收 TTM = 上年全年 + 本期累计 − 上年同期累计**（报告期为 12/31 时直接取全年）。亏损公司 PS 依然有效，这正是高成长科技用 PS 的原因
- 通道线 = 窗口内日指标的 0/20/40/60/80 分位倍数 × 当期每股值（股价尺度）
- 绘图脚本 `scripts/draw_valuation.py`（改 **5** 个常量，含 `METRIC = "PB" | "PS"`）；正文引用极值/分位前必须用脚本尾部核实输出，禁止估算
- **同一披露日挂了多期**：东财对上市前历史数据常统一填招股书披露日（如 2024-07-12 同时挂 2024Q1/2023 年报/2023Q1）。脚本按**报表期最晚的一期**取；不要按文件行序覆盖（否则会取到更老的报告期，PB 偏高）
- **送转坑（2026-10-17 301608 实战）**：公司实施送转（如「10 转 4.9」，1 股→1.49 股）时，除权日不复权股价跳空下跌约 33%，而 F10 的 BPS 仍是除权前股本口径，PB 会出现假断崖。在 `SPLITS` 里登记 `(除权日, 因子)`（10 转 4.9 → 1.49），脚本自动折算。**两个指标方向相反**：PB 的 BPS 是"报告期股本口径"→ 除权日前的 BPS **÷F**；PS 的 `TOTAL_SHARE` 实测恒为"最新股本"→ 除权日前的 SPS **×F**（脚本用 `SHARE_IS_LATEST` 自动判别，勿手改）。送转数据用 `reportName=RPT_SHAREBONUS_DET&columns=ALL&filter=(SECUCODE=301608.SZ)` 查 `IT_RATIO`（送转比）、`EX_DIVIDEND_DATE`（除权日）、`PRETAX_BONUS_RMB`（派现）。
- **⚠️ 送转的反向陷阱：BPS 可能已按最新股本回溯折算 → `SPLITS` 应为空（2026-10-17 300072 实测）**。东财 F10 有时会把**历史全部期次的 BPS 统一按最新股本重算**，此时序列里已内含送转，再按除权日 ÷F 就是二次折算，会在除权日凭空造出假台阶。
  - **判别方法（必须实测，不能靠猜）**：取送转前一期，用 `BPS × 最新总股本` 反推权益，再与当期报表归母净资产比对。若 ≈ 权益 → 已按最新股本折算 → `SPLITS = []`；若 ≈ 权益 × F → 仍是旧股本口径 → 需登记 `SPLITS`。
  - 300072 实证：2025 中报 BPS 2.5282 × 23.497 亿股 = 59.41 亿元 = 当期权益 → 已折算；若按除权前 15.77 亿股应为 3.7671 元。故 `SPLITS=[]`，否则 05-20 处会造出 PB 2.72（真实 1.83）。
- **⚠️ 窗口起点事件校正（2026-10-17 300072 实测）**：`pageSize=24` 会混入报告期在五年窗口之外的旧期次。若不剔除，窗口起点前的几个交易日会退回到最早那条旧事件的每股值，画出一段与窗口内首期不连接的假台阶。脚本已自动处理：若窗口起点之前没有任何披露事件，则用"窗口起点前最后一条"作初始值（但仍需肉眼复核图左端是否平整）。
- **⚠️ 小数位**：通道倍数打印必须保留 2 位（`%.2f`）。用 `%.0f` 会让不同分位数显示成同一个数字（如 0.60/0.58 都印成"1x"），正文引用时极易出错。

## 持股机构数（2026-10-26 航天彩虹 002389 新增行实测）

- 东财 `RPT_MAIN_ORGHOLDDETAILS` 等「机构持股统计」报表名均不存在（code 9501），别再试。
- 可用口径：**报告期末十大流通股东中机构家数** —— `reportName=RPT_F10_EH_FREEHOLDERS`（columns=ALL，filter=(SECUCODE="...")，pageSize=200 一页即覆盖约 20 期×10 席），每行带 `IS_HOLDORG`（"1"=机构）与 `HOLDER_TYPE`，按季度末（3/30、6/30、9/30、12/31）筛选取 `IS_HOLDORG="1"` 计数。正文须注明口径为"前十大席位"，不代表全市场机构持仓总数。

## 同业选取坑（2026-10-26 实测）

- 观典防务（688287）**已退市**（行情名「退市观典」，价格 0.37 元），不能再作无人机同业；替代：洪都航空 600316（教练机/导弹整机）或航天电子 600879（航天无人系统）。

## 研报共识 / 资金流向 / 新品动态

优先用 **WebSearch**（带 `freshness` 参数取近期）：

- 券商研报共识：搜 `"{公司} 研报 目标价 盈利预测"`
- 资金流向 / 龙虎榜：搜 `"{公司} 主力资金 龙虎榜"`
- 新品 / 新订单：搜 `"{公司} 新品 订单 客户"`，这是第五章第 5 条的素材来源

**已知故障：** eastmoney 资金流向接口 `push2.eastmoney.com` / `push2his` / `push2delay` 会出现全线不可达（curl exit 56 / `RemoteDisconnected` / urllib `AttributeError`）。2026-09-27 实测：**连续高频请求 K 线接口也会触发临时限流**（编号域名 90/48/23.push2his 一并被掐），单票研报一次调用不触发；被掐后**等 60s 再试或先用腾讯备源，不要反复重试**。研报资金流向取不到时**直接用 WebSearch**。

港股无主力资金流数据 → 用成交量/成交额替代。
