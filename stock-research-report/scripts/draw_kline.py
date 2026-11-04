# -*- coding: utf-8 -*-
"""A 股个股近一年日 K 线图 —— 用户定稿规格。

用法：只改下面「配置区」5 个常量即可，其余不动。

规格（勿改）：
  · 窗口只取近 1 年（245 个交易日），上市不足 1 年则取全历史
  · 均线 MA5 / MA20 / MA60 / MA240（MA240 替代 MA250）
  · MA60 分段着色：向上红、向下绿
  · 倍量阳线（收阳 且 量 ≥ 前日 ×2）黄色实体 FFD400 + 金边 E6A700
  · 红涨绿跌；量轴万手、P99 截断
  · 图幅 15.75 × 8.6，height_ratios [3.4, 1]，K 线实体宽 0.68

数据来源：腾讯 fqkline 接口，JSON 存为 data/kline_{code}.json
  curl -s "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz002536,day,,,490,qfq"
"""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
import matplotlib.font_manager as fm
import numpy as np

# ============ 配置区（只改这里） ============
CODE_QT = "sz002536"                                        # 腾讯备源接口代码，如 sz002536 / sh600685
CODE_KEY = "sz002536"                                       # 腾讯 JSON 内 data 下的键名（东财主源无需此键）
TITLE = "飞龙股份（002536.SZ）近一年日K线"                     # 图标题
YLABEL = "价格（元，前复权）"
VLABEL = "成交量（万股）"
SRC = "data/kline_002536.json"
OUT = "data/kline_002536.png"
WIN = 245                                                   # 窗口交易日数；上市不足则自动取全历史
IS_HK = False                                               # 港股改 True（量单位与接口键不同）
# ==========================================

for name in ["Microsoft YaHei", "SimHei", "SimSun", "Noto Sans CJK SC", "DejaVu Sans"]:
    try:
        fm.findfont(fm.FontProperties(family=name), fallback_to_default=False)
        plt.rcParams["font.sans-serif"] = [name]
        break
    except Exception:
        continue
plt.rcParams["axes.unicode_minus"] = False

RED = "#C0392B"
GREEN = "#00913F"
YELLOW = "#FFD400"
YELLOW_EDGE = "#E6A700"
GRAY = "#8C8C8C"

raw = json.load(open(SRC, encoding="utf-8"))


def _load_bars(raw):
    """兼容两种来源（列统一为 [日期, 开, 收, 高, 低, 量(股)]）：
    1) 腾讯 fqkline（主源 qfq，2026-11-04 定稿首选即主源）：data.{code}.qfqday / hkfqkline / day
    2) 东财 push2his kline（备源 fqt=1 前复权，仅腾讯失败时用一次）：
       data.klines = ["2025-01-02,开,收,高,低,量(手),额,振幅,涨跌幅,涨跌额,换手", ...]
       注意东财列序为 开,收,高,低；量单位为手，×100 换算成股与腾讯口径对齐。
    """
    data = raw.get("data") or {}
    if isinstance(data, dict) and data.get("klines"):
        rows = []
        for line in data["klines"]:
            p = line.split(",")
            rows.append([p[0], p[1], p[2], p[3], p[4], str(float(p[5]) * 100)])
        return rows
    node = data.get(CODE_KEY, data)
    bars = node.get("hkfqkline") if IS_HK else node.get("qfqday")
    if bars is None:  # 兼容部分返回结构
        for k in ("qfqday", "hkfqkline", "day"):
            if k in node:
                bars = node[k]
                break
    return bars


bars_all = _load_bars(raw)

FULL_HISTORY = len(bars_all) <= WIN
bars = bars_all[-WIN:] if not FULL_HISTORY else bars_all
dates = [b[0] for b in bars]
O = np.array([float(b[1]) for b in bars])
C = np.array([float(b[2]) for b in bars])
H = np.array([float(b[3]) for b in bars])
L = np.array([float(b[4]) for b in bars])
V = np.array([float(b[5]) for b in bars])
n = len(bars)
idx = np.arange(n)


def ma(arr, w):
    out = np.full(len(arr), np.nan)
    if len(arr) >= w:
        cs = np.cumsum(arr)
        out[w - 1:] = (cs[w - 1:] - np.concatenate([[0], cs[:-w]])) / w
    return out


# 均线用全量数据计算后截取窗口，保证 MA240 起点即有值
C_all = np.array([float(b[2]) for b in bars_all])
ma5 = ma(C_all, 5)[-n:]
ma20 = ma(C_all, 20)[-n:]
ma60 = ma(C_all, 60)[-n:]
ma240 = ma(C_all, 240)[-n:] if len(bars_all) >= 240 else np.full(n, np.nan)

is_bull = C > O
vol_double = np.zeros(n, dtype=bool)
for i in range(1, n):
    if V[i - 1] > 0 and V[i] >= V[i - 1] * 2:
        vol_double[i] = True
star = is_bull & vol_double
star_idx = np.where(star)[0]

fig = plt.figure(figsize=(15.75, 8.6), dpi=100)
gs = fig.add_gridspec(2, 1, height_ratios=[3.4, 1], hspace=0.07,
                      left=0.055, right=0.985, top=0.94, bottom=0.08)
