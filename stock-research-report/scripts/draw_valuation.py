# -*- coding: utf-8 -*-
"""估值通道图（第九章末尾第 4 节，2026-09-27 用户新增，Step 3E；窗口近五年）

★ 估值指标选择（2026-10-17 用户定稿）：高成长科技公司用 PS，传统公司用 PB。
  判定规则见 references/data-sources.md「估值指标选择」；本脚本用 METRIC 常量显式指定。

★ 估值数据源（v1.2.1 用户定案 + v1.2.2 审计修复）：理杏仁为首选源。
  VAL_SOURCE 默认 "lixinger"（铁律 2）；不可用时按 data-sources.md「启用铁律」第 5 条
  自动降级到东财 F10 + 腾讯日 K 自建通道，并在控制台打印降级横幅与附录披露语句——
  禁止静默降级、禁止降级后仍引用理杏仁分位数。

★ 价格与每股值口径配对硬规则（v1.2.1 勘误，2026-11-04；替代旧「必须用不复权价」绝对禁令）：
  - 不复权价 ⟷ 当时股本口径每股值，或「最新股本口径每股值 + 除权日前 ×F 还原」——两路径等价
  - 前复权价 ⟷ 最新股本口径每股值，同样正确且序列更连续
  - 错误只发生在「口径不配对」（双重调整或漏调整），不在复权方式本身
  - 理杏仁 ps_ttm = 总市值/营收TTM，本身即市值口径：直接画通道，不得再乘价格、不得再做复权

口径（METRIC="PB"）：PB(t) = 当日收盘价 / 当期每股净资产 BPS（BPS 按披露日 NOTICE_DATE 阶梯切换）
口径（METRIC="PS"）：PS(t) = 当日收盘价 / 当期每股营收 SPS
- SPS = 营收 TTM / 总股本；营收 TTM = 上年全年 + 本期累计 - 上年同期累计（12/31 直接取全年）
- 亏损公司 PS 依然有效，这正是高成长科技公司用 PS 的原因
共同口径：
- 通道线 = 窗口内全部日指标的 0/20/40/60/80 分位倍数 × 当期每股值（阶梯线）
- 通道线含义：估值回到该历史分位时股价应处的水平；y 轴为股价尺度
- y 轴上下限按真实收盘价定（v1.2.2 修复：禁止 ks[-1]×max(ps_w) 极值通道抬高上限，
  否则高分位通道会把现价压进图幅下方 1/3）；超出图幅的通道线在图内标注不画线
- 窗口：近五年；数据不足五年时自动取上市以来全部历史并在标题/图注注明

数据准备（三条数据通道，换股票只改代码与文件名）：
  东财 F10 每股值序列（自建通道 / 交叉验证用）：
  curl -s "https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_F10_FINANCE_MAINFINADATA&columns=SECUCODE,REPORT_DATE,REPORT_DATE_NAME,NOTICE_DATE,BPS,TOTAL_SHARE,TOTALOPERATEREVE&filter=(SECUCODE%3D%22688235.SH%22)&sortColumns=REPORT_DATE&sortTypes=-1&pageSize=24&pageNumber=1&source=WEB&client=WEB" -H "User-Agent: Mozilla/5.0" -H "Referer: https://emweb.securities.eastmoney.com/" -o val_bps_688235.json
  腾讯日 K（收盘价序列；价格口径由 SPLITS 配对逻辑决定，见上方硬规则）：
  curl -s "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh688235,day,,,1500," -o val_k_688235.json
  理杏仁（首选源；token 只存环境变量 LIXINGER_TOKEN，禁止写入脚本/报告/日志——铁律 4；
  结果存独立文件 valuation_lixinger_688235.json，禁止回写 matrix_data.json / val_*.json——铁律 1）：
  POST https://open.lixinger.com/api/cn/company/fundamental/non_financial
  取 ps_ttm 日序列（metrics: ps_ttm；分位字段 fs.y5.q2v/q5v/q8v 供交叉验证）

用法：改下面常量后运行（需 numpy + matplotlib）。
"""
import json
import os
import datetime as dt

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "Noto Sans CJK SC", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

