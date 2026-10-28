# -*- coding: utf-8 -*-
# ⚠ 本文件是技能模板，文件内示例数据为「海目星 688559」，使用前必须整体替换配置区。
# 用途：图3 市场空间 TAM 阶梯（左：全球锂电设备；右：中国 + 固态电池设备）
# 用法：复制到 data/ 后改名 draw_xxx_{code}.py，改配置区常量与 OUT 文件名，再运行。
# 规格：图注必须写清「口径 + 数据源等级（A/B/C/D）」，见 references/chapter-spec.md
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

OUT = "tam_688559.png"

# ── 配置区（B 类第三方统计，口径见注）────────────────
TITLE = "下游市场空间（TAM）：全球 2030E 2600 亿，固态电池设备是最大增量变量"
GLOBAL = [("2025", 1340, "约 1280–1400"), ("2026E", 1500, "破 1500"), ("2030E", 2600, "2600")]
CHINA = [("2025", 545, "约 540–550"), ("2026E", 680, "破 680")]
SSB = [("2030E", 592, "约 592")]
NOTE = "口径：锂电设备市场规模，B 类（中商产业研究院/前瞻产业研究院/中国证券报等，统计口径略有差异）；固态电池设备为 2030E 全固态设备市场（B 类推算）"
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
BLUE_LL = "#B7CDE8"
ORANGE = "#E67E22"
GRAY = "#8C8C8C"
DARK = "#1A1A1A"

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.75, 4.6), dpi=100,
                               gridspec_kw={"width_ratios": [1.15, 1.0]})
fig.subplots_adjust(left=0.065, right=0.975, top=0.76, bottom=0.15, wspace=0.24)

# ── 左：全球 TAM 阶梯 ──
x = np.arange(len(GLOBAL))
vals = [v for _, v, _ in GLOBAL]
bars = ax1.bar(x, vals, color=[BLUE_L, BLUE_L, BLUE], width=0.5, zorder=3)
for xi, (yr, v, txt) in zip(x, GLOBAL):
    ax1.text(xi, v + 45, txt, ha="center", va="bottom", fontsize=11,
             fontweight="bold", color=DARK)
# CAGR 标注
ax1.annotate("", xy=(2.32, 2600), xytext=(0.35, 1340),
             arrowprops=dict(arrowstyle="-|>", color=RED, lw=1.6, ls="--",
                             connectionstyle="arc3,rad=-0.12"))
ax1.text(1.52, 2280, "2025–2030 五年 CAGR 约 14%", fontsize=10, color=RED, fontweight="bold")
ax1.set_xticks(x)
ax1.set_xticklabels([g[0] for g in GLOBAL], fontsize=11)
ax1.set_ylim(0, 3050)
ax1.set_ylabel("市场规模（亿元）", fontsize=9.5, color="#333333")
ax1.set_title("全球锂电设备 TAM：稳步扩张", fontsize=11.5, fontweight="bold",
              color=DARK, pad=8, loc="left")
ax1.grid(True, axis="y", alpha=0.22, ls="--", lw=0.6, zorder=0)
ax1.set_axisbelow(True)
for s in ("top", "right"):
    ax1.spines[s].set_visible(False)

# ── 右：中国 TAM + 固态增量 ──
labels = [c[0] for c in CHINA] + ["2030E\n固态电池设备"]
vals2 = [c[1] for c in CHINA] + [SSB[0][1]]
txts = [c[2] for c in CHINA] + [SSB[0][2]]
x2 = np.arange(len(labels))
colors2 = [BLUE_L, BLUE_L, ORANGE]
bars2 = ax2.bar(x2, vals2, color=colors2, width=0.5, zorder=3)
bars2[2].set_hatch("//")
bars2[2].set_edgecolor("white")
for xi, v, t in zip(x2, vals2, txts):
    ax2.text(xi, v + 18, t, ha="center", va="bottom", fontsize=11,
             fontweight="bold", color=DARK)
ax2.annotate("单一增量 ≈ 当前中国盘子的 87%",
             xy=(2.0, 630), xytext=(1.02, 770), fontsize=9.5,
             color=ORANGE, fontweight="bold",
             arrowprops=dict(arrowstyle="-|>", color=ORANGE, lw=1.2,
                             connectionstyle="arc3,rad=-0.2"))
ax2.set_xticks(x2)
ax2.set_xticklabels(labels, fontsize=10.5)
ax2.set_ylim(0, 850)
ax2.set_ylabel("市场规模（亿元）", fontsize=9.5, color="#333333")
ax2.set_title("中国 TAM + 最大增量变量：固态电池设备", fontsize=11.5,
              fontweight="bold", color=ORANGE, pad=8, loc="left")
ax2.grid(True, axis="y", alpha=0.22, ls="--", lw=0.6, zorder=0)
ax2.set_axisbelow(True)
for s in ("top", "right"):
    ax2.spines[s].set_visible(False)

fig.suptitle(TITLE, fontsize=14.5, fontweight="bold", color=DARK, x=0.035, ha="left", y=0.96)
fig.text(0.035, 0.868, NOTE, fontsize=8.5, color=GRAY, ha="left")

fig.savefig(OUT, dpi=100, facecolor="white")
print("saved", OUT)
print("  全球:", GLOBAL, " 中国:", CHINA, " 固态:", SSB)