ax = fig.add_subplot(gs[0])
axv = fig.add_subplot(gs[1], sharex=ax)

body_w = 0.68
for i in range(n):
    up = C[i] >= O[i]
    if star[i]:
        fc, ec = YELLOW, YELLOW_EDGE
    else:
        fc, ec = (RED, RED) if up else (GREEN, GREEN)
    lo, hi = min(O[i], C[i]), max(O[i], C[i])
    h = max(hi - lo, 1e-4)
    ax.add_patch(Rectangle((i - body_w / 2, lo), body_w, h,
                           facecolor=fc, edgecolor=ec, linewidth=0.7, zorder=3))
    ax.plot([i, i], [L[i], lo], color=ec, linewidth=0.7, zorder=2)
    ax.plot([i, i], [hi, H[i]], color=ec, linewidth=0.7, zorder=2)

ax.plot(idx, ma5, color="#E67E22", lw=1.1, zorder=4)
ax.plot(idx, ma20, color="#2E86C1", lw=1.1, zorder=4)
for i in range(1, n):
    if np.isnan(ma60[i]) or np.isnan(ma60[i - 1]):
        continue
    c = RED if ma60[i] >= ma60[i - 1] else GREEN
    ax.plot([i - 1, i], [ma60[i - 1], ma60[i]], color=c, lw=1.6, zorder=6,
            solid_capstyle="round")
ax.plot(idx, ma240, color="#7D3C98", lw=1.4, zorder=5)

if len(star_idx):
    ax.scatter(star_idx, C[star_idx] * 1.015, marker="^", s=42,
               facecolor=YELLOW, edgecolor=YELLOW_EDGE, linewidth=0.8, zorder=8)

handles = [
    Line2D([], [], color="#E67E22", lw=1.4, label="MA5"),
    Line2D([], [], color="#2E86C1", lw=1.4, label="MA20"),
    Line2D([], [], color=RED, lw=1.8, label="MA60（向上为红）"),
    Line2D([], [], color=GREEN, lw=1.8, label="MA60（向下为绿）"),
    Line2D([], [], color="#7D3C98", lw=1.4, label="MA240"),
    Line2D([], [], marker="s", color="none", markerfacecolor=YELLOW,
           markeredgecolor=YELLOW_EDGE, markersize=9, label="倍量阳线"),
]
ax.legend(handles=handles, loc="upper right", fontsize=9, ncol=3,
          framealpha=0.92, borderpad=0.5, columnspacing=1.2)

win_txt = "上市以来" if FULL_HISTORY else "近一年"
ax.set_title(f"{TITLE}　{win_txt}　红涨绿跌 · 倍量阳线黄色标注 · MA240 替代 MA250",
             fontsize=14, fontweight="bold", pad=12)
ax.set_ylabel(YLABEL, fontsize=10.5)
ax.grid(True, alpha=0.22, linestyle="--", linewidth=0.6)
ax.set_axisbelow(True)

last_close = C[-1]
ax.axhline(last_close, color=GRAY, lw=0.9, linestyle=":", zorder=1)
ax.annotate(f"最新 {last_close:.2f}（{dates[-1]}）",
            xy=(n - 1, last_close), xytext=(n - 1 - 46, last_close * 1.06),
            fontsize=9, color=GRAY,
            arrowprops=dict(arrowstyle="->", color=GRAY, lw=0.9))

VW = V / 1e4
for i in range(n):
    up = C[i] >= O[i]
    col = YELLOW if star[i] else (RED if up else GREEN)
    axv.bar(i, VW[i], width=body_w, color=col, edgecolor=col, linewidth=0.4)
axv.set_ylabel(VLABEL, fontsize=10)
axv.grid(True, alpha=0.22, linestyle="--", linewidth=0.6)
axv.set_axisbelow(True)
axv.set_ylim(0, np.nanpercentile(VW, 99) * 1.15)

ticks, labels = [], []
prev_m = None
for i, d in enumerate(dates):
    m = d[:7]
    if m != prev_m:
        ticks.append(i)
        labels.append(d[2:7].replace("-", "/"))
        prev_m = m
ax.set_xticks(ticks)
ax.set_xticklabels([])
axv.set_xticks(ticks)
axv.set_xticklabels(labels, fontsize=8.5)
axv.set_xlim(-1.5, n + 0.5)

lo_all, hi_all = np.nanmin(L), np.nanmax(H)
pad = (hi_all - lo_all) * 0.08
ax.set_ylim(lo_all - pad, hi_all + pad * 1.5)

fig.savefig(OUT, dpi=100, facecolor="white")
print("saved", OUT)
print("窗口:", win_txt, "| 交易日:", n)
print("倍量阳线数量:", len(star_idx))
for i in star_idx[-12:]:
    print(f"  {dates[i]}  量比 {V[i]/V[i-1]:.2f}x  收 {C[i]:.2f}")
print("\n>>> 提醒：正文中「近一年共 X 根倍量阳线」的统计数字必须与上面的数量一致 <<<")
