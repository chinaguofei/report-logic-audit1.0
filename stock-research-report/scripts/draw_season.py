# -*- coding: utf-8 -*-
# ⚠ 本文件是技能模板，文件内示例数据为「海目星 688559」，使用前必须整体替换配置区。
# 用途：图10 季节性拆解（左：单季营收 Q4 高亮；右：月度平均收益）
# 用法：复制到 data/ 后改名 draw_xxx_{code}.py，改配置区常量与 OUT 文件名，再运行。
# 规格：图注必须写清「口径 + 数据源等级（A/B/C/D）」，见 references/chapter-spec.md
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

OUT = "season_688559.png"

# ── 配置区 ────────────────────────────────────────────
TITLE = "季节性拆解：收入旺季在 Q4，股价没有稳定的「旺季」"
NOTE = "口径：单季营收＝定期报告累计值差分（2021Q1–2026Q2，A 类）；月度收益＝前复权月末收盘环比（2021-06–2026-10）；D 类自算，n=5~6 样本短，仅作节奏参考"

QUARTERS = ["21Q1", "21Q2", "21Q3", "21Q4", "22Q1", "22Q2", "22Q3", "22Q4",
            "23Q1", "23Q2", "23Q3", "23Q4", "24Q1", "24Q2", "24Q3", "24Q4",
            "25Q1", "25Q2", "25Q3", "25Q4", "26Q1", "26Q2"]
REV = [1.26, 4.26, 4.74, 9.58, 4.47, 7.48, 11.76, 17.35,
       8.95, 12.51, 12.15, 14.43, 10.48, 13.47, 12.33, 8.97,
       5.39, 11.26, 10.39, 15.13, 13.17, 17.56]
Q4_IDX = [3, 7, 11, 15, 19]
Q4_TXT = ["9.6", "17.4", "14.4", "9.0", "15.1"]

MONTHS = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"]
MRET = [-4.84, 4.39, -0.61, -3.38, 5.06, 15.92, 18.84, -1.19, 4.30, -5.38, 4.44, -7.13]
MRET_TXT = ["-4.8%", "+4.4%", "-0.6%", "-3.4%", "+5.1%", "+15.9%",
            "+18.8%", "-1.2%", "+4.3%", "-5.4%", "+4.4%", "-7.1%"]
WIN = ["2/5", "3/5", "2/5", "1/5", "3/5", "4/5", "2/6", "2/6", "4/6", "3/6", "3/5", "1/5"]
# ─────────────────────────────────────────────────────

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
BLUE_L = "#9DB9DA"
GRAY = "#8C8C8C"
DARK = "#1A1A1A"

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.75, 4.9), dpi=100,
                               gridspec_kw={"width_ratios": [1.45, 1]})
fig.subplots_adjust(left=0.058, right=0.982, top=0.755, bottom=0.20, wspace=0.20)

# ── 左：单季营收，Q4 高亮 ──
x = np.arange(len(QUARTERS))
colors = [RED if i in Q4_IDX else BLUE_L for i in x]
ax1.bar(x, REV, color=colors, width=0.66, zorder=3)
for i, t in zip(Q4_IDX, Q4_TXT):
    ax1.text(i, REV[i] + 0.45, t, ha="center", va="bottom",
             fontsize=9, color=RED, fontweight="bold")
ax1.set_xticks(x)
ax1.set_xticklabels(QUARTERS, fontsize=8, rotation=0)
ax1.set_ylim(0, max(REV) * 1.30)
ax1.set_ylabel("单季营业收入（亿元）", fontsize=9.5, color="#333333")
ax1.set_title("Q4 平均占全年 35.3%（区间 19.8%–48.3%），Q4/Q1 = 2.45 倍",
              fontsize=10.5, fontweight="bold", color=RED, pad=8, loc="left")
ax1.grid(True, axis="y", alpha=0.25, ls="--", lw=0.6, zorder=0)
ax1.set_axisbelow(True)
for s in ("top", "right"):
    ax1.spines[s].set_visible(False)
ax1.annotate("24Q4 旺季失效：\n单季 9.0 亿、环比 -27%",
             xy=(15, 8.97), xytext=(12.1, 19.4), fontsize=8.6, color=GREEN,
             arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.0,
                             connectionstyle="arc3,rad=-0.18"))

# ── 右：月度平均收益 ──
xm = np.arange(len(MONTHS))
mc = [RED if v > 0 else GREEN for v in MRET]
ax2.bar(xm, MRET, color=mc, width=0.62, zorder=3)
for i, (v, t) in enumerate(zip(MRET, MRET_TXT)):
    ax2.text(i, v + (0.75 if v > 0 else -0.75), t, ha="center",
             va="bottom" if v > 0 else "top", fontsize=8.2,
             color=RED if v > 0 else GREEN)
ax2.axhline(0, color="#555555", lw=0.9, zorder=4)
ax2.set_xticks(xm)
ax2.set_xticklabels([f"{m}\n{w}" for m, w in zip(MONTHS, WIN)], fontsize=8)
ax2.set_ylim(min(MRET) * 1.42, max(MRET) * 1.42)
ax2.set_ylabel("月度平均收益率（%）", fontsize=9.5, color="#333333")
ax2.set_title("12 个月平均收益：6 月 +15.9% 最高，全年无单调旺季",
              fontsize=10.5, fontweight="bold", color=DARK, pad=8, loc="left")
ax2.grid(True, axis="y", alpha=0.25, ls="--", lw=0.6, zorder=0)
ax2.set_axisbelow(True)
for s in ("top", "right"):
    ax2.spines[s].set_visible(False)
ax2.text(0.015, 0.965, "月份下方为上涨月数/样本数；7 月均值剔除 2021 年 +149.6% 后为 -7.3%",
         transform=ax2.transAxes, fontsize=7.8, color=GRAY, va="top")

fig.suptitle(TITLE, fontsize=14.5, fontweight="bold", color=DARK, x=0.035, ha="left", y=0.955)
fig.text(0.035, 0.878, NOTE, fontsize=8.4, color=GRAY, ha="left")


# ── 生成时单位自查（前置闸门：report-logic-audit 关卡五 FU1/FU2）──
def _assert_units(axis_title, labels, group, unit="%"):
    if unit not in axis_title:
        return
    bad = [s for s in labels if (unit not in s) or (unit == "%" and "倍" in s)]
    assert not bad, "[FU2] %s 组标签与轴单位「%s」不一致：%s" % (group, unit, bad)


_assert_units("月度平均收益率（%）", MRET_TXT, "MRET")
_assert_units("单季营业收入（亿元）", [t + "亿" for t in Q4_TXT], "Q4", unit="亿")

fig.savefig(OUT, dpi=100, facecolor="white")
print("saved", OUT)
print("  Q4 平均占比 35.3% / Q4-Q1 2.45x / 6月均值 +15.9% / 1月 -4.8%")