TITLE_NAME = "百济神州（688235.SH）"        # ← 改
OUT = "valuation_688235.png"                # ← 改
VAL_BPS_JSON = "val_bps_688235.json"        # ← 改（F10 BPS/营收/股本序列，pageSize=24）
VAL_K_JSON = "val_k_688235.json"            # ← 改（腾讯日 K，1500 根）
LIXINGER_JSON = "valuation_lixinger_688235.json"  # ← 改（理杏仁 ps_ttm 日序列独立文件，首选源）
LIXINGER_TOKEN_ENV = "LIXINGER_TOKEN"
METRIC = "PB"                               # ← 改："PB" = 市净率（传统公司）/ "PS" = 市销率（高成长科技公司）
# 估值数据源显式开关（data-sources.md 估值通道子域 · 铁律 2）：
#   "lixinger"  = 首选源（默认）；METRIC=PB 时未接入，自动降级
#   "eastmoney" = 备源自建通道（东财 F10 + 腾讯日 K + SPLITS 配对还原）
VAL_SOURCE = "lixinger"
QUANTILES = (0, 20, 40, 60, 80)
LINE_COLORS = ["#F5A623", "#B45AE0", "#35C4A2", "#4D9DF5", "#9AA3AE"]  # 上→下
# 送转复权：(除权日 "YYYY-MM-DD", 因子F)。
# 不填 = 不做处理（无送转的股票无需填）。示例：2026-05-20 实施 10 转 4.9 → ("2026-05-20", 1.49)
# 注意两者方向相反（实测东财 F10：BPS 是「报告期股本口径」，TOTAL_SHARE 是「最新股本口径」）：
#   PB → 除权日前的 BPS ÷F（折算到除权后股本口径，匹配已除权的价格）
#   PS → 若 TOTAL_SHARE 全序列为同一值（=最新股本），除权日前的 SPS ×F（还原到当时股本口径）
#   以上为「不复权价」路径的配对还原；若改用前复权价（val_k 取 qfqday），则配对最新股本口径
#   每股值、SPLITS 置空即可——见 docstring「价格与每股值口径配对硬规则」
SPLITS = []

METRIC = METRIC.upper()
assert METRIC in ("PB", "PS"), "METRIC 只能是 'PB' 或 'PS'"
assert VAL_SOURCE in ("lixinger", "eastmoney"), "VAL_SOURCE 只能是 'lixinger' 或 'eastmoney'"
METRIC_NAME = {"PB": "市净率 PB", "PS": "市销率 PS"}[METRIC]
PER_SHARE_NAME = {"PB": "每股净资产（BPS）", "PS": "每股营收（SPS，TTM）"}[METRIC]

# ---- 腾讯日 K（收盘价，两条数据源共用）----
kraw = json.load(open(VAL_K_JSON, encoding="utf-8"))["data"]
days = next(v.get("day") or v.get("qfqday") for v in kraw.values() if isinstance(v, dict))
dates = [dt.datetime.strptime(d[0], "%Y-%m-%d") for d in days]
closes = [float(d[2]) for d in days]

# ---- 东财 F10 每股值序列（自建通道主数据 / 理杏仁模式下作铁律 3 交叉验证）----
rows = json.load(open(VAL_BPS_JSON, encoding="utf-8"))["result"]["data"]

_by_rd = {(r.get("REPORT_DATE") or "")[:10]: r for r in rows if r.get("REPORT_DATE")}


def _cum_rev(rd: str):
    """报告期累计营业收入（元）；缺失返回 None。"""
    r = _by_rd.get(rd)
    if not r:
        return None
    v = r.get("TOTALOPERATEREVE")
    return float(v) if v is not None else None


def _ttm_rev(rd: str):
    """营收 TTM = 上年全年 + 本期累计 - 上年同期累计；12/31 直接取全年。"""
    y, md = int(rd[:4]), rd[5:]
    cur = _cum_rev(rd)
    if cur is None:
        return None
    if md == "12-31":
        return cur
    prev_annual = _cum_rev(f"{y - 1}-12-31")
    prev_same = _cum_rev(f"{y - 1}-{md}")
    if prev_annual is None or prev_same is None:
        return None
    return prev_annual + cur - prev_same


