# -*- coding: utf-8 -*-
# ⚠ 本文件是技能模板，文件内示例数据为「海目星 688559」，使用前必须整体替换配置区。
# 用途：图6 订单全景（左：规模；右：同比增速）
# 用法：复制到 data/ 后改名 draw_xxx_{code}.py，改配置区常量与 OUT 文件名，再运行。
# 规格：图注必须写清「口径 + 数据源等级（A/B/C/D）」，见 references/chapter-spec.md
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

OUT = "orders_688559.png"

# ── 配置区 ────────────────────────────────────────────
TITLE = "海目星订单全景：规模与同比增速"
ITEMS = ["在手订单（含税）", "新增订单（含税）", "海外新签（25H1）"]
AMT = [200.0, 100.0, 18.88]        # 亿元
AMT_TXT = ["约 200 亿", "超 100 亿", "18.88 亿"]
YOY = [100.0, 150.0, 192.5]        # %
# 单位硬规则：轴标题为「%」时，所有数据标签必须同为 %，禁止「翻倍 / 1.5 倍」混入
YOY_TXT = ["+100%", "+150%", "+192.5%"]
NOTE = "口径：在手/新增截至 2026-06-30（调研公告 2026-09-08）；海外新签为 2025H1 口径"
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
BLUE = "#185FA5"
BLUE_L = "#7FA8D9"
GRAY = "#8C8C8C"
DARK = "#1A1A1A"

N = len(ITEMS)
y = np.arange(N)[::-1]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.75, 4.6), dpi=100)
fig.subplots_adjust(left=0.135, right=0.975, top=0.78, bottom=0.16, wspace=0.42)

# ── 左：规模 ──
colors = [BLUE, BLUE_L, "#B7CDE8"]
ax1.barh(y, AMT, color=colors, height=0.56, zorder=3)
for yi, a, t in zip(y, AMT, AMT_TXT):
    ax1.text(a + max(AMT) * 0.015, yi, t, va="center", ha="left",
             fontsize=10.5, color=DARK, fontweight="bold")
ax1.set_yticks(y)
ax1.set_yticklabels(ITEMS, fontsize=10.5)
ax1.set_xlim(0, max(AMT) * 1.28)
ax1.set_xlabel("订单金额（亿元）", fontsize=9.5, color="#333333")
ax1.set_title("规模（亿元）", fontsize=11.5, fontweight="bold", color=DARK, pad=8)
ax1.grid(True, axis="x", alpha=0.25, ls="--", lw=0.6, zorder=0)
ax1.set_axisbelow(True)
for s in ("top", "right"):
    ax1.spines[s].set_visible(False)

# ── 右：同比 ──
ax2.barh(y, YOY, color=RED, height=0.56, zorder=3)
for yi, v, t in zip(y, YOY, YOY_TXT):
    ax2.text(v + max(YOY) * 0.015, yi, t, va="center", ha="left",
             fontsize=10.5, color=RED, fontweight="bold")
ax2.set_yticks(y)
ax2.set_yticklabels(ITEMS, fontsize=10.5)
ax2.set_xlim(0, max(YOY) * 1.38)
ax2.set_xlabel("同比增速（%）", fontsize=9.5, color="#333333")
ax2.set_title("同比增速（%）", fontsize=11.5, fontweight="bold", color=DARK, pad=8)
ax2.grid(True, axis="x", alpha=0.25, ls="--", lw=0.6, zorder=0)
ax2.set_axisbelow(True)
for s in ("top", "right"):
    ax2.spines[s].set_visible(False)

fig.suptitle(TITLE, fontsize=14.5, fontweight="bold", color=DARK, x=0.035, ha="left", y=0.96)
fig.text(0.035, 0.875, NOTE, fontsize=9, color=GRAY, ha="left")


# ── 生成时单位自查（前置闸门：report-logic-audit 关卡五 FU1/FU2）──
def _assert_units(axis_title, labels, group, unit="%"):
    """轴标题声明了单位，该轴所有数据标签必须同为该单位且不得混入「倍」。"""
    if unit not in axis_title:
        return
    bad = [s for s in labels if (unit not in s) or (unit == "%" and "倍" in s)]
    assert not bad, "[FU2] %s 组标签与轴单位「%s」不一致：%s" % (group, unit, bad)


_assert_units("同比增速（%）", YOY_TXT, "YOY")
_assert_units("订单金额（亿元）", AMT_TXT, "AMT", unit="亿")

fig.savefig(OUT, dpi=100, facecolor="white")
print("saved", OUT)
for it, a, t, v in zip(ITEMS, AMT, AMT_TXT, YOY):
    print(f"  {it}: {t} / {v:+.1f}%")
