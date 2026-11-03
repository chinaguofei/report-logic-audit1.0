# -*- coding: utf-8 -*-
"""把 docx 中的 12 个图片占位段替换为真实图片，并复制到桌面 WB 文件夹（2026-10-27 扩展为 12 图）。

十二个占位符（物理顺序即图号顺序，勿改）：
  [[IMG_GROWTH]]      图1  第四章矩阵下方的「同比变化率折线图」
  [[IMG_PROFIT]]      图2  第四章解读后的「利润含金量瀑布」
  [[IMG_TAM]]         图3  第五章②「市场空间 TAM 阶梯」
  [[IMG_SCORECARD]]   图4  第五章③「景气度六维打分」
  [[IMG_CHAIN]]       图5  第五章④「产业链传导路径」
  [[IMG_ORDERS]]      图6  第五章⑦「订单全景」
  [[IMG_INDNP_LIBATT]] 图7 第六章「行业平均 vs 公司（主业口径）」
  [[IMG_INDNP]]       图8  第六章「行业平均 vs 公司（工艺邻接口径）」
  [[IMG_KLINE]]       图9  第八章①「近一年日 K 线」
  [[IMG_SEASON]]      图10 第八章③「季节性拆解」
  [[IMG_VALUATION]]   图11 第八章④「估值通道」
  [[IMG_SCENARIO]]    图12 第八章⑤「估值三情景」

用法：改下面 SRC 与 12 个图片路径后运行。换设备时 DST_DIR 已自动适配，无需改。
"""
import os
import shutil
from docx import Document
from docx.shared import Emu

SRC = r"data/公司名000000研报分析.docx"                              # ← 改（build_report 的产物）
IMG_GROWTH = r"data/growth_000000.png"                              # ← 改 图1
IMG_PROFIT = r"data/profit_000000.png"                              # ← 改 图2
IMG_TAM = r"data/tam_000000.png"                                    # ← 改 图3
IMG_SCORECARD = r"data/scorecard_000000.png"                        # ← 改 图4
IMG_CHAIN = r"data/chain_000000.png"                                # ← 改 图5
IMG_ORDERS = r"data/orders_000000.png"                              # ← 改 图6
IMG_INDNP_LIBATT = r"data/ind_vs_hmg_npcmp_libatt.png"              # ← 改 图7（主口径）
IMG_INDNP = r"data/ind_vs_hmg_npcmp.png"                            # ← 改 图8（工艺邻接口径）
IMG_KLINE = r"data/kline_000000.png"                                # ← 改 图9
IMG_SEASON = r"data/season_000000.png"                              # ← 改 图10
IMG_VALUATION = r"data/valuation_000000.png"                        # ← 改 图11
IMG_SCENARIO = r"data/scenario_000000.png"                          # ← 改 图12

# 输出目录：默认写到当前用户的桌面 WB 文件夹（跨设备可用，无需硬编码用户名）
DST_DIR = os.path.join(os.path.expanduser("~"), "Desktop", "WB")
DST = os.path.join(DST_DIR, os.path.basename(SRC))

# 宽度默认铺满正文（5903999 EMU ≈ 16.4cm）；若超出版心宽则自适应缩放到版心内（2026-09-27 固化交付铁律）
W = 5903999
PLACEHOLDERS = [
    # (占位符, 图片路径, 高度 EMU，按 W=5903999 基准比例换算)
    ("[[IMG_GROWTH]]", IMG_GROWTH, 1949666),          # 15.75 : 5.2
    ("[[IMG_PROFIT]]", IMG_PROFIT, 1724300),          # 15.75 : 4.6
    ("[[IMG_TAM]]", IMG_TAM, 1724300),                # 15.75 : 4.6
    ("[[IMG_SCORECARD]]", IMG_SCORECARD, 2099200),    # 15.75 : 5.6
    ("[[IMG_CHAIN]]", IMG_CHAIN, 1836800),            # 15.75 : 4.9
    ("[[IMG_ORDERS]]", IMG_ORDERS, 1724300),          # 15.75 : 4.6
    ("[[IMG_INDNP_LIBATT]]", IMG_INDNP_LIBATT, 2898500),   # 15.75 : 7.73
    ("[[IMG_INDNP]]", IMG_INDNP, 2898500),
    ("[[IMG_KLINE]]", IMG_KLINE, 3373714),            # 15.75 : 9.0
    ("[[IMG_SEASON]]", IMG_SEASON, 1836800),          # 15.75 : 4.9
    ("[[IMG_VALUATION]]", IMG_VALUATION, 2099620),    # 15.75 : 5.6
    ("[[IMG_SCENARIO]]", IMG_SCENARIO, 1724300),      # 15.75 : 4.6
]

os.makedirs(DST_DIR, exist_ok=True)

doc = Document(SRC)

# 版心宽度自适应：page_width − 左右边距；图宽超版心时等比缩放，防止 Word 按版心右侧裁切
W0 = W
sec = doc.sections[0]
USABLE = int(sec.page_width) - int(sec.left_margin) - int(sec.right_margin)
if W0 > USABLE:
    W = int(USABLE) - 2000
    print("clamp-to-column, scale =", round(W / W0, 4))

for token, img, h in PLACEHOLDERS:
    hit = 0
    if not os.path.exists(img):
        print(f"!! 缺少图片，跳过 {token}: {img}")
        continue
    # 高度优先按 PNG 实际纵横比算（h 仅为缺 Pillow 时的兜底常量）。
    # 2026-11-03 修正：draw_all 各图 figsize 不同，硬编码高度会把图压扁/拉长
    # （实测 scorecard 实际比例 0.798，旧常量对应 0.356，插入后严重变形）。
    hh = None
    try:
        from PIL import Image
        pw, ph = Image.open(img).size
        hh = int(W * ph / pw)
    except Exception:
        hh = int(h * W / W0)
    for p in doc.paragraphs:
        if token in p.text:
            for r in list(p.runs):
                r._element.getparent().remove(r._element)
            p.add_run().add_picture(img, width=Emu(W), height=Emu(hh))
            hit += 1
    print(f"inserted {token}:", hit)
    if hit == 0:
        print(f"!! 未找到占位符 {token}，请检查 build_report 模板")

doc.save(SRC)

# 自检 1：占位符必须全部消失
left = [p.text for p in doc.paragraphs if "[[" in p.text]
if left:
    print("!! 仍有未替换的占位符：", left)
if os.path.abspath(SRC) != os.path.abspath(DST):
    shutil.copy2(SRC, DST)
    print("copied:", DST)
else:
    print("SRC 与 DST 相同，跳过复制（已在目标位置）")

# 自检 2：逐张复核 sh.width ≤ 版心宽（不过则非零码退出，阻断交付）
chk = Document(SRC)
nfit = sum(1 for sh in chk.inline_shapes if int(sh.width) <= USABLE)
print("SELF-CHECK images-fit-column:", "PASS" if nfit == len(chk.inline_shapes) else "FAIL",
      "(%d/%d)" % (nfit, len(chk.inline_shapes)))
if nfit != len(chk.inline_shapes):
    raise SystemExit(2)