def _per_share_raw(r) -> float | None:
    """按指标取当期每股值（未做送转复权）。"""
    if METRIC == "PB":
        v = r.get("BPS")
        return float(v) if v is not None else None
    rd = (r.get("REPORT_DATE") or "")[:10]
    ttm = _ttm_rev(rd)
    sh = r.get("TOTAL_SHARE")
    if ttm is None or not sh:
        return None
    return ttm / float(sh)


# 东财 F10 的 TOTAL_SHARE 实测为「最新股本」统一值（不随报告期变化）；若序列有多个值则为时点股本
_share_vals = {r.get("TOTAL_SHARE") for r in rows if r.get("TOTAL_SHARE")}
SHARE_IS_LATEST = len(_share_vals) == 1

_ev = []
for r in rows:
    nd = (r.get("NOTICE_DATE") or "")[:10]
    ps = _per_share_raw(r)
    if nd and ps is not None and ps > 0:
        _ev.append((nd, ps, (r.get("REPORT_DATE") or "")[:10]))
if not _ev:
    raise SystemExit(f"没有可用的 {METRIC} 每股值（检查 JSON 是否含 BPS / TOTALOPERATEREVE / TOTAL_SHARE）")
# 同一披露日多期时保留报表期最晚的一条
_dedup = {}
for nd, ps, rd in _ev:
    if nd not in _dedup or rd > _dedup[nd][1]:
        _dedup[nd] = (ps, rd)
events = sorted([(nd, v[0], v[1]) for nd, v in _dedup.items()], key=lambda x: x[0])


def per_share_at(day_str: str) -> float:
    """东财自建口径：每股值按披露日阶梯 + SPLITS 口径配对还原。"""
    nd0, b, rd0 = events[0]
    for nd, v, rd in events:
        if nd <= day_str:
            nd0, b, rd0 = nd, v, rd
        else:
            break
    # 送转复权：把每股值折算到与当日价格同一股本口径
    for ex_date, f in SPLITS:
        if METRIC == "PB" or not SHARE_IS_LATEST:
            # BPS / 时点股本口径的 SPS = 报告期股本口径；当日价格已除权（缩至 1/F）→ ÷F
            if day_str >= ex_date and rd0 < ex_date:
                b = b / f
        else:
            # SPS 按「最新股本」算出；当日价格尚未除权（仍是旧口径）→ ×F 还原
            if day_str < ex_date:
                b = b * f
    return b


# ---- 窗口：近五年（历史超过五年时按自然日截取近五年；不足五年则取上市以来全部历史）----
span_years_all = (dates[-1] - dates[0]).days / 365.25
if span_years_all > 5.4:
    cutoff = dates[-1] - dt.timedelta(days=int(365.25 * 5))
    keep = [i for i, d in enumerate(dates) if d >= cutoff]
    d_w = [dates[i] for i in keep]
    closes_w = [closes[i] for i in keep]
    span_years = (d_w[-1] - d_w[0]).days / 365.25
    span_txt = "近五年"
else:
    keep = list(range(len(dates)))
    d_w, closes_w = dates, closes
    span_years = span_years_all
    span_txt = "上市以来"

# ---- 估值数据源裁决（data-sources.md 估值通道子域 · 铁律 2/5）----
_ACTUAL_SOURCE = VAL_SOURCE
_DEGRADE_REASON = None
_lx_by_date = {}

