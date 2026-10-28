# -*- coding: utf-8 -*-
# ⚠ 本文件是技能模板，文件内示例数据为「海目星 688559」，使用前必须整体替换配置区。
# 用途：图12 估值三情景推演
# 用法：复制到 data/ 后改名 draw_xxx_{code}.py，改配置区常量与 OUT 文件名，再运行。
# 规格：图注必须写清「口径 + 数据源等级（A/B/C/D）」，见 references/chapter-spec.md
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

OUT = "scenario_688559.png"

# ── 配置区（D 类情景推演：PS×SPS=22.71，非预测）────────
TITLE = "估值三情景推演：现价 35.74 元贴近悲观档，上行空间取决于扣非转正验证"
SCEN = [
    # (名称, 条件, lo, hi, 标签, 颜色)
    ("乐观", "固态/AI 批量订单\n营收 TTM +50% 以上", 86, 105, "86–105 元 · PS 3.8–4.6× · +141~194%", "#7FA8D9"),
    ("中性", "营收 TTM +20~30%\n26Q4 前扣非 TTM 转正", 52, 64, "52–64 元 · PS 2.3–2.8× · +46~79%", "#4A7EBB"),
    ("悲观", "营收零增长\n扣非为负", 23.9, 26.6, "25 元 · PS 1.11×（历史最低） · −30%", "#C0392B"),
]
CUR = 35.74         # 现价（2026-10-27 收盘）
LOW = 22.78         # PS 历史最低点对应价（2024-02-05）
NOTE = "情景股价 = PS 分位倍数 × SPS 22.71 元/股（营收 TTM 56.26 亿 ÷ 总股本 2.4776 亿股）；数学映射非目标价，任一验证信号落空即下修至悲观档"
# ─────────────────────────────────────────────────────

for name in ["Microsoft YaHei", "SimHei", "SimSun", "Noto Sans CJK SC", "DejaVu Sans"]:
    try:
        fm.findfont(fm.FontProperties(family=name), fallback_to_default=False)
        plt.rcParams["font.sans-serif"] = [name]
        break
    except Exception:
        continue
plt.rcParams["axes.unicode_minus"] = False

GRAY = "#8C8C8C"
DARK = "#1A1A1A"

fig, ax = plt.subplots(figsize=(15.75, 4.6), dpi=100)
fig.subplots_adjust(left=0.115, right=0.985, top=0.76, bottom=0.14)

for i, (name, cond, lo, hi, lab, c) in enumerate(SCEN):
    y = i
    if name == "悲观":
        ax.plot([25.2], [y], marker="D", ms=13, color=c, zorder=5)
        ax.plot([lo, hi], [y, y], color=c, lw=2.2, zorder=4)
        ax.text(25.2, y + 0.30, lab, va="bottom", ha="center", fontsize=10.5,
                fontweight="bold", color=c)
    else:
        ax.barh(y, hi - lo, left=lo, color=c, height=0.42, zorder=3)
        ax.text((lo + hi) / 2, y + 0.30, lab, va="bottom", ha="center",
                fontsize=10.5, fontweight="bold", color=c)
    ax.text(-0.005, y, name, va="center", ha="right", fontsize=12,
            fontweight="bold", color=DARK, transform=ax.get_yaxis_transform())
    ax.text(0.004, y, cond, va="center", ha="left", fontsize=8.5, color=GRAY,
            transform=ax.get_yaxis_transform())

# 现价与历史低点
ax.axvline(CUR, color="#C0392B", lw=1.8, ls="--", zorder=2)
ax.text(CUR + 1.2, 2.60, "现价 35.74 元（10-27 收盘）\nPS 1.57×，上市以来 12% 分位", fontsize=9.5,
        color="#C0392B", fontweight="bold", va="top")
ax.axvline(LOW, color=GRAY, lw=1.3, ls=":", zorder=2)
ax.text(LOW + 0.8, -0.52, "PS 历史最低 1.11×（2024-02-05，对应 22.78 元）", fontsize=9,
        color=GRAY, ha="left")

# 现价与三档的相对位置括注
ax.annotate("介于悲观与中性之间：市场尚未定价中性情景", xy=(36.4, 0.60), xytext=(42.5, 0.56),
            fontsize=9, color=DARK, va="center",
            arrowprops=dict(arrowstyle="-|>", color=GRAY, lw=1.1,
                            connectionstyle="arc3,rad=-0.15"))

ax.set_yticks([])
ax.set_xlim(18, 118)
ax.set_ylim(-0.75, 2.85)
ax.set_xlabel("股价（元）", fontsize=9.5, color="#333333")
ax.grid(True, axis="x", alpha=0.22, ls="--", lw=0.6, zorder=0)
ax.set_axisbelow(True)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)

fig.suptitle(TITLE, fontsize=14, fontweight="bold", color=DARK, x=0.035, ha="left", y=0.955)
fig.text(0.035, 0.878, NOTE, fontsize=8.5, color=GRAY, ha="left")

fig.savefig(OUT, dpi=100, facecolor="white")
print("saved", OUT)
for name, cond, lo, hi, lab, c in SCEN:
    print("  %s: %s" % (name, lab))
