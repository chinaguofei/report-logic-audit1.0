# -*- coding: utf-8 -*-
# ⚠ 本文件是技能模板，文件内示例数据为「海目星 688559」，使用前必须整体替换配置区。
# 用途：图5 产业链传导路径与时滞
# 用法：复制到 data/ 后改名 draw_xxx_{code}.py，改配置区常量与 OUT 文件名，再运行。
# 规格：图注必须写清「口径 + 数据源等级（A/B/C/D）」，见 references/chapter-spec.md
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = "chain_688559.png"

TITLE = "产业链传导路径：利润池在中游，海目星受益滞后下游下单 2–3 个季度"
NOTE = "传导起点 = 下游资本开支；路径 = 扩产下单 → 收入确认（验收制，1–1.5 年）→ 毛利兑现"
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
BLUE_L = "#D9E6F5"
BLUE_M = "#7FA8D9"
ORANGE = "#E67E22"
ORANGE_L = "#FBE3CD"
GRAY = "#8C8C8C"
DARK = "#1A1A1A"

fig = plt.figure(figsize=(15.75, 4.9), dpi=100)
ax = fig.add_axes([0.02, 0.02, 0.96, 0.80])
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis("off")

def box(x, y, w, h, text, fc, ec, fs=10, tc=DARK, bold=False, lw=1.2):
    b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6,rounding_size=1.6",
                       facecolor=fc, edgecolor=ec, lw=lw, zorder=3)
    ax.add_patch(b)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            color=tc, fontweight="bold" if bold else "normal", zorder=4, linespacing=1.5)
    return b

def arrow(x1, y1, x2, y2, color=GRAY, lw=1.6, style="-|>"):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, color=color,
                        lw=lw, mutation_scale=16, zorder=2,
                        connectionstyle="arc3,rad=0")
    ax.add_patch(a)

# ── 列标题 ──
for cx, t, c in [(14, "上游", GRAY), (50, "中游 · 海目星所在", RED), (86, "下游", BLUE)]:
    ax.text(cx, 93, t, ha="center", fontsize=12, fontweight="bold", color=c)

# ── 上游 ──
box(3.5, 66, 21, 17, "激光器\nIPG / 锐科 / 杰普特", BLUE_L, BLUE_M, fs=9.5)
box(3.5, 44, 21, 15, "精密机械", BLUE_L, BLUE_M, fs=9.5)
box(3.5, 22, 21, 15, "电控系统", BLUE_L, BLUE_M, fs=9.5)

# ── 中游（高亮）──
box(36, 52, 28, 31,
    "锂电设备集成\n激光焊接 · 模切 · 清洗 · 整线\n+ 固态电池设备（0→1）",
    ORANGE_L, RED, fs=10, bold=True, lw=2.2)
ax.text(50, 40.5, "利润池：中游非标集成与工艺 know-how",
        ha="center", fontsize=9.5, color=RED, fontweight="bold")
ax.text(50, 32.5, "壁垒高 → 利润最易截留环节", ha="center", fontsize=8.5, color=GRAY)

# ── 下游 ──
box(74, 66, 22.5, 17, "电池厂\n动力 / 储能 / 消费", BLUE_L, BLUE_M, fs=9.5)
box(74, 44, 22.5, 15, "储能集成商", BLUE_L, BLUE_M, fs=9.5)
ax.text(85, 35.5, "买方议价权：高\n（电池厂集中、压价强）", ha="center", fontsize=8.5, color=GRAY)

# ── 主链箭头 ──
arrow(25.5, 58, 35, 63, color=RED, lw=2.0)
arrow(65, 63, 73, 58, color=GRAY, lw=2.0)
ax.text(30.2, 66.5, "供货", fontsize=9, color=GRAY)
ax.text(66.8, 66.5, "设备采购", fontsize=9, color=GRAY)

# 反向传导（需求自下游发起）
arrow(73, 50, 65.2, 55, color=BLUE, lw=1.6, style="-|>")
ax.text(69.5, 38.5, "资本开支 / 招标\n（传导起点）", fontsize=8.5, color=BLUE, ha="center")

# ── 底部时间轴：受益节奏 ──
ty = 13
ax.plot([26, 92], [ty, ty], color=DARK, lw=1.4, zorder=1)
steps = [
    (30, "下游扩产下单", "T"),
    (50, "中游订单高增", "T + 2–3 季度"),
    (70, "收入确认（验收制）", "T + 1–1.5 年"),
    (89, "毛利兑现", "T + 1.5 年+"),
]
for sx, t1, t2 in steps:
    ax.plot([sx], [ty], marker="o", ms=7, color=RED, zorder=5)
    ax.text(sx, ty + 5.5, t1, ha="center", fontsize=9.5, fontweight="bold", color=DARK)
    ax.text(sx, ty - 7.0, t2, ha="center", fontsize=9, color=RED)
ax.annotate("", xy=(91.8, ty), xytext=(88.8, ty),
            arrowprops=dict(arrowstyle="-|>", color=DARK, lw=1.4))
ax.text(12, ty, "受益节奏 →", ha="center", va="center", fontsize=9.5, color=GRAY)

fig.suptitle(TITLE, fontsize=14, fontweight="bold", color=DARK, x=0.035, ha="left", y=0.955)
fig.text(0.035, 0.885, NOTE, fontsize=9, color=GRAY, ha="left")

fig.savefig(OUT, dpi=100, facecolor="white")
print("saved", OUT)