if VAL_SOURCE == "lixinger":
    if METRIC != "PS":
        _DEGRADE_REASON = "METRIC=%s 时理杏仁通道未接入（当前仅 PS 接入）" % METRIC
    elif not os.environ.get(LIXINGER_TOKEN_ENV):
        _DEGRADE_REASON = "未配置环境变量 %s" % LIXINGER_TOKEN_ENV
    elif not os.path.isfile(LIXINGER_JSON):
        _DEGRADE_REASON = "理杏仁取数文件缺失（%s）" % LIXINGER_JSON
    else:
        try:
            _lx = json.load(open(LIXINGER_JSON, encoding="utf-8"))
            _rows_lx = _lx.get("data") if isinstance(_lx, dict) else None
            if isinstance(_rows_lx, dict):   # 兼容 {data:{code:[...]}} 布局
                _rows_lx = next((v for v in _rows_lx.values() if isinstance(v, list)), None)
            if not isinstance(_rows_lx, list) or not _rows_lx:
                _DEGRADE_REASON = "理杏仁返回空数组或结构不符"
            else:
                for r in _rows_lx:
                    _d = r.get("date") or r.get("trade_date")
                    _v = r.get("ps_ttm")
                    if _d and _v is not None:
                        _lx_by_date[_d[:10]] = float(_v)
        except Exception as e:
            _DEGRADE_REASON = "理杏仁 JSON 解析失败：%s" % e
    if not _DEGRADE_REASON and _lx_by_date:
        # 铁律 5：数据起始晚于所需窗口 → 降级
        _first = min(_lx_by_date)
        _need = (dates[keep[0]] if keep else dates[0]).strftime("%Y-%m-%d")
        if _first > _need:
            _DEGRADE_REASON = "理杏仁数据起始（%s）晚于所需窗口（%s）" % (_first, _need)
    if not _lx_by_date and not _DEGRADE_REASON:
        _DEGRADE_REASON = "理杏仁序列无可用 ps_ttm 记录"
    if _DEGRADE_REASON:
        _ACTUAL_SOURCE = "eastmoney"
        print("=" * 66)
        print("[VAL_SOURCE 降级] 首选源理杏仁不可用 → 降级东财 F10 + 腾讯日 K 自建通道")
        print("  原因：%s" % _DEGRADE_REASON)
        print("  报告附录「数据来源与分级说明」必须写明（铁律 5，禁止静默降级）：")
        print("  「本次估值通道采用备源（东财 F10 + 腾讯不复权日 K），原因：%s；")
        print("   理杏仁为首选源，未取用」，并同步记入 meta.source。" % _DEGRADE_REASON)
        print("=" * 66)

# ---- 每股值序列（窗口内）----
if _ACTUAL_SOURCE == "lixinger":
    # 理杏仁 ps_ttm = 总市值/营收TTM（市值口径）：每股值 = 当日收盘价 / ps_ttm，
    # 已内含公司行动与股本事件对齐——直接派生，不得再乘价格、不得再做复权
    _lx_days = sorted(_lx_by_date)

    def per_share_lx(day_str: str) -> float | None:
        v = _lx_by_date.get(day_str)
        if v is None:   # 休市日对齐：取窗口内不晚于该日的最近一个理杏仁交易日
            import bisect
            i = bisect.bisect_right(_lx_days, day_str) - 1
            v = _lx_by_date[_lx_days[i]] if i >= 0 else None
        return v

    ps_w = [per_share_lx(days[i][0]) for i in keep]
    _miss = [i for i, v in enumerate(ps_w) if v is None or v <= 0]
    if _miss:   # 序列前段超出理杏仁覆盖 → 缩窗到理杏仁覆盖范围
        _start = _miss[-1] + 1
        d_w, closes_w, ps_w = d_w[_start:], closes_w[_start:], ps_w[_start:]
        keep = keep[_start:]
        if len(d_w) < 250:
            raise SystemExit("理杏仁覆盖窗口不足一年，请检查 %s" % LIXINGER_JSON)
else:
    ps_w = [per_share_at(days[i][0]) for i in keep]

vals_full = [c / b for c, b in zip(closes_w, ps_w)]
ks = [float(np.percentile(vals_full, p)) for p in QUANTILES]

FS = 10.5          # 脚本字号；9.0in / dpi180 → scale 0.700 → 进版心 7.35pt
DPI = 180
fig, ax = plt.subplots(figsize=(9.0, 5.3), dpi=DPI)

# 可读性修复（v1.2.2）：y 轴上下限按真实股价定，禁止用 ks[-1]×max(ps_w) 极值通道抬高上限
price_hi = max(closes_w)
hi = price_hi * 1.15
lo = min(closes_w) * 0.85
ax.set_ylim(lo, hi)

ax.plot(d_w, closes_w, color="#3B6FF0", lw=1.5, label="收盘价", zorder=5)

over = []
for k, color in zip(ks, LINE_COLORS):
    top = k * ps_w[-1]
    if top <= hi:
        ax.plot(d_w, [k * b for b in ps_w], color=color, lw=1.3,
                drawstyle="steps-post", label=f"{METRIC} {k:.1f}x", zorder=3)
    else:
        over.append(top)

