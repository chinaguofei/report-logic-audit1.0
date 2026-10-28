# -*- coding: utf-8 -*-
# ⚠ 本文件是技能模板，文件内示例数据为「海目星 688559」，使用前必须整体替换配置区。
# 用途：图2 利润含金量瀑布（左：归母→扣非瀑布；右：归母构成）
# 用法：复制到 data/ 后改名 draw_xxx_{code}.py，改配置区常量与 OUT 文件名，再运行。
# 规格：图注必须写清「口径 + 数据源等级（A/B/C/D）」，见 references/chapter-spec.md
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

OUT = "profit_688559.png"

# ── 配置区（数据取自 2026 半年报，A 类）────────────────
TITLE = "利润含金量拆解：26H1 归母 0.52 亿中，非经常性损益占 64.2%"
STEPS = [
    ("归母净利润", 0.52, "total", "0.52 亿"),
    ("减：非经常性损益", -0.334, "delta", "-0.334 亿"),
    ("扣非净利润", 0.186, "total", "0.186 亿"),
]
NONREC_SHARE = 64.2      # %
CORE_SHARE = 35.8        # %
NOTE = "非经常性损益主要为减值转回与政府补助；扣非/归母 = 35.8%，账面扭亏对非经常项依赖度高"
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
RED_L = "#E8A79E"
BLUE = "#185FA5"
BLUE_L = "#7FA8D9"
GRAY = "#8C8C8C"
DARK = "#1A1A1A"

fig = plt.figure(figsize=(15.75, 4.6), dpi=100)
ax1 = fig.add_axes([0.075, 0.16, 0.50, 0.58])
ax2 = fig.add_axes([0.66, 0.28, 0.30, 0.34])

# ── 左：瀑布 ──
labels, bottoms, heights, colors = [], [], [], []
run = 0.0
for i, (name, val, kind, txt) in enumerate(STEPS):
    labels.append(name)
    if kind == "total":
        bottoms.append(0)
        heights.append(val)
        colors.append(BLUE if i == 0 else BLUE_L)
        run = val
    else:
        tops = run + val
        bottoms.append(tops)
        heights.append(abs(val))
        colors.append(RED_L)
        run = tops

x = np.arange(len(STEPS))
bars = ax1.bar(x, heights, bottom=bottoms, color=colors, width=0.48, zorder=3)

# 连接线
ax1.plot([0.24, 0.76], [0.52, 0.52], color=GRAY, lw=0.9, ls=":", zorder=2)
ax1.plot([1.24, 1.76], [0.186, 0.186], color=GRAY, lw=0.9, ls=":", zorder=2)

for xi, b, (name, val, kind, txt) in zip(x, bars, STEPS):
    top = b.get_y() + b.get_height()
    ax1.text(xi, top + 0.018, txt, ha="center", va="bottom",
             fontsize=11.5, fontweight="bold",
             color=(RED if val < 0 else BLUE))

ax1.axhline(0, color=DARK, lw=1.0)
ax1.set_xticks(x)
ax1.set_xticklabels(labels, fontsize=11)
ax1.set_ylim(-0.02, 0.63)
ax1.set_ylabel("金额（亿元）", fontsize=9.5, color="#333333")
ax1.grid(True, axis="y", alpha=0.22, ls="--", lw=0.6, zorder=0)
ax1.set_axisbelow(True)
for s in ("top", "right"):
    ax1.spines[s].set_visible(False)
ax1.set_title("归母 → 扣非：一块钱的账面利润里只有 0.36 元来自主业",
              fontsize=11.5, fontweight="bold", color=DARK, pad=8, loc="left")

# ── 右：成色条 ──
ax2.barh([0], [CORE_SHARE], color=BLUE_L, height=0.42, zorder=3)
ax2.barh([0], [NONREC_SHARE], left=[CORE_SHARE], color=RED_L, height=0.42, zorder=3)
ax2.text(CORE_SHARE / 2, 0, "扣非\n35.8%", ha="center", va="center",
         fontsize=10, color="white", fontweight="bold")
ax2.text(CORE_SHARE + NONREC_SHARE / 2, 0, "非经常性损益\n64.2%", ha="center", va="center",
         fontsize=10, color="white", fontweight="bold")
ax2.set_xlim(0, 100)
ax2.set_ylim(-0.55, 0.55)
ax2.set_yticks([])
ax2.set_xticks([0, 50, 100])
ax2.tick_params(axis="x", labelsize=8.5, colors=GRAY)
ax2.set_xlabel("归母净利润构成（%）", fontsize=9, color="#333333")
ax2.set_title("利润成色：明显偏弱", fontsize=11, fontweight="bold", color=RED, pad=8, loc="left")
for s in ("top", "right", "left"):
    ax2.spines[s].set_visible(False)

fig.suptitle(TITLE, fontsize=14.5, fontweight="bold", color=DARK, x=0.035, ha="left", y=0.96)
fig.text(0.035, 0.875, NOTE, fontsize=9, color=GRAY, ha="left")

fig.savefig(OUT, dpi=100, facecolor="white")
print("saved", OUT)
for name, val, kind, txt in STEPS:
    print("  %-14s %s" % (name, txt))
print("  扣非占比 %.1f%% / 非经常 %.1f%%" % (CORE_SHARE, NONREC_SHARE))
