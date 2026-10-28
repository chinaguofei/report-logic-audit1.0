# -*- coding: utf-8 -*-
"""上市公司研报分析 docx 生成器 —— 骨架模板。

复制本文件为 data/build_report_{code}.py，然后：
  1. 替换「数据区」的 CONSENSUS / MATRIX_HEAD / MATRIX / PEER_HEAD / PEER
  2. 替换 main() 中各章节的文字内容
  3. 运行：python data/build_report_{code}.py
  4. 再运行 insert_img_{code}.py 把 [[IMG_KLINE]] 占位替换为 K 线图

样式规格见 references/style-spec.md（勿随意改动）。
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

TODAY = "2026 年 9 月 10 日"      # ← 改
OUT_SRC = "data/飞龙股份002536研报分析.docx"   # ← 改（中间产物，insert 脚本会复制到桌面）


def set_cell_shading(cell, color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    tcPr.append(shd)


def set_cell_width(cell, twips):
    tcPr = cell._tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("w:tcW")):
        tcPr.remove(old)
    tcW = OxmlElement("w:tcW")
    tcW.set(qn("w:w"), str(twips))
    tcW.set(qn("w:type"), "dxa")
    tcPr.append(tcW)


def add_runs(p, text, *, size=8.0, bold=False, color=None, font=FONT):
    """支持内联标记：<r>红</r> <g>绿</g> <b>粗</b>"""
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
        run.font.size = Pt(size)
        run.font.bold = b
        run.font.name = font
        run._element.rPr.rFonts.set(qn("w:eastAsia"), font)
        if c:
            run.font.color.rgb = RGBColor.from_string(c)


def write_cell(cell, text, *, size=8.0, bold=False, color=None, align="center"):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = {"center": WD_ALIGN_PARAGRAPH.CENTER,
                   "left": WD_ALIGN_PARAGRAPH.LEFT}[align]
    pf = p.paragraph_format
    pf.space_after = Pt(0)
    pf.space_before = Pt(0)
    pf.line_spacing = 1.0
    add_runs(p, text, size=size, bold=bold, color=color)


def para(doc, text="", *, size=10.5, bold=False, color=None, align=None,
         after=4.0, line=1.3):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after = Pt(after)
    pf.line_spacing = line
    if align == "center":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if text:
        add_runs(p, text, size=size, bold=bold, color=color)
    return p


def h1(doc, text):
    """一级标题（一、二、…）：粗体 主题蓝 14pt"""
    return para(doc, text, size=14, bold=True, color=HDR, after=6)


def h2(doc, text):
    """二级标题（1. 2. …）：粗体 主题蓝 12pt"""
    return para(doc, text, size=12, bold=True, color=HDR, after=4)


def note(doc, text, size=8.5):
    """灰字注释"""
    return para(doc, text, size=size, color=GRAY)


def build_table(doc, rows, widths, *, header_size=9, body_size=8,
                first_col_hl=FIRSTCOL, own_col_idx=None, own_col_hl=OWNCOL):
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            cell = t.cell(ri, ci)
            set_cell_width(cell, widths[ci])
            if ri == 0:
                set_cell_shading(cell, HDR)
                write_cell(cell, val, size=header_size, bold=True, color=HDRTXT)
            elif ci == 0 and first_col_hl:
                set_cell_shading(cell, first_col_hl)
                write_cell(cell, val, size=body_size, bold=True)
            elif own_col_idx is not None and ci == own_col_idx:
                set_cell_shading(cell, own_col_hl)
                write_cell(cell, val, size=body_size)
            else:
                write_cell(cell, val, size=body_size)
    return t


# ===================== 数据区（替换此处） =====================

# --- 二、研报共识（4 列表，6 行 = 表头 + 5） ---
CONSENSUS = [
    ["研报/机构", "评级", "归母净利预测（亿元）", "关键观点"],
    # ["中报点评·XX证券（2026-08-23）", "买入", "2026E：4.69", "关键观点…"],
]

# --- 四、单季度财务矩阵（17 列 × 11 行 = 表头 + 10 指标行；末行「持股机构数」为 2026-10-26 起模板固定行） ---
# 9 行固定顺序：毛利率 / 营收(亿) / 营收同比 / 归母(亿) / 归母同比 / 扣非同比 /
#              扣非TTM(亿) / 股东人数(户) / 户数环比 / 持股机构数
MATRIX_HEAD = ["指标", "26Q2", "26Q1", "25Q4", "25Q3", "25Q2", "25Q1", "24Q4", "24Q3",
               "24Q2", "24Q1", "23Q4", "23Q3", "23Q2", "23Q1", "22Q4", "22Q3"]
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
    ("持股机构数", ["…"] * 16),   # 十大流通股东中机构家数（IS_HOLDORG="1" 计数），不着色
]

# --- 六、同业对比（7 列 = 指标 + 本公司 + 5 同业；8 行） ---
PEER_HEAD = ["指标", "本公司 000000", "同业A 000000", "同业B 000000", "同业C 000000", "同业D 000000", "同业E 000000"]
PEER = [
    ["26H1营收(亿/同比)"] + ["…"] * 6,
    ["26H1归母(亿/同比)"] + ["…"] * 6,
    ["26H1毛利率"] + ["…"] * 6,
    ["26H1净利率"] + ["…"] * 6,
    ["最新市值(亿元)"] + ["…"] * 6,
    ["估值 PE(TTM)/PB"] + ["…"] * 6,
    ["核心卡位"] + ["…"] * 6,
]

# =============================================================


def main():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Twips(12240)
    sec.page_height = Twips(15840)
    sec.top_margin = Twips(1440)
    sec.bottom_margin = Twips(1440)
    sec.left_margin = Twips(1800)
    sec.right_margin = Twips(1800)

    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10.5)
    st._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    st.paragraph_format.space_after = Pt(10)
    st.paragraph_format.line_spacing = 1.15

    para(doc, "公司名（代码）研报分析", size=20, bold=True, align="center", after=6)
    para(doc, f"基于公司定期报告、券商研报点评与公开披露整理　　报告日期：{TODAY}",
         size=10, color=GRAY, align="center", after=10)

    # 一、公司概况与最新行情（2 段）
    h1(doc, "一、公司概况与最新行情")
    para(doc, "【公司简介段：注册地、成立/上市时间、控股股东、主营业务与申万分类、产品线、"
              "客户结构、收入结构拆分、第二曲线】", size=10.5)
    para(doc, "【最新行情段：股价、涨跌幅、市值、PE(TTM)、PB、年初至今涨幅、近期高低点、"
              "异动与龙虎榜、公司风险提示公告】", size=10.5)

    # 二、最新研报共识
    h1(doc, "二、最新研报共识")
    build_table(doc, CONSENSUS, [1980, 1150, 2100, 3410], header_size=9, body_size=8)
    note(doc, "【说明：中报完成度 vs 全年一致预期、卖方如何解释利润低点、兑现押注在哪个季度、"
              "若未改善的下修风险、机构调研热度】", size=9.5)

    # 三、核心逻辑（5 条）
    h1(doc, "三、核心逻辑")
    for i in range(1, 6):
        para(doc, f"{i}. 【核心逻辑第 {i} 条】", size=10.5)

    # 四、单季度财务矩阵
    h1(doc, "四、单季度财务矩阵（2022Q3–2026Q2）")
    note(doc, "口径：单季度值由累计值差分计算，单季毛利率由累计毛利额差分推算；同比 = 本季 vs 上年同季；"
              "扣非TTM 为滚动四个季度扣非合计（绿色 = 环比下滑，红色 = 环比改善）；股东人数取各季度末"
              "（3/31、6/30、9/30、12/31）披露值，户数环比为与上一季末对比（红色 = 增加/筹码分散，绿色 = 减少/"
              "筹码集中）。红色 = 正值/增长，绿色 = 负值/下滑。数据源：公司定期报告（东方财富 F10 整理）。", size=8.5)
    mrows = [MATRIX_HEAD] + [[name] + vals for name, vals in MATRIX]
    build_table(doc, mrows, [1140] + [468.75] * 16, header_size=8, body_size=7.5)
    note(doc, "* 【低基数导致的百分比失真说明；与公司披露口径的核对说明】", size=8.5)

    # —— 第四章附属：同比变化率折线图（2026-09-10 新增，位于矩阵表与解读段之间）——
    pimg2 = para(doc, "", size=10.5)
    pimg2.add_run("[[IMG_GROWTH]]")
    note(doc, "图 1：单季度营收同比与归母同比增速（%）。横轴为 2022Q3–2026Q2 共 16 个季度，"
              "红色 = 正增长（0 轴以上），绿色 = 负增长（0 轴以下）；实线 = 营收同比，虚线 = 归母同比。"
              "数据源：公司定期报告（东方财富 F10 整理），与上方矩阵表口径一致。", size=8.5)

    para(doc, "矩阵表解读：① 【收入端 vs 利润端】② 【毛利率周期】③ 【扣非TTM 趋势 = 最重要警示信号】"
              "④ 【单季归母分布与利润底部确认】⑤ 【股东户数 = 筹码由集中到分散的过程】"
              "⑥ 【现金流与股东回报】", size=10.5)

    # === 第四章附属：财务质量甄别小节（Step 3D 常设必写；来源 fraud-detector 技能；克隆勿删）===
    h2(doc, "财务质量甄别")
    para(doc, "【红黄绿灯结论：🟢绿灯（无★异常且非★≤3）/ 🟡黄灯（★1–2 项或非★≥4 项）/ 🔴红灯（★≥3 或触发一票否决），"
              "并给一句定性，如「财务指标全绿，仅行为信号轻微异常」】", size=10.5)
    para(doc, "★异常项清单：【逐条列★级异常，注明属行为信号（减持/质押/问询函）还是财务信号"
              "（现金流/资本化/一次性收益）；无异常则写「未发现★级异常」】", size=10.5)
    para(doc, "一票否决项核查：① 证监会立案 —— 【核查结果】；② 存贷双高 —— 【核查结果】；"
              "③ 净利与经营现金流长期背离 —— 【核查结果】（三项逐一给出，未触发也要写明）", size=10.5)
    para(doc, "利润含金量：【OCF/归母现金含量、扣非/归母占比、收现比、应收周转天数、研发资本化率等关键证据数字"
              "（与矩阵数据同源同口径）；一次性收益占比高时明确提示估值锚应切换至扣非口径】", size=10.5)

    # 五、行业景气度分析（5 条，第 5 条必须是公司新品/订单动态）
    h1(doc, "五、所属行业景气度分析（行业名）")
    for i in range(1, 6):
        if i == 5:
            para(doc, "5. 【公司近期新品/新订单动态 —— 必写：新产品平台、订单量、客户名单、"
                      "项目梯队（批量/小批量/验证/送样）、产能建设进度、新领域拓展】", size=10.5)
        else:
            para(doc, f"{i}. 【行业景气度第 {i} 条】", size=10.5)

    # 六、同业对比
    h1(doc, "六、同行业前 5 名公司财务矩阵对比（26H1）")
    build_table(doc, [PEER_HEAD] + PEER, [1320] + [1275] * 6,
                header_size=8, body_size=7.5, first_col_hl=FIRSTCOL,
                own_col_idx=1, own_col_hl=OWNCOL)
    note(doc, "选取说明：【同业选取标准】。注：【口径与数据来源】。", size=8.5)
    para(doc, "对比解读：【盈利能力、成长性、估值、卡位的横向比较结论】", size=10.5)

    # 七、小结
    h1(doc, "七、小结")
    para(doc, "【一段式小结：投资逻辑、关键变化、卖方预期、须清醒看到的风险、"
              "这是什么样的交易、最关键的证真/证伪节点】", size=10.5)

    # 八、风险提示
    h1(doc, "八、风险提示")
    para(doc, "① 【风险一】；② 【风险二】；③ 【风险三】；④ 【风险四】；"
              "⑤ 【风险五】；⑥ 【风险六】；⑦ 【风险七】", size=10.5)

    # 九、技术分析
    h1(doc, "九、技术分析")
    h2(doc, "1. 近一年K线走势与趋势点评")
    para(doc, "【K 线走势描述：区间高低点、涨跌幅、均线排列（MA5/20/60/240）、"
              "当前价与各均线关系、MA60 红绿状态】", size=10.5)
    para(doc, "【⑤ 倍量阳线信号：近一年共 X 根（日期列表 + 量比），"
              "区分底部/趋势初期的有效信号 与 高位无事件配合的诱多信号】", size=10.5)
    pimg = para(doc, "", size=10.5)
    run = pimg.add_run("[[IMG_KLINE]]")
    note(doc, "注：K 线图为近一年日线（前复权），均线 MA5/MA20/MA60/MA240；"
              "60 日线向上为红、向下为绿；倍量阳线（收阳且量 ≥ 前日 2 倍）以黄色实体标注。", size=8.5)
    h2(doc, "2. 近一个月行业与个股资金流向分析")
    para(doc, "【板块资金面 + 个股主力资金进出节奏、龙虎榜、换手率、股东户数变化、"
              "机构持仓（基金/北向）】", size=10.5)
    h2(doc, "3. 未来趋势预判（季节性 × 热点 × 位置）")
    para(doc, "【综合判断：趋势 × 换手 × 估值三重状态；操作建议（均线分界位）；"
              "后续需跟踪的关键变量】", size=10.5)

    # 4. 近五年估值通道分析（Step 3E）—— 标题随指标二选一，勿漏：
    #    高成长科技 → h2(doc, "4. 近五年估值通道分析（市销率 PS）")
    #    传统公司   → h2(doc, "4. 近五年估值通道分析（市净率 PB）")
    #    口径段必须写明选 PS / PB 的理由与关键指标（见 references/data-sources.md「估值指标选择」）
    #    h2(doc, "4. 近五年估值通道分析（市销率 PS）")
    #    para(doc, "口径：以不复权收盘价对应每股营收（SPS，营收 TTM/总股本）计算 PS，"
    #              "通道线为近五年日 PS 的 0/20/40/60/80 分位倍数×当期 SPS；"
    #              "选用 PS 因公司营收 TTM 同比 +XX%、研发费用率 X%、毛利率 X%，属高成长科技。", size=10.5)
    #    para(doc, "【当前位置与历史脉络：当前 PS 与分位、通道价格带、极值日期与收盘价】", size=10.5)
    #    pimg = para(doc, "", size=10.5)
    #    pimg.add_run("[[IMG_VALUATION]]")
    #    note(doc, "注：通道线为近五年（或上市以来）日 PS 分位数×当期每股营收，y 轴为股价尺度。", size=8.5)

    note(doc, "免责声明：本报告基于公开信息整理，仅供研究参考，不构成任何投资建议。"
              "报告中的预测、估值与判断均存在不确定性，投资者应独立判断并自行承担投资风险。"
              "股市有风险，入市需谨慎。", size=8.5)

    doc.save(OUT_SRC)
    print("saved:", OUT_SRC)


if __name__ == "__main__":
    main()
