# -*- coding: utf-8 -*-
"""上市公司研报分析 docx 生成器 —— 骨架模板（十章 12 图 4 表，2026-10-27 定稿）。

复制本文件为 data/build_report_{code}.py，然后：
  1. 替换「数据区」的 CONSENSUS / MATRIX_HEAD / MATRIX / PEER_MAIN / PEER_ALT（示例已清空，需整体填入）
  2. 把 main() 里每个【填空…】替换为真实文字（**保留章节顺序、二级标题编号、占位符位置，不增删章节**）
  3. 运行 build_report_{code}.py → 再运行 insert_img_{code}.py 替换 12 个 [[IMG_*]] 占位

结构权威：references/chapter-spec.md（十章 + 12 图 + 4 表 + 六条硬规则）
样式规格：references/style-spec.md（勿随意改动）
旧版（九章 3 图）存档：scripts/_archive/build_report_v1_9ch.py
"""
import sys
sys.path.insert(0, "data")
from docx import Document
from docx.shared import Pt, RGBColor, Twips
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# ============ 主题常量（勿改） ============
R = "C0392B"          # 涨/正 红
G = "00913F"          # 跌/负 绿
HDR = "185FA5"        # 主题蓝
HDRTXT = "FFFFFF"
FIRSTCOL = "E6F1FB"
OWNCOL = "FFF4E5"
GRAY = "595959"
FONT = "微软雅黑"
# =========================================

TODAY = "2026 年 10 月 27 日"                    # ← 改
OUT_SRC = "data/{公司简称}{代码}研报分析.docx"     # ← 改（中间产物，insert 脚本复制到桌面 WB）


def set_cell_shading(cell, color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), color)
    tcPr.append(shd)


def set_cell_width(cell, twips):
    tcPr = cell._tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("w:tcW")):
        tcPr.remove(old)
    tcW = OxmlElement("w:tcW"); tcW.set(qn("w:w"), str(twips)); tcW.set(qn("w:type"), "dxa")
    tcPr.append(tcW)


def add_runs(p, text, *, size=8.0, bold=False, color=None, font=FONT):
    """支持内联标记：<r>红</r> <g>绿</g> <b>粗</b>（正文中文引号一律用「」，勿用 ASCII 双引号）"""
    import re
    parts = re.split(r"(<r>.*?</r>|<g>.*?</g>|<b>.*?</b>)", text, flags=re.S)
    for part in parts:
        if not part:
            continue
        c, b = color, bold
        if part.startswith("<r>"):
            part, c = part[3:-4], R
        elif part.startswith("<g>"):
            part, c = part[3:-4], G
        elif part.startswith("<b>"):
            part, b = part[3:-4], True
        run = p.add_run(part)
        run.font.size = Pt(size); run.font.bold = b; run.font.name = font
        run._element.rPr.rFonts.set(qn("w:eastAsia"), font)
        if c:
            run.font.color.rgb = RGBColor.from_string(c)


def write_cell(cell, text, *, size=8.0, bold=False, color=None, align="center"):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if align == "center" else WD_ALIGN_PARAGRAPH.LEFT
    pf = p.paragraph_format; pf.space_after = Pt(0); pf.space_before = Pt(0); pf.line_spacing = 1.0
    add_runs(p, text, size=size, bold=bold, color=color)


def para(doc, text="", *, size=10.5, bold=False, color=None, align=None, after=4.0, line=1.3):
    p = doc.add_paragraph()
    pf = p.paragraph_format; pf.space_after = Pt(after); pf.line_spacing = line
    if align == "center":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if text:
        add_runs(p, text, size=size, bold=bold, color=color)
    return p


def h1(doc, text):
    return para(doc, text, size=14, bold=True, color=HDR, after=6)


def h2(doc, text):
    return para(doc, text, size=12, bold=True, color=HDR, after=4)


def note(doc, text, size=8.5):
    return para(doc, text, size=size, color=GRAY)