ax.set_title(f"{TITLE_NAME}{span_txt}估值通道：{METRIC_NAME}", fontsize=12, pad=10)
ax.grid(axis="y", ls="--", alpha=0.25)
ax.set_ylabel("股价（元）", fontsize=FS)

n_ticks = 5
idx = [int(round(i * (len(d_w) - 1) / (n_ticks - 1))) for i in range(n_ticks)]
ax.set_xticks([d_w[i] for i in idx])
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
ax.tick_params(axis="both", labelsize=FS)

if over:
    ax.text(0.985, 0.955, "高分位通道 %s 元超出图幅" %
            "/".join("%.0f" % v for v in over),
            transform=ax.transAxes, ha="right", va="top",
            fontsize=FS, color="#8A8F98",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#DDDDDD", alpha=0.9))

ax.legend(loc="upper left", fontsize=FS, ncol=2, frameon=False)
v_now = closes_w[-1] / ps_w[-1]
pos = sum(1 for v in vals_full if v <= v_now) / len(vals_full) * 100
_src_note = ("理杏仁 ps_ttm（市值口径，首选源）" if _ACTUAL_SOURCE == "lixinger"
             else "东财 F10、腾讯行情（价格与每股值口径按配对硬规则还原）")
fig.text(0.012, 0.012,
         f"注：通道线＝{span_txt}（{d_w[0]:%Y-%m-%d} 起 {len(d_w)} 个交易日）{METRIC} 分位×当期每股值，"
         f"即该分位对应股价；现价 {closes_w[-1]:.2f} 元＝{METRIC} {v_now:.1f}x，处 {pos:.0f}% 分位。\n"
         f"来源：{_src_note}。",
         fontsize=FS, color="#8A8F98", va="bottom")
fig.subplots_adjust(left=0.105, right=0.985, top=0.90, bottom=0.16)
fig.savefig(OUT, dpi=DPI, facecolor="white")
print("saved:", OUT, "| metric:", METRIC, "| source:", _ACTUAL_SOURCE)

# 铁律 3 · 双源交叉验证：理杏仁模式下仍计算一次东财自建 PS，>5% 须以理杏仁为准并在附录披露差异
if _ACTUAL_SOURCE == "lixinger":
    try:
        _self_ps = closes_w[-1] / per_share_at(days[keep[-1]][0])
        _diff = abs(_self_ps - v_now) / v_now * 100
        print("[铁律3 交叉验证] 理杏仁 ps_ttm=%.2f | 自建 PS=%.2f | 相对差异 %.2f%%"
              % (v_now, _self_ps, _diff))
        if _diff > 5:
            print("[铁律3] 差异>5%%：以理杏仁为准，报告附录 MUST 披露差异值与自建口径结果，不得静默替换")
    except Exception as e:
        print("[铁律3 交叉验证] 自建通道计算失败（%s），附录须注明仅单源" % e)

if METRIC == "PS":
    print("share basis:", "最新股本（除权日前需 ×F 还原）" if SHARE_IS_LATEST else "时点股本")
print("span:", span_txt, "(%.2fy, %d days)" % (span_years, len(d_w)))
print("%s range: %.2f ~ %.2f | now %.2f (%.0f%% pct)" % (METRIC, min(vals_full), max(vals_full), v_now, pos))
print("quantile ks(0/20/40/60/80):", ["%.2f" % k for k in ks])
print("channel price now:", ["%.0f" % (k * b) for k, b in zip(ks, [ps_w[-1]] * len(ks))],
      "| %s now = %.4f" % (PER_SHARE_NAME.split("（")[0], ps_w[-1]))
# 正文引用所需：极值日期与对应收盘价（写解读段前必须核实）
vr = [(closes_w[i] / ps_w[i], d_w[i].strftime("%Y-%m-%d"), closes_w[i]) for i in range(len(d_w))]
print("%s max: %.2fx on %s close=%.2f" % ((METRIC,) + max(vr)))
print("%s min: %.2fx on %s close=%.2f" % ((METRIC,) + min(vr)))
