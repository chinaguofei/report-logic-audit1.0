# -*- coding: utf-8 -*-
"""估值通道图（第九章末尾第 4 节，2026-09-27 用户新增，Step 3E；窗口近五年）

★ 估值指标选择（2026-10-17 用户定稿）：高成长科技公司用 PS，传统公司用 PB。
  判定规则见 references/data-sources.md「估值指标选择」；本脚本用 METRIC 常量显式指定。

口径（METRIC="PB"）：
- PB(t) = 当日收盘价(不复权) / 当期每股净资产 BPS（BPS 按披露日 NOTICE_DATE 阶梯切换）
口径（METRIC="PS"）：
- PS(t) = 当日收盘价(不复权) / 当期每股营收 SPS
- SPS = 营收 TTM / 总股本；营收 TTM = 上年全年 + 本期累计 - 上年同期累计（12/31 直接取全年）
- 亏损公司 PS 依然有效，这正是高成长科技公司用 PS 的原因
共同口径：
- 通道线 = 窗口内全部日指标的 0/20/40/60/80 分位倍数 × 当期每股值（阶梯线）
- 通道线含义：估值回到该历史分位时股价应处的水平；y 轴为股价尺度
- 窗口：近五年；数据不足五年时自动取上市以来全部历史并在标题/图注注明

数据准备（两条 curl，换股票只改代码与文件名）：
  curl -s "https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_F10_FINANCE_MAINFINADATA&columns=SECUCODE,REPORT_DATE,REPORT_DATE_NAME,NOTICE_DATE,BPS,TOTAL_SHARE,TOTALOPERATEREVE&filter=(SECUCODE%3D%22688235.SH%22)&sortColumns=REPORT_DATE&sortTypes=-1&pageSize=24&pageNumber=1&source=WEB&client=WEB" -H "User-Agent: Mozilla/5.0" -H "Referer: https://emweb.securities.eastmoney.com/" -o val_bps_688235.json
  curl -s "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh688235,day,,,1500," -o val_k_688235.json

用法：改下面 5 个常量后运行（需 numpy + matplotlib）。
"""
import json
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
VAL_K_JSON = "val_k_688235.json"            # ← 改（不复权日 K，1500 根）
METRIC = "PB"                               # ← 改："PB" = 市净率（传统公司）/ "PS" = 市销率（高成长科技公司）
QUANTILES = (0, 20, 40, 60, 80)
LINE_COLORS = ["#F5A623", "#B45AE0", "#35C4A2", "#4D9DF5", "#9AA3AE"]  # 上→下
# 送转复权：(除权日 "YYYY-MM-DD", 因子F)。
# 不填 = 不做处理（无送转的股票无需填）。示例：2026-05-20 实施 10 转 4.9 → ("2026-05-20", 1.49)
# 注意两者方向相反（实测东财 F10：BPS 是「报告期股本口径」，TOTAL_SHARE 是「最新股本口径」）：
#   PB → 除权日前的 BPS ÷F（折算到除权后股本口径，匹配已除权的价格）
#   PS → 若 TOTAL_SHARE 全序列为同一值（=最新股本），除权日前的 SPS ×F（还原到当时股本口径）
SPLITS = []

METRIC = METRIC.upper()
assert METRIC in ("PB", "PS"), "METRIC 只能是 'PB' 或 'PS'"
METRIC_NAME = {"PB": "市净率 PB", "PS": "市销率 PS"}[METRIC]
PER_SHARE_NAME = {"PB": "每股净资产（BPS）", "PS": "每股营收（SPS，TTM）"}[METRIC]

# ---- 数据 ----
rows = json.load(open(VAL_BPS_JSON, encoding="utf-8"))["result"]["data"]
kraw = json.load(open(VAL_K_JSON, encoding="utf-8"))["data"]
days = next(v.get("day") or v.get("qfqday") for v in kraw.values() if isinstance(v, dict))

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

dates = [dt.datetime.strptime(d[0], "%Y-%m-%d") for d in days]
closes = [float(d[2]) for d in days]


def per_share_at(day_str: str) -> float:
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


span_years_all = (dates[-1] - dates[0]).days / 365.25
# 窗口：近五年（历史超过五年时按自然日截取近五年；不足五年则取上市以来全部历史）
if span_years_all > 5.4:
    cutoff = dates[-1] - dt.timedelta(days=int(365.25 * 5))
    keep = [i for i, d in enumerate(dates) if d >= cutoff]
    d_w = [dates[i] for i in keep]
    closes_w = [closes[i] for i in keep]
    ps_w = [per_share_at(days[i][0]) for i in keep]
    span_years = (d_w[-1] - d_w[0]).days / 365.25
    span_txt = "近五年"
else:
    d_w, closes_w = dates, closes
    ps_w = [per_share_at(d[0]) for d in days]
    span_years = span_years_all
    span_txt = "上市以来"

vals_full = [c / b for c, b in zip(closes_w, ps_w)]
ks = [float(np.percentile(vals_full, p)) for p in QUANTILES]

fig, ax = plt.subplots(figsize=(15.75, 5.6), dpi=150)
ax.plot(d_w, closes_w, color="#3B6FF0", lw=1.4, label="收盘价", zorder=5)

for k, color in zip(ks, LINE_COLORS):
    ax.plot(d_w, [k * b for b in ps_w], color=color, lw=1.2,
            drawstyle="steps-post", label=f"{METRIC} {k:.1f}x", zorder=3)

ax.set_title(f"{TITLE_NAME}{span_txt}估值通道：{METRIC_NAME}", fontsize=14, pad=12)
ax.grid(axis="y", ls="--", alpha=0.25)
lo = min(min(closes_w), ks[0] * max(ps_w))
hi = max(max(closes_w), ks[-1] * max(ps_w))
ax.set_ylim(lo * 0.88, hi * 1.10)
ax.set_ylabel("股价（元）", fontsize=10)

n_ticks = 5
idx = [int(round(i * (len(d_w) - 1) / (n_ticks - 1))) for i in range(n_ticks)]
ax.set_xticks([d_w[i] for i in idx])
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
ax.tick_params(axis="both", labelsize=9)

ax.legend(loc="upper left", fontsize=9, ncol=6, frameon=False)
v_now = closes_w[-1] / ps_w[-1]
pos = sum(1 for v in vals_full if v <= v_now) / len(vals_full) * 100
fig.text(0.01, 0.015,
         f"注：通道线={span_txt}（{d_w[0]:%Y-%m-%d} 起 {len(d_w)} 个交易日）日 {METRIC} 的 0/20/40/60/80 分位倍数×当期{PER_SHARE_NAME}，"
         f"即估值回到该历史分位对应的股价水平；图例为各通道对应 {METRIC} 倍数。当前价 {closes_w[-1]:.2f} 元对应 {METRIC} {v_now:.1f}x，"
         f"处于{span_txt}{METRIC} 区间的 {pos:.0f}% 分位。\n"
         "数据来源：东方财富 F10（每股净资产 / 营业收入 / 总股本及披露日）、腾讯行情（不复权收盘价）。",
         fontsize=7.5, color="#8A8F98", va="bottom")
fig.subplots_adjust(left=0.055, right=0.99, top=0.90, bottom=0.17)
fig.savefig(OUT, facecolor="white")
print("saved:", OUT, "| metric:", METRIC)
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