def build_table(doc, rows, widths, *, header_size=9, body_size=8,
                first_col_hl=FIRSTCOL, own_col_idx=None, own_col_hl=OWNCOL):
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER; t.autofit = False
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            cell = t.cell(ri, ci)
            set_cell_width(cell, widths[ci])
            if ri == 0:
                set_cell_shading(cell, HDR); write_cell(cell, val, size=header_size, bold=True, color=HDRTXT)
            elif ci == 0 and first_col_hl:
                set_cell_shading(cell, first_col_hl); write_cell(cell, val, size=body_size, bold=True)
            elif own_col_idx is not None and ci == own_col_idx:
                set_cell_shading(cell, own_col_hl); write_cell(cell, val, size=body_size)
            else:
                write_cell(cell, val, size=body_size)
    return t


# ===================== 数据区（整体替换） =====================
CONSENSUS = [
    ["研报/机构", "评级", "盈利/收入预测（亿元）", "关键观点"],
    ["【机构·标题（日期）】", "【买入/增持】", "【2026E x.x / 2027E x.x】", "【一句话核心观点，含关键数字】"],
]

MATRIX_HEAD = ["指标", "26Q2", "26Q1", "25Q4", "25Q3", "25Q2", "25Q1", "24Q4", "24Q3",
               "24Q2", "24Q1", "23Q4", "23Q3", "23Q2", "23Q1", "22Q4", "22Q3"]
# 10 行，顺序固定：毛利率 / 营收(亿) / 营收同比 / 归母(亿) / 归母同比 / 扣非同比 / 扣非TTM(亿) / 股东人数(户) / 户数环比 / 持股机构数
MATRIX = [
    ("毛利率", ["…"] * 16),
    ("营收(亿)", ["…"] * 16),
    ("营收同比", ["…"] * 16),
    ("归母(亿)", ["…"] * 16),
    ("归母同比", ["…"] * 16),
    ("扣非同比", ["…"] * 16),
    ("扣非TTM(亿)", ["…"] * 16),
    ("股东人数(户)", ["…"] * 16),
    ("户数环比", ["…"] * 16),
    ("持股机构数", ["…"] * 16),
]

# 同业两表：列序即名次（按近 3 季营收单季同比均值降序），8 行固定
PEER_HEAD = ["指标", "①{本公司}", "②{同业1}", "③{同业2}", "④{同业3}", "⑤{同业4}"]
PEER_ROWS = ["营收(亿)", "营收同比", "归母(亿)", "归母同比", "毛利率", "净利率", "PE(TTM)", "PB"]
PEER_MAIN = [PEER_HEAD] + [[k] + ["…"] * 5 for k in PEER_ROWS]      # 主业口径（表1，在前）
PEER_ALT = [PEER_HEAD] + [[k] + ["…"] * 5 for k in PEER_ROWS]       # 工艺邻接口径（表2，在后）

# ── 同业表头占位符闸门（构建时强制拦截） ───────────────────
# PEER_HEAD 必须填真实公司名+代码（如「①北芯生命 688712」），禁止保留
# {本公司}/{同业N}/花括号占位。下面 _assert_peer_headers_ok 在 main() 构建同业表前
# 调用，命中占位直接 raise，使文档无法生成——从源头杜绝带占位符出货。
_PEER_PLACEHOLDER_TOKENS = ("本公司", "同业1", "同业2", "同业3", "同业4", "{", "}")
def _assert_peer_headers_ok(tables, names):
    for tbl, nm in zip(tables, names):
        for cell in tbl[0]:                      # 仅校验表头行（首行），正文「…」占位不计
            s = str(cell)
            hit = [t for t in _PEER_PLACEHOLDER_TOKENS if t in s]
            if hit:
                raise RuntimeError(
                    f"[阻断] 同业对标表「{nm}」表头残留占位符 {s!r}（命中 {hit}）。"
                    f"必须替换为真实公司名+代码（如「惠泰医疗 688617」）后再生成文档。"
                )
# =============================================================


