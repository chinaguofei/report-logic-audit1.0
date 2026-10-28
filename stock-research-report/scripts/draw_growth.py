# -*- coding: utf-8 -*-
"""第四章矩阵下方的「同比变化率折线图」—— 用户定稿规格（2026-09-10 新增）。

用法：只改下面「配置区」常量，其余不动。

规格（勿改）：
  · 两条折线：营收同比(%)、归母同比(%)，横轴为矩阵相同的 16 个季度（时间正序，早→晚）
  · 0 轴上下分区着色：线上方（正值）用红 C0392B，线下方（负值）用绿 00913F
  · 0 轴加水平实线；分区底纹淡红/淡绿，直观区分正负增长
  · 数据点按所属区间着色（正红负绿），末点标注最新数值
  · 图幅 15.75 × 5.2，与 K 线图同为白底、主题蓝标题、微软雅黑
  · 单位 %，图例含"营收同比 / 归母同比"

数据来源：与第四章矩阵同源（公司定期报告，东方财富 F10 整理）。
数值以字符串传入，支持 "<r>…</r>" 之类内联标记的原文需先在数据区去掉，只留纯数值。
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import matplotlib.font_manager as fm
import numpy as np

# ============ 配置区（只改这里） ============
TITLE = "飞龙股份（002536.SZ）单季度营收与归母同比增速（2022Q3–2026Q2）"
OUT = "data/growth_002536.png"
# 16 个季度，时间正序（与矩阵表左右相反，矩阵是最新在左）
PERIODS = ["22Q3", "22Q4", "23Q1", "23Q2", "23Q3", "23Q4",
           "24Q1", "24Q2", "24Q3", "24Q4",
           "25Q1", "25Q2", "25Q3", "25Q4",
           "26Q1", "26Q2"]
# 与矩阵「营收同比」行一致的数值（%），None 表示缺失/不适用
REV_YOY = [None] * 16
# 与矩阵「归母同比」行一致的数值（%），None 表示缺失/不适用
PROFIT_YOY = [None] * 16
# 是否在图上标注每条线的最新值
LABEL_LAST = True
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
RED_BG = "#FDECEA"
GREEN_BG = "#E9F7EF"
BLUE = "#185FA5"
GRAY = "#8C8C8C"

if REV_YOY == [None] * 16 or PROFIT_YOY == [None] * 16:
    raise SystemExit("请先在配置区填入 REV_YOY / PROFIT_YOY 的真实数值")

n = len(PERIODS)
idx = np.arange(n)


def series(vals):
    """把 None 转成 NaN，返回 (x有效索引, y有效值)"""
    arr = np.array([np.nan if v is None else float(v) for v in vals])
    ok = ~np.isnan(arr)
    return idx[ok], arr[ok], arr


rev_x, rev_y, rev_arr = series(REV_YOY)
prf_x, prf_y, prf_arr = series(PROFIT_YOY)

fig, ax = plt.subplots(figsize=(15.75, 5.2), dpi=100)
fig.subplots_adjust(left=0.062, right=0.985, top=0.88, bottom=0.14)

# —— 0 轴上下分区底纹 ——
ymax = max(np.nanmax(rev_arr), np.nanmax(prf_arr))
ymin = min(np.nanmin(rev_arr), np.nanmin(prf_arr))
span = max(abs(ymax), abs(ymin), 1.0)
top = span * 1.28
bot = -span * 1.28
ax.axhspan(0, top, facecolor=RED_BG, alpha=0.55, zorder=0)
ax.axhspan(bot, 0, facecolor=GREEN_BG, alpha=0.55, zorder=0)
ax.axhline(0, color="#333333", lw=1.2, zorder=2)

# —— 两条折线：按区间分段着色（正红负绿）——
# 营收同比 = 实线（粗），归母同比 = 虚线（略细），便于区分
for x, y, is_rev in ((rev_x, rev_y, True), (prf_x, prf_y, False)):
    lw = 2.4 if is_rev else 2.0
    ls = "-" if is_rev else "--"
    for i in range(len(x) - 1):
        seg_c = RED if (y[i] + y[i + 1]) / 2 >= 0 else GREEN
        ax.plot(x[i:i + 2], y[i:i + 2], color=seg_c, lw=lw, ls=ls,
                solid_capstyle="round", zorder=4)
    # 数据点同样正红负绿
    ax.scatter(x, y, s=34, zorder=5,
               c=[RED if v >= 0 else GREEN for v in y],
               edgecolors="white", linewidths=0.8)

# —— 最新值标注 ——
if LABEL_LAST and len(rev_x):
    i = rev_x[-1]
    ax.annotate(f"{rev_y[-1]:+.1f}%", xy=(i, rev_y[-1]),
                xytext=(i - 1.6, rev_y[-1] + span * 0.16), fontsize=9.5,
                color=RED if rev_y[-1] >= 0 else GREEN, fontweight="bold")
if LABEL_LAST and len(prf_x):
    i = prf_x[-1]
    ax.annotate(f"{prf_y[-1]:+.1f}%", xy=(i, prf_y[-1]),
                xytext=(i - 1.6, prf_y[-1] - span * 0.22), fontsize=9.5,
                color=RED if prf_y[-1] >= 0 else GREEN, fontweight="bold")

ax.set_title(f"{TITLE}　红线 = 正增长 · 绿线 = 负增长", fontsize=14,
             fontweight="bold", pad=12, color="#1A1A1A")
ax.set_ylabel("同比增速（%）", fontsize=10.5, color="#333333")
ax.set_xlim(-0.8, n - 0.2)
ax.set_ylim(bot, top)
ax.set_xticks(idx)
ax.set_xticklabels(PERIODS, fontsize=9)
ax.tick_params(axis="y", labelsize=9)
ax.grid(True, axis="y", alpha=0.25, linestyle="--", linewidth=0.6, zorder=1)
ax.set_axisbelow(True)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)

handles = [
    Line2D([], [], color=RED, lw=2.6, label="营收同比（正）"),
    Line2D([], [], color=GREEN, lw=2.6, label="营收同比（负）"),
    Line2D([], [], color=RED, lw=2.2, ls="--", label="归母同比（正）"),
    Line2D([], [], color=GREEN, lw=2.2, ls="--", label="归母同比（负）"),
]
ax.legend(handles=handles, loc="upper left", fontsize=9, ncol=2,
          framealpha=0.92, borderpad=0.5, columnspacing=1.4)

fig.savefig(OUT, dpi=100, facecolor="white")
print("saved", OUT)
print("区间:", PERIODS[0], "→", PERIODS[-1], "| 季度数:", n)
print("营收同比:", ["—" if v is None else f"{v:+.1f}" for v in REV_YOY])
print("归母同比:", ["—" if v is None else f"{v:+.1f}" for v in PROFIT_YOY])
print("\n>>> 提醒：正文「矩阵表解读」中涉及增速方向的表述须与本图一致 <<<")
