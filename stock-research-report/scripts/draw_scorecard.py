# -*- coding: utf-8 -*-
# ⚠ 本文件是技能模板，文件内示例数据为「海目星 688559」，使用前必须整体替换配置区。
# 用途：图4 景气度六维打分（左：雷达；右：各维缺口条形）
# 用法：复制到 data/ 后改名 draw_xxx_{code}.py，改配置区常量与 OUT 文件名，再运行。
# 规格：图注必须写清「口径 + 数据源等级（A/B/C/D）」，见 references/chapter-spec.md
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

OUT = "scorecard_688559.png"

# ── 配置区（改这里即可换公司）─────────────────────────────
TITLE = "海目星下游行业景气度六维打分（100 分制）"
DIMS = ["需求", "价格", "供给", "盈利", "政策/外部", "资金/情绪"]
FULL = [25, 20, 15, 15, 15, 10]
GOT = [22, 12, 11, 10, 14, 7]
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
GRAY = "#8C8C8C"
LIGHT = "#DCE6F2"
DARK = "#1A1A1A"

assert len(DIMS) == len(FULL) == len(GOT), "维度数不一致"
TOTAL = sum(GOT)
TOTAL_FULL = sum(FULL)
N = len(DIMS)
gaps = [f - g for f, g in zip(FULL, GOT)]
worst = int(np.argmax(gaps))

fig = plt.figure(figsize=(15.75, 5.6), dpi=100)
fig.subplots_adjust(left=0.035, right=0.985, top=0.83, bottom=0.09, wspace=0.30)

# ── 左：雷达 ─────────────────────────────────────────────
ax = fig.add_subplot(1, 2, 1, polar=True)
ax.set_position([0.055, 0.115, 0.36, 0.685])
angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
angles_c = angles + angles[:1]
full_c = FULL + FULL[:1]
got_c = GOT + GOT[:1]

ax.plot(angles_c, full_c, color=GRAY, lw=1.5, ls="--", zorder=3, label="满分轮廓")
ax.fill(angles_c, full_c, color=GRAY, alpha=0.10, zorder=1)
ax.plot(angles_c, got_c, color=RED, lw=2.3, zorder=4, label="实得分")
ax.fill(angles_c, got_c, color=RED, alpha=0.20, zorder=2)
ax.scatter(angles, GOT, s=42, color=RED, edgecolors="white", linewidths=1.0, zorder=6)

ax.set_xticks(angles)
ax.set_xticklabels([f"{d}\n{g}/{f}" for d, g, f in zip(DIMS, GOT, FULL)], fontsize=9.5, color=DARK)
ax.set_ylim(0, max(FULL) * 1.06)
ax.set_yticks([5, 10, 15, 20, 25])
ax.set_yticklabels(["5", "10", "15", "20", "25"], fontsize=7.5, color=GRAY)
ax.tick_params(axis="y", pad=-2)
ax.grid(color=GRAY, alpha=0.30, lw=0.7)
ax.spines["polar"].set_color(GRAY)
ax.spines["polar"].set_alpha(0.35)
ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.24), ncol=2,
          fontsize=8.5, frameon=False)

# ── 右：缺口条形 ─────────────────────────────────────────
ax2 = fig.add_subplot(1, 2, 2)
ax2.set_position([0.50, 0.13, 0.47, 0.66])
y = np.arange(N)[::-1]
ax2.barh(y, FULL, color=LIGHT, height=0.60, zorder=2, label="满分")
ax2.barh(y, GOT, color=RED, height=0.60, zorder=3, label="实得")
for yi, f, g, gp in zip(y, FULL, GOT, gaps):
    ax2.text(f + 0.35, yi, f"{g} / {f}", va="center", ha="left",
             fontsize=9.5, color=DARK, fontweight="bold")
    if gp >= 3:
        ax2.text(f + 2.9, yi, f"缺口 {gp}", va="center", ha="left",
                 fontsize=8.5, color=(RED if gp >= 5 else GRAY))

ax2.set_yticks(y)
ax2.set_yticklabels(DIMS, fontsize=10)
ax2.set_xlim(0, max(FULL) * 1.42)
ax2.set_ylim(-0.7, N - 0.3)
ax2.set_xlabel("得分（分）", fontsize=9.5, color="#333333")
ax2.grid(True, axis="x", alpha=0.25, ls="--", lw=0.6, zorder=0)
ax2.set_axisbelow(True)
for s in ("top", "right"):
    ax2.spines[s].set_visible(False)
ax2.legend(loc="lower right", fontsize=8.5, frameon=False, ncol=2)

# ── 标题与结论 ───────────────────────────────────────────
fig.text(0.035, 0.955, TITLE, fontsize=15, fontweight="bold", color=DARK, ha="left")
fig.text(0.035, 0.895,
         f"合计 {TOTAL} / {TOTAL_FULL} 分 → 景气档（65–79）：上行中段，非过热",
         fontsize=10.5, color=RED, ha="left", fontweight="bold")
fig.text(0.035, 0.855,
         f"最大失分项 = {DIMS[worst]}（缺口 {gaps[worst]} 分）；"
         f"次为 {'、'.join(d for d, gp in zip(DIMS, gaps) if gp >= 4 and d != DIMS[worst])}",
         fontsize=9.5, color="#444444", ha="left")
fig.text(0.985, 0.955, "满分 = 各维度权重，实得 = 打分", fontsize=8.5,
         color=GRAY, ha="right")

fig.savefig(OUT, dpi=100, facecolor="white")
print("saved", OUT)
for d, f, g, gp in zip(DIMS, FULL, GOT, gaps):
    print(f"  {d:8s} {g:2d}/{f:2d}  缺口 {gp}")
print(f"  合计 {TOTAL}/{TOTAL_FULL} → {'景气档(65-79)' if 65 <= TOTAL <= 79 else '需复核档位'}")
print(f"  最大失分项：{DIMS[worst]}（缺口 {gaps[worst]}）")