def main():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Twips(11906), Twips(16838)

    # ── 一、公司概况与最新行情 ─────────────────────────────
    h1(doc, "一、公司概况与最新行情")
    para(doc, "【填空①公司简介：主营/核心产品/客户/产能布局 + 报告期重大事件（定增、并购、扩产）；"
              "若报告期有定增/转债，必须写明对每股指标的摊薄影响，并指出本报告估值测算是否含摊薄】", size=10.5)
    para(doc, "【最新行情】截至 {交易日} 收盘，现价 <b>{价格} 元</b>（当日 {涨跌幅}），总市值约 <b>{市值} 亿元</b>；"
              "PB(LF) 约 {PB} 倍。需注意<b>两种 PE 口径不同</b>：按最新半年报归母简单年化 PE 约 {PE1} 倍；"
              "按滚动 TTM（最近四季合计）归母 {TTM 归母} 亿元，PE {适用情况}。因此全篇估值锚以 <b>{PS/PB}</b> 为主，PE 仅作辅助——"
              "{指标} 约 <b>{倍数} 倍</b>，处<b>上市以来 {分位}% 分位</b>。近一年（前复权）区间 <b>{最低}–{最高} 元</b>，"
              "现价较 {高点日期} 高点回撤约 {回撤}%。", size=10.5)

    # ── 二、最新研报共识 ──────────────────────────────────
    h1(doc, "二、最新研报共识")
    build_table(doc, CONSENSUS, [1980, 1150, 2100, 3410], header_size=9, body_size=8)
    note(doc, "【灰字：一致预期的口径、时点、机构数量；说明 C 类数据仅作参照】", size=8.5)

    # ── 三、核心逻辑 ──────────────────────────────────────
    h1(doc, "三、核心逻辑")
    para(doc, "① 【判断 + 数据支撑】", size=10.5)
    para(doc, "② 【判断 + 数据支撑】", size=10.5)
    para(doc, "③ 【判断 + 数据支撑】", size=10.5)
    para(doc, "④ 【判断 + 数据支撑】", size=10.5)
    para(doc, "⑤ 【判断 + 数据支撑，末条必须落到「证真节点」：验证什么、何时验证】", size=10.5)

    # ── 四、单季度财务矩阵 ────────────────────────────────
    h1(doc, "四、单季度财务矩阵（{起始季}–{最新季}）")
    mrows = [MATRIX_HEAD] + [[k] + v for k, v in MATRIX]
    build_table(doc, mrows, [1140] + [468.75] * 16, header_size=8, body_size=7.5)
    note(doc, "<b>口径</b>：单季值＝累计值差分；毛利率＝累计毛利额差分/累计营收差分；扣非TTM＝最近四季扣非合计；"
              "股东人数取各季末披露值、户数环比对比上一季末；持股机构数＝期末十大流通股东中机构家数（仅反映前十大席位）。"
              "红＝同比正增长/筹码分散，绿＝同比负增长/筹码集中；<b>*</b>＝上年同期基数绝对值 < 0.1 亿，同比失真仅作参考；"
              "「扭亏/转亏」＝负基数转正/正基数转负。数据源：公司定期报告（A 类）。", size=8.5)
    pimg2 = para(doc, "", size=10.5)
    pimg2.add_run("[[IMG_GROWTH]]")
    note(doc, "图1：{说明}。数据源：公司定期报告单季差分（A 类），与上方矩阵表口径一致。", size=8.5)
    para(doc, "【矩阵解读段：增长（营收/归母同比拐点）+ 盈利质量（毛利率、扣非TTM 走势）+ 筹码（户数、机构数）三段】", size=10.5)
    pimgpf = para(doc, "", size=10.5)
    pimgpf.add_run("[[IMG_PROFIT]]")
    note(doc, "图2：{说明}。数据源：公司定期报告（A 类）。", size=8.5)
    para(doc, "利润含金量提示：{归母中非经常性损益占比、扣非规模、研发投入占营收比及同比变化}；"
              "<b>估值锚提示</b>——当前滚动 TTM 归母为 {TTM} 亿元，应切换至 {PS/PB} 通道（见第八章第4节）。", size=10.5)
    h2(doc, "财务质量甄别")
    para(doc, "【调用 fraud-detector 技能，固定四块：①红黄绿灯结论 ②★异常项清单 ③一票否决项核查（立案/存贷双高/净利与经营现金流背离）"
              "④利润含金量（OCF/归母、扣非占比、收现比、应收周转、研发资本化率）】", size=10.5)

    # ── 五、所属行业景气度分析 ─────────────────────────────
    h1(doc, "五、所属行业景气度分析（{主业}为主业，{工艺}为差异化工艺）")
    h2(doc, "1. 行业界定与子赛道拆分")
    para(doc, "【主口径判定：按分业务营收占比判「所处行业」，写清占比数字；其余只作工艺邻接口径】", size=10.5)
    h2(doc, "2. 市场空间测算（TAM/SAM，量价分拆）")
    para(doc, "【TAM/SAM 测算与假设；工艺邻接行业规模只作参照，不得与主口径混用】", size=10.5)
    pimgtam = para(doc, "", size=10.5)
    pimgtam.add_run("[[IMG_TAM]]")
    note(doc, "图3：{说明}。数据源：{A/B/C/D 类}。", size=8.5)
    h2(doc, "3. 景气度六维打分（100 分，针对{公司}下游组合）")
    para(doc, "【六维定义 + 各维得分 + 总分与所处阶段（如「景气上行中段」）】", size=10.5)
    pimgsc = para(doc, "", size=10.5)
    pimgsc.add_run("[[IMG_SCORECARD]]")
    note(doc, "图4：{说明}。数据源：本报告第⑤章测算（D 类自行推算）。", size=8.5)
    h2(doc, "4. 产业链传导路径")
    para(doc, "【传导起点→中游→公司的路径与时滞；利润池位置】", size=10.5)
    pimgch = para(doc, "", size=10.5)
    pimgch.add_run("[[IMG_CHAIN]]")
    note(doc, "图5：{说明}。数据源：本报告第⑤章整理（D 类）。", size=8.5)
    h2(doc, "5. 竞争格局（波特五力）")
    para(doc, "【五力逐项 + 集中度数字】", size=10.5)
    h2(doc, "6. 关键变量与跟踪指标")
    para(doc, "【3–5 个可跟踪变量，写明数据源与频率】", size=10.5)
    h2(doc, "7. 公司订单与新品动态（行业景气落地，必写）")
    para(doc, "【在手/新增订单、海外新签、新品与客户验证进展；与前文景气判断互相印证】", size=10.5)
    pimgod = para(doc, "", size=10.5)
    pimgod.add_run("[[IMG_ORDERS]]")
    note(doc, "图6：{说明}。口径：{含税/截至日/来源公告}。", size=8.5)

    # ── 六、行业平均净利润 vs 公司净利润 ───────────────────
    h1(doc, "六、行业平均净利润 vs {公司}净利润曲线对比（近16个季度·{主业}主口径 + {工艺}工艺邻接口径）")
    para(doc, "【主口径对比：取样公司名单与等权均值口径；先读主口径】", size=10.5)
    pimgnp2 = para(doc, "", size=10.5)
    pimgnp2.add_run("[[IMG_INDNP_LIBATT]]")
    note(doc, "图7：{说明}。数据源：各公司定期报告（A 类），等权均值。", size=8.5)
    para(doc, "【工艺邻接口径对比，仅作参照】", size=10.5)
    pimgnp = para(doc, "", size=10.5)
    pimgnp.add_run("[[IMG_INDNP]]")
    note(doc, "图8：{说明}。数据源：各公司定期报告（A 类），等权均值。", size=8.5)
    para(doc, "【结论段：公司与行业是否同周期、滞后/领先几季、反转确定性】", size=10.5)

    # ── 七、同行业对标 ────────────────────────────────────
    h1(doc, "七、同行业对标（{主业}为主业口径·{工艺}为工艺邻接口径·按近3季营收增速排名前5·纯主业过滤）（{报告期}）")
    para(doc, "【选取规则：样本池、纯主业过滤（剔除跨界/占比不足者）、排序键（近 3 季营收单季同比均值降序）】", size=10.5)
    _assert_peer_headers_ok([PEER_MAIN, PEER_ALT], ["主业口径(表1)", "工艺邻接口径(表2)"])
    build_table(doc, PEER_MAIN, [1200, 1200, 1200, 1200, 1200, 1200], header_size=9, body_size=8, own_col_idx=1)
    note(doc, "表1：{口径与财务列时点}；列序即名次 ①→⑤。", size=8.5)
    build_table(doc, PEER_ALT, [1200, 1200, 1200, 1200, 1200, 1200], header_size=9, body_size=8, own_col_idx=1)
    note(doc, "表2：{工艺邻接对照口径，仅作参照}；列序即名次 ①→⑤。", size=8.5)
    para(doc, "主口径解读：{公司在主业池的名次、增速、盈利成色、估值对比}", size=10.5)
    para(doc, "工艺邻接解读：{仅作工艺邻接参照，不改变所处行业判定}", size=10.5)
    para(doc, "双口径综合解读：①<b>增长排位</b>…②<b>盈利成色</b>…③<b>估值</b>…④<b>口径纪律</b>…", size=10.5)

    # ── 八、技术分析与估值 ────────────────────────────────
    h1(doc, "八、技术分析与估值（趋势位置 × 筹码 × {PS/PB} 通道 × 三情景）")
    h2(doc, "1. 近一年K线走势与趋势点评")
    para(doc, "【近一年区间、现价位置、均线排列与数值、倍量阳线统计与有效性】", size=10.5)
    pimg = para(doc, "", size=10.5)
    pimg.add_run("[[IMG_KLINE]]")
    note(doc, "图9：K 线图为近一年日线（前复权），均线 MA5/MA20/MA60/MA240；60 日线向上为红、向下为绿；"
              "倍量阳线（收阳且量 ≥ 前日 2 倍）以黄色实体标注。", size=8.5)
    h2(doc, "2. 筹码结构与资金关注度（股东户数 × 调研热度）")
    para(doc, "【户数环比、机构调研家数、机构席位数量；未取的资金数据必须明说「本期未取、不下结论」】", size=10.5)
    h2(doc, "3. 未来趋势预判（季节性 × 热点 × 位置）")
    para(doc, "【必写季节性论证，四段结构：①分开「收入旺季」与「股价旺季」②收入侧实证（Q4 占全年比、区间、Q4/Q1 倍数、旺季失效反例）"
              "③股价侧月度收益统计并说明显著性（样本量 n、极端值影响）④翻译成验证时间轴 + 两条可证伪判据 + 与三情景档位联动】", size=10.5)
    pimgsz = para(doc, "", size=10.5)
    pimgsz.add_run("[[IMG_SEASON]]")
    note(doc, "图10：{说明}。收入口径为定期报告累计值差分（A 类），股价口径为前复权月末收盘环比（D 类自算）。", size=8.5)
    para(doc, "位置结论：季节性只影响<b>验证节奏</b>，不改变<b>趋势判断</b>——{均线分界与操作定性}。", size=10.5)
    h2(doc, "4. 近五年估值通道分析（市销率 PS / 市净率 PB，按 Step 3E 分派）")
    para(doc, "【口径段（必须写明选 PS 还是 PB 及关键证据数字）+ 当前位置/历史脉络段；数字取自 draw_valuation 尾部核实输出，禁止估算】", size=10.5)
    pimg3 = para(doc, "", size=10.5)
    pimg3.add_run("[[IMG_VALUATION]]")
    note(doc, "图11：通道线为上市以来日 {PS/PB} 分位数×当期每股营收（净资产），y 轴为股价尺度。", size=8.5)
    h2(doc, "5. 估值三情景推演（{PS/PB} 通道 × 营收增速 × 扣非验证）")
    para(doc, "【基础参数（SPS/BPS、股本、现价、当前倍数）→ 悲观/中性/乐观三档（分位、股价区间、涨跌幅、成立条件与验证信号）"
              "→ 声明「条件判断非预测，任一信号落空即下修」】", size=10.5)
    pimgsc2 = para(doc, "", size=10.5)
    pimgsc2.add_run("[[IMG_SCENARIO]]")
    note(doc, "图12：{说明}。红虚线＝现价，灰点线＝历史最低对应价；情景为数学映射，非目标价。", size=8.5)
    note(doc, "情景假设说明：{每股指标口径、股本假设与摊薄情形、是否含流动性/情绪溢价}。", size=8.5)

    # ── 九、小结（结论章，必须排在估值之后）─────────────────
    h1(doc, "九、小结")
    para(doc, "【第 1 段：主线与基本面——反转逻辑、订单与现金流、第二曲线、一致预期；须清醒看到的问题（扣非、毛利率、杠杆、筹码）】", size=10.5)
    para(doc, "把三块拼起来看：<b>基本面在修复</b>——{增速与排位、盈利成色}；<b>估值在底部</b>——{倍数与分位}，"
              "三情景对应股价 {悲观}/{中性}/{乐观} 元（{涨跌幅区间}）。<b>趋势未反转</b>——{均线与位置}。"
              "三者错位意味着这是一笔「{左侧/右侧}交易」——<b>低分位只提供赔率、不提供催化</b>，真正的扳机是 {证真节点}。", size=10.5)

    # ── 十、风险提示（正文末章）──────────────────────────
    h1(doc, "十、风险提示")
    para(doc, "本章按「风险来源—传导路径—观察指标」三要素列示，与第九章小结的证真节点、第八章第5节的三情景条件一一对应；"
              "下列任一条兑现，均应据此下修情景假设，而非仅作提示性表述。", size=10.5)
    h2(doc, "1. 行业与需求风险")
    para(doc, "① 【下游扩产/资本开支】…观察指标：… ② 【价格战与毛利率】…观察指标：…", size=10.5)
    h2(doc, "2. 财务与资产质量风险")
    para(doc, "③ 【应收+合同资产与减值】… ④ 【杠杆与流动性】… ⑤ 【修复依赖出清假设】… ⑥ 【定增摊薄】（如有）…", size=10.5)
    h2(doc, "3. 新业务与兑现风险")
    para(doc, "⑦ 【新业务验证周期与订单兑现】…观察指标：…", size=10.5)
    h2(doc, "4. 交易与外部风险")
    para(doc, "⑧ 【筹码分散】… ⑨ 【海外地缘与汇率】… ⑩ 【技术面趋势未反转，低分位不等于底】…", size=10.5)
    para(doc, "<b>风险与证真节点的对应关系</b>：{最关键节点} 对应上文哪些项；若同时落空，应切换至第八章第5节的悲观档（{倍数}、对应约 {价格} 元），"
              "并重新评估主线是否成立。", size=10.5)

    # ── 尾注（固定，勿删）────────────────────────────────
    note(doc, "<b>数据来源与分级说明</b>：A 类＝交易所/公司公告等法定披露文件（定期报告、调研公告、年报问询函）；"
              "B 类＝第三方研究机构统计与主流财经媒体；C 类＝券商研报与市场一致预期（仅作参照，不作决策依据）；"
              "D 类＝本报告自行推算（如量价分拆、情景推演，已标注假设）。全篇数据如未特别标注，均取 A 类公司定期报告口径。", size=8.5)
    note(doc, "免责声明：本报告基于公开信息整理，仅供研究参考，不构成任何投资建议。"
              "报告中的预测、估值与判断均存在不确定性，投资者应独立判断并自行承担投资风险。"
              "股市有风险，入市需谨慎。", size=8.5)

    doc.save(OUT_SRC)
    print("saved:", OUT_SRC)


if __name__ == "__main__":
    main()
