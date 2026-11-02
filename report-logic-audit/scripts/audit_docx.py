# -*- coding: utf-8 -*-
"""文章审校机械检查器（report-logic-audit 通用档 / 研报档）。

只查"机器能确定判对错"的项；口径混搭、主张是否成立、推理是否终结仍需模型/人语义判断。

用法:
    # 通用（任意文章）
    python audit_docx.py 文章.docx
    python audit_docx.py 文章.md --genre essay --must-have 反方观点 --must-have 限定条件

    # 研报档（向后兼容旧调用）
    python audit_docx.py 报告.docx --genre research \
        --must-have 财务质量甄别 --must-have 免责声明 \
        --industry 锂电设备 --industry-alt 激光

    # 额外产出「主张 → 证据」对照空表，供人工填
    python audit_docx.py 文章.docx --claim-table

支持 .docx / .md / .txt / .html
输出: 控制台清单 + 同目录 <文件名>_audit.json
退出码: 有 BLOCK 级发现 → 1，否则 0（便于串联流程阻断）
"""
import argparse
import json
import os
import re
import sys

from common import findings, add, CN_NUM

# 各体裁默认必写要素（用户传 --must-have 时以用户为准）
# 每组内为同义写法，命中任一即算"在位"——只认一个词会把「来源附录」判成缺失
GENRE_DEFAULTS = {
    "research": [["数据来源", "资料来源", "来源附录", "数据说明", "口径说明"],
                 ["风险提示", "风险因素", "风险分析"]],
    "essay": [["反方", "对立观点", "另一种观点", "反驳", "批驳"],
              ["限定", "前提", "适用边界", "边界条件"]],
    "academic": [["研究方法", "研究设计", "样本", "数据与方法"],
                 ["参考文献", "文献综述", "引用"],
                 ["研究局限", "局限", "不足"]],
    "explainer": [["定义", "是指", "所谓"], ["边界", "不适用", "局限", "误区"]],
    "plan": [["风险"], ["预算", "投入", "资源"], ["验收", "考核", "评估标准"]],
    "report-gov": [["存在问题", "问题与不足", "问题"], ["下一步", "下一步工作", "工作打算"]],
    "copy": [["案例", "客户"], ["适用", "场景", "不适合"]],
    "speech": [["行动", "建议", "呼吁"]],
    "howto": [["前置", "准备", "环境"], ["报错", "异常", "故障", "常见问题"]],
    "general": [],
}

# 只在"讲事实"的体裁里查来源标注
SOURCE_STRICT_GENRES = ("research", "academic")

VAGUE_WORDS = ["可能", "有望", "或将", "预计", "或许", "大概", "也许", "趋势上",
               "整体来看", "一定程度上", "在某种程度上", "不排除"]

CLAIM_MARKERS = ["因此", "所以", "说明", "表明", "可见", "意味着", "证明", "反映",
                 "显示", "显然", "必然", "应当", "必须", "核心是", "关键在于",
                 "本质是", "结论是", "由此"]

# —— 新增：逻辑冲突 / 严谨性 / 事实 / 完整性 补强（修复项，v1.1.1）——
# R17 自相矛盾：同一主题两处相反方向判断（方向极性词表）
CONTRA_POS = ("提升", "提高", "增加", "增长", "扩大", "增强", "上升", "改善", "加快", "领先",
              "高于", "集中", "充足", "乐观", "利好", "上涨", "向好", "复苏", "回暖", "收紧",
              "走强", "加速", "增进", "攀升", "走高", "偏高", "较高", "增多", "增大")
CONTRA_NEG = ("下降", "降低", "减少", "下滑", "萎缩", "减弱", "回落", "恶化", "放缓", "落后",
              "低于", "分散", "不足", "悲观", "利空", "下跌", "向差", "衰退", "走弱", "放松",
              "减速", "走低", "收窄", "承压", "偏小", "偏低", "较低", "减小")
POLARITY_ALL = set(CONTRA_POS + CONTRA_NEG)

# 作为"主题词"出现太泛、易误报的词（通用名词 + 指标名词），矛盾检测排除它们
CONTRA_STOP = set(
    "市场 行业 公司 企业 我们 目前 中国 国内 全球 数据 情况 方面 领域 业务 产品 客户 "
    "需求 供给 政策 时间 今年 去年 主要 重要 未来 短期 长期 海外 地区 部门 系统 规模 占比 "
    "收入 成本 利润 营收 净利润 增速 产量 销量 价格 利率 估值 毛利率 净利率 份额 金额 业绩 "
    "投资 风险 分析 研究 报告 影响 原因 因素 水平 状态 程度 范围 效果 质量 能力 关系 模式 "
    "体系 结构 渠道 区域 项目 计划 目标 结果 问题 优势 劣势 机会 威胁 战略 策略 方案 措施 "
    "建议 结论 总结 现状 趋势 变化 差异 比例 基数 指标 表现 环境 条件 标准 内容 形式".split()
)

# 时间词：两句话引用不同时期/年份时的合法变化，不算矛盾（R17 防误报闸）
TIME_WORDS = ("一季度", "二季度", "三季度", "四季度", "上半年", "下半年", "去年同期",
              "上年同期", "年初", "年末", "当月", "上月", "本月", "本期", "上期", "近期",
              "同期", "短期", "长期", "当期", "过往", "过去", "历史", "当前", "目前",
              "本年", "次年", "前年", "明年", "上季度", "下季度", "全年",
              "Q1", "Q2", "Q3", "Q4")
TIME_RE = re.compile(r"(?:19|20)\d{2}\s*年?")  # 4 位年份（如 2025年 / 2026）
CYCLE_WORDS = ("周期", "景气", "波动", "起伏", "轮回")  # 周期叙事天然含上下行，非矛盾


def _has_time(s):
    return any(w in s for w in TIME_WORDS) or bool(TIME_RE.search(s))


def _periods(s):
    """抽取句子所指时期签名（年份/季度/半年），用于判断两句话是否同一时期。"""
    ps = set(TIME_RE.findall(s))
    for w in ("Q1", "Q2", "Q3", "Q4", "上半年", "下半年", "全年"):
        if w in s:
            ps.add(w)
    return ps


def _has_cycle(s):
    return any(w in s for w in CYCLE_WORDS)

# 已知名词（嵌入极性词）：其中的极性语素不算方向信号，避免「集中度」误触发「集中」为正向
EMBED_NOUNS = ("集中度", "增长率", "增速", "增幅", "增长量", "降幅", "下降率", "下降量",
               "提升率", "提升空间", "提高率", "减少量", "降低率", "上升率", "升幅", "回落率")


def _has_polarity(s, words):
    """极性词若在已知名词（集中度/增长率…）内部，不算方向信号，避免误判。"""
    for w in words:
        if w in s and not any(w in n and n in s for n in EMBED_NOUNS):
            return True
    return False

# R13 量级不匹配：量级词需配效应量
EFFECT_WORDS = ("显著", "大幅", "明显", "决定性", "重大", "急剧", "剧烈", "骤然", "成倍",
                "强劲", "尤为", "格外", "高度")
# X1 有望/预计 缺条件句
FORWARD_WORDS = ("有望", "预计", "或将", "大概率", "预料", "预期将")

def cn2int(s):
    mp = {c: i + 1 for i, c in enumerate(CN_NUM[:10])}
    if s == "十":
        return 10
    if s.startswith("十"):
        return 10 + mp.get(s[1:], 0)
    if "十" in s:
        a, b = s.split("十", 1)
        return mp.get(a, 0) * 10 + (mp.get(b, 0) if b else 0)
    return mp.get(s, 0)


def load_blocks(path):
    """返回 [(kind, text, style)]，kind: p / table"""
    ext = os.path.splitext(path)[1].lower()
    blocks = []
    if ext == ".docx":
        try:
            from docx import Document
            from docx.table import Table
            from docx.text.paragraph import Paragraph
        except ImportError:
            sys.exit("缺少 python-docx，读不了 .docx。\n"
                     "  安装：pip install python-docx\n"
                     "  或者：把文档另存为 .md / .txt / .html —— 读这三种格式不需要任何第三方包。")
        d = Document(path)
        body = d.element.body
        for child in body.iterchildren():
            if child.tag.endswith("}p"):
                p = Paragraph(child, d)
                blocks.append(("p", p.text.strip(), p.style.name if p.style else ""))
            elif child.tag.endswith("}tbl"):
                t = Table(child, d)
                head = " | ".join(c.text.strip() for c in t.rows[0].cells) if len(t.rows) else ""
                blocks.append(("table", head, f"{len(t.rows)}x{len(t.columns)}"))
    elif ext in (".md", ".txt"):
        for line in open(path, encoding="utf-8", errors="ignore"):
            blocks.append(("p", line.strip(), ""))
    elif ext in (".html", ".htm"):
        raw = open(path, encoding="utf-8", errors="ignore").read()
        raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
        for m in re.finditer(r"(?is)<(h[1-6])[^>]*>(.*?)</\1>|<t[dr][^>]*>(.*?)</t[dr]>|<p[^>]*>(.*?)</p>|<div[^>]*>(.*?)</div>",
                             raw):
            tag = (m.group(1) or "").lower()
            txt = re.sub(r"(?s)<[^>]+>", "", "".join(g for g in m.groups()[1:] if g))
            txt = re.sub(r"\s+", " ", txt).strip()
            if not txt:
                continue
            blocks.append(("p", txt, tag))
    return [b for b in blocks if b[1]]


# ---------------------------------------------------------------- 结构类

def check_chapters(blocks):
    """章节编号连续性 + 缺号（中文「一、二、」或 markdown # 均可）"""
    nums = []
    for i, (kind, text, style) in enumerate(blocks):
        if kind != "p":
            continue
        m = re.match(r"^(?:#{1,6}\s*)?([%s]+)、\s*(.+)$" % CN_NUM, text)
        if m and len(m.group(1)) <= 2:
            nums.append((cn2int(m.group(1)), text[:40], i))
    if not nums:
        add("SUGGEST", "CH-EMPTY", "全文", "未识别到「一、二、三…」式章节标题",
            "若用 # / 第N部分 等结构，属正常；此时靠模型语义判结构")
        return
    seq = [n for n, _, _ in nums]
    for k in range(1, len(seq)):
        if seq[k] == seq[k - 1]:
            add("BLOCK", "CH-DUP", nums[k][1], f"章节编号重复：{nums[k][0]}", "批量改稿假成功典型症状")
        elif seq[k] > seq[k - 1] + 1:
            missing = list(range(seq[k - 1] + 1, seq[k]))
            add("BLOCK", "CH-GAP", nums[k][1], f"章节缺号：缺第 {missing} 章", "检查是否有整节漏克隆")
        elif seq[k] < seq[k - 1]:
            add("BLOCK", "CH-ORDER", nums[k][1], f"章节编号回退 {seq[k - 1]}→{seq[k]}", "顺序错乱")
    return nums


def check_placeholders(blocks):
    """占位符/模板残留检查。

    双括号 {{…}}/[[…]]、显式标记 TODO/XXX/PLACEHOLDER/待补/待填 确定性高 → BLOCK；
    单花括号字段 {…}（如 {本公司}/{交易日}）、模板「【填空】」标记较泛（可能误伤含花括号的
    非模板文档）→ SUGGEST，仅作提醒。覆盖 stock 模板的 {字段} 式占位正是这一条补上的。
    注意：单花括号匹配要求括号内非空且不含花括号自身（1–40 字符）。
    """
    rules = [
        (r"\[\[", "BLOCK", "PH-RESIDUE"),
        (r"\{\{", "BLOCK", "PH-RESIDUE"),
        (r"TODO|XXX|PLACEHOLDER", "BLOCK", "PH-RESIDUE"),
        (r"待补|待填", "BLOCK", "PH-RESIDUE"),
        (r"\{[^{}]{1,40}\}", "SUGGEST", "PH-BRACE"),
        (r"【填空", "SUGGEST", "PH-FILL"),
    ]
    for kind, text, style in blocks:
        for pat, lvl, code in rules:
            m = re.search(pat, text, re.I)
            if m:
                add(lvl, code, text[:40], f"疑似占位符残留：{m.group(0)[:30]}",
                    "模板字段/填空标记未替换，请核对是否全文填完")
                break


def check_dangling(blocks):
    """悬空章节引用"""
    allnums = set()
    for kind, text, style in blocks:
        if kind != "p":
            continue
        m = re.match(r"^(?:#{1,6}\s*)?([%s]+)、" % CN_NUM, text)
        if m:
            allnums.add(cn2int(m.group(1)))
    if not allnums:
        return
    ref_pat = re.compile(r"(?:见|参见|详见|如|前文)?第([%s]+)章" % CN_NUM)
    for kind, text, style in blocks:
        if kind != "p":
            continue
        for m in ref_pat.finditer(text):
            n = cn2int(m.group(1))
            if n and n not in allnums:
                add("FIX", "REF-DANGLING", text[:50], f"引用「第{m.group(1)}章」不存在", "被指章节缺失或编号已变")


def check_table_reading(blocks):
    """表/图后是否紧跟解读段"""
    for i, (kind, text, style) in enumerate(blocks):
        if kind != "table":
            continue
        nxt = ""
        for j in range(i + 1, min(i + 4, len(blocks))):
            if blocks[j][0] == "p" and len(blocks[j][1]) >= 25:
                nxt = blocks[j][1]
                break
        if not nxt:
            add("FIX", "TBL-NOREAD", text[:40], "表后无解读段（<25字或直接接下一表）", "空投表格缺结论")


def check_fig_numbering(blocks):
    """图表编号连续性：从1起、不重号、不缺号"""
    for kw in ("图", "表"):
        seen = []
        for kind, text, style in blocks:
            if kind != "p":
                continue
            m = re.match(r"^%s\s?(\d+)[：:]" % kw, text.strip())
            if m:
                seen.append((int(m.group(1)), text.strip()[:36]))
        if not seen:
            continue
        nums = [n for n, _ in seen]
        dup = {n for n in nums if nums.count(n) > 1}
        if dup:
            add("BLOCK", "FIG-DUP", f"{kw}编号", f"{kw}编号重复：{sorted(dup)}", "多章各自从1起编，读者无法定位")
        missing = [n for n in range(1, max(nums) + 1) if n not in nums]
        if missing:
            add("FIX", "FIG-GAP", f"{kw}编号", f"{kw}编号缺号：{missing}", "有图/表未编号")


def check_fig_ref(blocks):
    """正文引用图N/表N 是否有对应编号对象；反向查图注是否从未被正文引用"""
    defined = {"图": set(), "表": set()}
    for kind, text, style in blocks:
        if kind != "p":
            continue
        m = re.match(r"^(图|表)\s?(\d+)[：:]", text.strip())
        if m:
            defined[m.group(1)].add(int(m.group(2)))
    cited = {"图": set(), "表": set()}
    for kind, text, style in blocks:
        if kind != "p" or re.match(r"^(图|表)\s?\d+[：:]", text.strip()):
            continue
        for m in re.finditer(r"([图表])\s?(\d+)", text):
            cited[m.group(1)].add(int(m.group(2)))
    for kw in ("图", "表"):
        for n in sorted(cited[kw] - defined[kw]):
            add("FIX", "FIG-REF-MISS", f"正文提到{kw}{n}", f"引用{kw}{n}，但全文无「{kw}{n}：」编号对象",
                "图被删/编号改了，正文没跟上")
        orphan = sorted(defined[kw] - cited[kw])
        if orphan:
            add("SUGGEST", "FIG-UNCITED", f"{kw}编号", f"{kw}{orphan} 从未被正文引用", "读者不知为何看这张图")


def check_title_pair(blocks):
    """标题承诺 vs 章内实际：标题含「A与B」「A、B」时，两侧关键词都应在章内出现

    只对"可检验的具体对象"（行业名/产品名/主体名）判定；抽象结构词做标题标签是常态，
    要求它们在正文重现会产生大量噪音，故用 STOPWORDS 排除。
    """
    STOPWORDS = ("概况", "行情", "最新", "分析", "估值", "技术", "结论", "风险", "建议",
                 "逻辑", "财务", "行业", "公司", "产品", "业务", "竞争", "市场", "核心",
                 "要点", "综述", "概述", "展望", "策略", "判断", "思考", "小结", "总结",
                 "影响", "意义", "背景", "现状", "问题", "对策", "路径", "框架", "方法",
                 "壁垒", "梯队", "优势", "分级", "附录", "来源", "证据", "维度", "趋势",
                 "需求", "供给", "格局", "路线", "政策", "空间", "驱动", "变量", "指标",
                 "验证", "反思", "启示", "误区", "常识", "真相", "变局", "机会")
    chaps = []
    for i, (kind, text, style) in enumerate(blocks):
        if kind != "p":
            continue
        m = re.match(r"^(?:#{1,6}\s*)?([%s]+)、\s*(.+)$" % CN_NUM, text)
        if m and len(m.group(1)) <= 2:
            chaps.append({"idx": i, "title": m.group(2).strip()})
    for k, c in enumerate(chaps):
        end = chaps[k + 1]["idx"] if k + 1 < len(chaps) else len(blocks)
        body = "\n".join(t for _, t, _ in blocks[c["idx"] + 1:end])
        head = re.sub(r"^[^：:]{0,8}[：:]", "", c["title"])         # 去掉「维度四：」类前缀
        head = re.sub(r"[（(].*?[)）]", "", head)
        parts = re.split(r"[与及、]", head.split("——")[0])
        parts = [p.strip() for p in parts if 3 <= len(p.strip()) <= 6]
        if len(parts) < 2:
            continue
        for p in parts:
            if any(w in p for w in STOPWORDS):
                continue
            core = p[:4]
            if core and core not in body:
                add("SUGGEST", "TITLE-PROMISE", c["title"][:30],
                    f"标题含具体对象「{p}」，但本章正文未出现该词",
                    "标题承诺了没写，或写法不一致（同义异名）")


def check_conclusion_pos(blocks):
    """通用：结论/总结章不应埋在中段（研报另有更严的 CH-CONCL-BEFORE-VAL）"""
    chaps = []
    for i, (kind, text, style) in enumerate(blocks):
        if kind != "p":
            continue
        m = re.match(r"^(?:#{1,6}\s*)?([%s]+)、\s*(.+)$" % CN_NUM, text)
        if m and len(m.group(1)) <= 2:
            chaps.append({"num": cn2int(m.group(1)), "title": text.strip()})
    if len(chaps) < 4:
        return
    SKIP = ("核心结论", "摘要", "一页版", "执行摘要", "要点", "速览")
    hits = [c for c in chaps
            if any(w in c["title"] for w in ("结论", "总结", "小结", "结语", "收尾"))
            and not any(w in c["title"] for w in SKIP)]
    if not hits:
        return
    last = max(c["num"] for c in chaps)
    c = hits[-1]
    if c["num"] < last - 1:
        add("SUGGEST", "CH-CONCL-MID", c["title"][:30],
            f"结论章在第 {c['num']} 章，后面还有 {last - c['num']} 章",
            "若后续只是附录/说明可忽略；否则读者看完结论还要往下翻")


# ---------------------------------------------------------------- 表达类

def check_vague(blocks):
    """模糊限定词密度 + 同句堆叠"""
    full = "\n".join(t for _, t, _ in blocks if t)
    total = len(re.sub(r"\s", "", full)) or 1
    hits = sum(full.count(w) for w in VAGUE_WORDS)
    density = hits * 1000.0 / total
    if density > 8:
        add("SUGGEST", "X1-VAGUE-DENSE", "全文",
            f"模糊限定词 {hits} 处，密度 {density:.1f}/千字（偏高）",
            "「可能/有望/或将/预计」堆叠会稀释结论；换成「若X则Y」的条件句")
    for kind, text, style in blocks:
        if kind != "p" or len(text) < 12:
            continue
        n = sum(1 for w in VAGUE_WORDS if w in text)
        if n >= 3:
            add("FIX", "X1-HEDGE-STACK", text[:45], f"一句话内 {n} 个模糊限定词", "读者无法判断把握程度")


def check_unit_mix(blocks):
    """正文「倍 / %」误用与混用（按分句判，段落级会把无关指标错配成一组）"""
    GROWTH = ("增长", "提升", "下降", "下滑", "上涨", "下跌", "同比", "环比", "增速", "涨幅", "跌幅")
    for kind, text, style in blocks:
        if kind != "p" or len(text) < 6:
            continue
        for sent in re.split(r"[。；！？\n]", text):
            if len(sent) < 4:
                continue
            for m in re.finditer(r"(增长|提升|下降|下滑|上涨|下跌)[了]?\s*[\d.]+\s*倍", sent):
                add("FIX", "X2-GROWTH-BEI", sent.strip()[:45],
                    f"「{m.group(0)}」表述歧义（增长1倍=变2倍）",
                    "增速一律用 %：增长 1 倍写 +100%，是 2 倍写「为 2 倍」")
            if "倍" in sent and "%" in sent and any(w in sent for w in GROWTH):
                add("SUGGEST", "X2-MIX", sent.strip()[:45],
                    "同一句里「倍」与「%」并存且都指向增长",
                    "确认是否同一指标；同一指标只用一种口径")


def check_absolute(blocks):
    """绝对化断言：只抓"短句 + 排他性/最高级 + 无任何依据"的组合。

    长句里出现「唯一/最好」多半是复杂论证的一部分（如"唯一没有加速的是行政职能"），
    一律报会淹没真问题，故用句长与排他词双重限缩。
    """
    HARD = ("必然", "一定会", "必将", "毫无疑问", "毋庸置疑", "百分之百")
    # 只用"宣称短语"，不用裸「唯一/第一」——中文里前者多为普通描述或序号
    EXCL = ("首个", "首家", "唯一一家", "独家", "没有之一", "全球第一", "国内第一",
            "行业第一", "绝无仅有", "最好", "最强", "最优")
    for kind, text, style in blocks:
        if kind != "p" or len(text) < 8:
            continue
        for sent in re.split(r"[。；！？\n]", text):
            sent = sent.strip()
            if not sent:
                continue
            if re.match(r"^第[一二三四五六七八九十0-9]+[，,、．.]", sent):
                continue      # 序号句：「第一，…」不是在宣称排他
            got = [w for w in HARD + EXCL if w in sent]
            if not got:
                continue
            has_ev = bool(re.search(r"据|来源|年报|公告|数据|统计|报告|测算|样本|案例", sent)) or bool(re.search(r"\d", sent))
            if has_ev:
                continue
            hard_hit = any(w in sent for w in HARD)
            excl_hit = any(w in sent for w in EXCL)
            if hard_hit or (excl_hit and len(sent) <= 80) or len(sent) <= 45:
                add("FIX" if hard_hit else "SUGGEST", "E-ABSOLUTE", sent[:45],
                    f"绝对化用词（{'/'.join(got)}）且同句无任何依据",
                    "补出处、样本或条件；补不上就改成概率或条件句")


def check_source_note(blocks, genre):
    """讲事实的体裁必须有来源/口径说明"""
    if genre not in SOURCE_STRICT_GENRES:
        return
    full = "\n".join(t for _, t, _ in blocks)
    if not re.search(r"(数据来源|资料来源|来源[:：]|参考文献|口径说明|Wind|iFinD|东方财富|统计局|公司公告)", full):
        add("FIX", "E-NO-SOURCE", "全文", "未发现任何数据来源/口径说明",
            "该体裁的全文级来源标注缺失，读者无法核证")


# ---------------------------------------------------------------- 逻辑冲突 / 严谨性 / 事实 / 完整性 补强（修复项）

def _zh_windows(s):
    """抽取句子里所有 3–4 字中文窗口（只在中文字符段内滑动，避开数字/标点）"""
    out = []
    for run in re.findall(r"[\u4e00-\u9fff]+", s):
        n = len(run)
        for i in range(n):
            for L in (3, 4):
                if i + L <= n:
                    out.append(run[i:i + L])
    return out


def _sentences_with_chapter(blocks):
    """返回 [(章名, 句子)]，跳过章节标题与图/表注"""
    out, cur = [], "开头"
    for kind, text, style in blocks:
        if kind != "p":
            continue
        m = re.match(r"^(?:#{1,6}\s*)?([%s]+)、\s*(.+)$" % CN_NUM, text)
        if m and len(m.group(1)) <= 2:
            cur = text[:30]
            continue
        if re.match(r"^(图|表)\s?\d+[：:]", text.strip()):
            continue
        for s in re.split(r"[。！？；\n]", text):
            s = s.strip()
            if 12 <= len(s) <= 300:
                out.append((cur, s))
    return out


def check_contradiction(blocks):
    """R17 · 自相矛盾（命题冲突）：同一主题在全文两处给出相反方向判断。

    做法：抽 3–4 字中文实词 token（排除通用/指标名词与极性词），若某 token 至少出现在
    两句、且一句含正向极性词、另一句含负向极性词 → 疑似矛盾。要求 3–4 字精确共现，
    可避免「公司营收增长 vs 行业营收下降」这类不同主体的误报；两句都带时间词（如
    上半年/下半年）时视为合法的时间变化，跳过以防误报。
    """
    sents = _sentences_with_chapter(blocks)
    tok_index = {}
    for i, (chap, s) in enumerate(sents):
        st = s.strip()
        # 标题/章节标题行是摘要而非事实命题，不参与矛盾配对（R17 防误报：标题 vs 正文）
        if st.startswith("#"):
            continue
        pos = _has_polarity(s, CONTRA_POS)
        neg = _has_polarity(s, CONTRA_NEG)
        pol = 0 if (pos and neg) else (1 if pos else (-1 if neg else 0))
        if pol == 0:
            continue
        seen = set()
        for tok in _zh_windows(s):
            if tok in seen or len(tok) < 3:
                continue
            seen.add(tok)
            if tok in CONTRA_STOP or tok in POLARITY_ALL:
                continue
            tok_index.setdefault(tok, []).append((i, pol))
    # 同一对句子可能共享多个 3–4 字窗口，按「句子对」去重，每对只报一次（取最长共有主题）
    pair_tokens = {}
    for tok, occ in tok_index.items():
        pols = {p for _, p in occ}
        if 1 not in pols or -1 not in pols:
            continue
        p = next(o for o in occ if o[1] == 1)
        ng = next(o for o in occ if o[1] == -1)
        key = (p[0], ng[0]) if p[0] < ng[0] else (ng[0], p[0])
        if key not in pair_tokens or len(tok) > len(pair_tokens[key]):
            pair_tokens[key] = tok
    seen_pair, n = set(), 0
    for (ia, ib), tok in pair_tokens.items():
        if (ia, ib) in seen_pair:
            continue
        seen_pair.add((ia, ib))
        c1, s1 = sents[ia]
        c2, s2 = sents[ib]
        # 两句都带时间词且所指时期不同 → 多半是不同时期的合法变化，跳过（R17 防误报）
        if _has_time(s1) and _has_time(s2) and _periods(s1) != _periods(s2):
            continue
        # 两句都在谈周期/景气波动 → 上下行是周期叙事常态，非矛盾（R17 防误报）
        if _has_cycle(s1) and _has_cycle(s2):
            continue
        add("FIX", "R17-CONTRA", "%s / %s" % (c1[:16], c2[:16]),
            "疑似自相矛盾：两处对「%s」给出相反方向判断" % tok,
            "①「%s」 ②「%s」——需人工确认是否同一对象、是否真矛盾（R17）" % (s1[:46], s2[:46]))
        n += 1
        if n >= 12:
            break


def check_recompute(blocks):
    """E5 · 可复算（弱校验）：检测「由 X 到 Y，增长 Z%」类陈述，验算 Z 是否与 (Y-X)/X 一致。

    只查明确给出了起点、终点与百分比的段；其余可复算项（均值/合计/排名）仍是人工项
    （SKILL 已标注）。研报实战：正文 +100.2%、复算只得 +89.7%。
    """
    full = "\n".join(t for _, t, _ in blocks if t)
    # 顺序A：先出现「由X到Y」（中间可夹「增长/提升…」动词），附近 60 字内出现「增长 Z%」
    for m in re.finditer(r"(?:由|从)\s*([\d.]+)\s*(?:增长|提升|上升|提高|下降|降低|减少)?\s*(?:到|至|→)\s*([\d.]+)", full):
        a, b = float(m.group(1)), float(m.group(2))
        win = full[m.start():m.start() + 60]
        rm = re.search(r"增长\s*([\d.]+)\s*%", win)
        if not rm or a == 0 or b == a:
            continue
        rate, implied = float(rm.group(1)), (b - a) / a * 100
        if abs(implied - rate) > 3 and abs(implied - rate) > abs(rate) * 0.15:
            add("SUGGEST", "E5-RECOMPUTE", "全文",
                "增速复算不一致：称由 %g 到 %g 增长 %g%%，实算应为 %g%%" % (a, b, rate, implied),
                "用文中明细复算；研报实战 +100.2% 复算只得 +89.7%（E5）")
    # 顺序B：先「增长 Z%」，括号内/后接「由X到Y」
    for m in re.finditer(r"增长\s*([\d.]+)\s*%（?[^）]{0,40}?(?:由|从)\s*([\d.]+)\s*(?:到|至|→)\s*([\d.]+)", full):
        rate, a, b = float(m.group(1)), float(m.group(2)), float(m.group(3))
        if a == 0 or b == a:
            continue
        implied = (b - a) / a * 100
        if abs(implied - rate) > 3 and abs(implied - rate) > abs(rate) * 0.15:
            add("SUGGEST", "E5-RECOMPUTE", "全文",
                "增速复算不一致：称增长 %g%%，由 %g 到 %g 实算应为 %g%%" % (rate, a, b, implied),
                "用文中明细复算；研报实战 +100.2% 复算只得 +89.7%（E5）")


def check_effect_size(blocks):
    """R13 · 量级不匹配（弱校验）：量级词需配效应量，否则强度撑不起用词。"""
    for kind, text, style in blocks:
        if kind != "p" or len(text) < 12:
            continue
        for sent in re.split(r"[。；！？\n]", text):
            sent = sent.strip()
            if len(sent) < 8:
                continue
            hit = [w for w in EFFECT_WORDS if w in sent]
            if not hit:
                continue
            has_effect = bool(re.search(r"\d", sent)) or bool(re.search(r"倍|%", sent))
            if not has_effect:
                add("SUGGEST", "R13-EFFECT", text[:44],
                    "量级词「%s」需配效应量（具体百分比/倍数）" % "/".join(hit),
                    "效应量只有 3% 却写「决定性/显著」即量级不匹配（R13）")


def check_condition_clause(blocks):
    """X1 · 有望/预计 类判断缺条件句：拿模糊词逃过举证。"""
    for kind, text, style in blocks:
        if kind != "p" or len(text) < 12:
            continue
        for sent in re.split(r"[。；！？\n]", text):
            sent = sent.strip()
            if len(sent) < 8:
                continue
            if not any(w in sent for w in FORWARD_WORDS):
                continue
            has_cond = any(w in sent for w in ("若", "如果", "假如", "除非", "一旦", "前提", "假设", "情景", "条件下", "届时")) \
                or bool(re.search(r"在[^，。；]{0,12}下", sent))
            if not has_cond:
                add("SUGGEST", "X1-COND", text[:44],
                    "「有望/预计」类判断缺条件句，请补「若 X 则 Y」",
                    "拿模糊词逃过举证（X1）；补全成立条件或降级为推测")


def _sections(blocks):
    """把文档切成「标题 + 正文范围」。标题 = markdown 标题（# 起）或「一、」编号段。
    返回 [{'idx','title','start','end'}]；标题之前的内容归入「开头」段。"""
    secs, cur = [], None
    for i, (kind, text, style) in enumerate(blocks):
        if kind != "p":
            continue
        t = text.strip()
        m = re.match(r"^#{1,6}\s+(.+)$", t)
        m2 = re.match(r"^([%s]{1,2})[、.．]\s*(.+)$" % CN_NUM, t)
        if m or m2:
            if cur is not None:
                cur["end"] = i
                secs.append(cur)
            title = (m.group(1) if m else m2.group(2)).strip()
            title = re.sub(r"^[%s]{1,2}[、.．]\s*" % CN_NUM, "", title)
            cur = {"idx": i, "title": title, "start": i + 1}
    if cur is not None:
        cur["end"] = len(blocks)
        secs.append(cur)
    if not secs:
        return [{"idx": -1, "title": "（全文）", "start": 0, "end": len(blocks)}]
    if secs[0]["idx"] > 0:
        secs.insert(0, {"idx": -1, "title": "（开头）", "start": 0, "end": secs[0]["idx"]})
    return secs


def _title_hit(title, kws):
    return any(title.startswith(kw) or title == kw for kw in kws)


def check_abstract_conclusion(blocks):
    """关三·7 · 摘要与结论一致：结论提出的主张/数据若摘要完全未涉及 → 疑似不一致。"""
    secs = _sections(blocks)
    front = [s for s in secs if _title_hit(s["title"], ("摘要", "执行摘要", "核心结论", "一页版", "要点", "速览", "观点"))]
    tail = [s for s in secs if _title_hit(s["title"], ("结论", "总结", "小结", "结语", "投资建议", "投资结论", "收尾"))]
    if not front or not tail:
        return
    abs_text = "\n".join("\n".join(t for _, t, _ in blocks[s["start"]:s["end"]]) for s in front)
    conc_text = "\n".join("\n".join(t for _, t, _ in blocks[s["start"]:s["end"]]) for s in tail)
    # 1) 结论关键数据未在摘要出现
    for num in set(re.findall(r"[\d.]+%?", conc_text)):
        if len(num) >= 2 and num not in abs_text:
            add("SUGGEST", "C-ABS-CONCL-NUM", "结论/摘要",
                "结论含关键数据「%s」，摘要未提及，二者口径可能不一致" % num,
                "摘要与结论须同一件事、同一口径（关三·7）")
            break
    # 2) 结论主张的主题词在摘要完全未出现 → 疑似新增不一致
    for s in re.split(r"[。！？；\n]", conc_text):
        s = s.strip()
        if len(s) < 12 or not any(k in s for k in CLAIM_MARKERS):
            continue
        toks = set(_zh_windows(s)) - CONTRA_STOP - POLARITY_ALL
        if not any(tok in abs_text for tok in toks):
            add("SUGGEST", "C-ABS-CONCL-DIV", "结论/摘要",
                "结论主张「%s」未在摘要中体现，摘要与结论可能不一致" % s[:40],
                "摘要与结论须同一件事、同一口径（关三·7）")
            break


def check_conclusion_first(blocks, genre):
    """关三·6 · 公文/方案结论先行：结论/建议章不应压在末尾（除非开头已有摘要）。"""
    if genre not in ("report-gov", "plan"):
        return
    secs = _sections(blocks)
    if len(secs) < 3:
        return
    front_exist = any(_title_hit(s["title"], ("摘要", "执行摘要", "核心结论", "一页版", "要点")) for s in secs)
    for pos, s in enumerate(secs, 1):
        if _title_hit(s["title"], ("建议", "对策", "措施", "结论", "总结", "下一步", "工作打算", "打算")) \
                and pos > max(1, round(len(secs) * 2 / 3)) and not front_exist:
            add("SUGGEST", "C-CONCL-NOT-FIRST", s["title"][:30],
                "公文/方案体裁：结论应前置（结论先行），当前结论/建议章偏后",
                "领导先看第一段；建议把核心结论/建议提到开头或独立摘要（关三·6）")


# ---------------------------------------------------------------- 关四 · 逻辑缺失补强（v1.1.2）

STRONG_CLAIM = ("因此", "所以", "说明", "表明", "证明", "反映出", "意味着", "结论是",
                "可见", "由此", "综上", "由此可见", "由此可知", "关键在于", "核心是",
                "本质是", "不难看出", "足以说明")

# 汇总章白名单：这些章本来就是结论/摘要，不要求内部论证，排除防误报
_LOGIC_GAP_SKIP = ("摘要", "执行摘要", "核心结论", "一页版", "要点", "速览", "观点",
                   "结论", "总结", "小结", "结语", "投资建议", "投资结论", "收尾",
                   "附录", "数据来源", "免责", "说明", "参考文献", "目录", "引言", "前言")
# 证据供给信号：数字 + 下列任一（或指向图/表）
_LOGIC_GAP_DATA = (r"\d", "数据", "年报", "公告", "来源", "统计", "测算", "调研", "样本",
                   "案例", "显示", "据", "研报", "文献", "图表", "披露", "报告", "口径",
                   "同比", "环比", "增速", "增幅", "%", "亿元", "万元", "GWh", "万台", "倍")
_LOGIC_GAP_FIG = r"如图|见图|如下表|见下表|图\s?\d|表\s?\d|图表\s?\d"
_LOGIC_GAP_MECH = ("因为", "由于", "导致", "带动", "源于", "通过", "机制", "传导", "取决于",
                   "依赖", "驱动", "使得", "从而", "在于", "受.*影响", "受制于", "背后是",
                   "本质上是", "根源", "推手", "关键在", "得益于", "受益于", "其原因是")


def check_logic_gap(blocks):
    """关四 · 逻辑缺失（v1.1.2 新增）：论证章甩出结论，但整节既无证据供给、也无机制说明。

    与 check_reasoning 的「逐句五落点」互补：那个看单句窗口（前2后1），这个看整节供给。
    只查「非汇总章」——摘要/结论/投资建议/收尾等允许只做总结，否则把总结章误判为缺失。
    指向图N/表N（视觉证据）也视为有供给，因为图内文字是像素、脚本读不到（避免误报）。
    """
    secs = _sections(blocks)
    for s in secs:
        title = s["title"]
        if any(title.startswith(k) or title == k for k in _LOGIC_GAP_SKIP):
            continue
        body = "\n".join(t for _, t, _ in blocks[s["start"]:s["end"]])
        has_data = (bool(re.search(r"\d", body)) and bool(re.search("|".join(_LOGIC_GAP_DATA[1:]), body))) \
            or bool(re.search(_LOGIC_GAP_FIG, body))
        has_mech = bool(re.search("|".join(_LOGIC_GAP_MECH), body))
        if has_data or has_mech:
            continue                                    # 整节有供给 → 不算逻辑缺失
        hits = [t.strip() for _, t, _ in blocks[s["start"]:s["end"]]
                if t and len(t) >= 18 and any(mk in t for mk in STRONG_CLAIM)]
        if not hits:
            continue                                    # 该节无强结论 → 不报（过渡段/空壳章天然不含强结论）
        add("SUGGEST", "L4-LOGIC-GAP", title[:30],
            "逻辑缺失：本章给出结论性判断，但整节未见证据供给或机制说明",
            "从证据到主张那一跳走不通（关四）；补数据/案例或机制链（R3/R1）。例如：「%s」" % hits[0][:36])


# ---------------------------------------------------------------- 主张—证据对照

def build_claim_table(blocks):
    """抽出结论性句子，并附上最接近的、含数字的前文，作为证据候选（供人工填表）"""
    claims = []
    chap = ""
    for i, (kind, text, style) in enumerate(blocks):
        if kind != "p":
            continue
        m = re.match(r"^(?:#{1,6}\s*)?([%s]+)、" % CN_NUM, text)
        if m:
            chap = text[:40]
            continue
        if len(text) < 12 or text.endswith("？") or text.endswith("?"):
            continue
        if re.match(r"^(图|表)\s?\d+[：:]", text):
            continue
        if not any(k in text for k in CLAIM_MARKERS):
            continue
        ev = ""
        if re.search(r"\d", text) and len(text) >= 10:
            ev = "（本句自带数字）" + text[:76]
        else:
            for j in range(i - 1, max(-1, i - 4), -1):
                if blocks[j][0] == "p" and re.search(r"\d", blocks[j][1]) and len(blocks[j][1]) >= 10:
                    ev = blocks[j][1][:80]
                    break
        claims.append({
            "pos": chap or "开头",
            "claim": text[:120],
            "evidence_candidate": ev or "（前文无含数字句，需人工确认证据在哪）",
            "marker": next((k for k in CLAIM_MARKERS if k in text), ""),
        })
    if len(claims) > 60:
        add("SUGGEST", "CLAIM-MANY", "全文", f"识别出 {len(claims)} 条结论句（>60）",
            "主张密度过高，读者难抓主线；建议每章留 1–3 条主结论")
    return claims


# ---------------------------------------------------------------- 研报档专项

def check_industry_matrix(blocks, industry, alt):
    """行业标签矩阵：列出主口径/邻接口径出现位置，供语义判断"""
    if not industry:
        return None

    def scan(word):
        hits = []
        for kind, text, style in blocks:
            if word and word in text:
                hits.append({"pos": text[:36], "kind": kind})
        return hits
    matrix = {"primary": {"word": industry, "hits": scan(industry)},
              "alt": {"word": alt, "hits": scan(alt) if alt else []}}
    pa, pb = len(matrix["primary"]["hits"]), len(matrix["alt"]["hits"])
    if pa == 0:
        add("BLOCK", "IND-ABSENT", "全文", f"主行业「{industry}」在全文未出现", "口径可能整体跑偏")
    if alt and pb and pa:
        add("SUGGEST", "IND-MIXED", "全文",
            f"主行业「{industry}」出现 {pa} 处、邻接口径「{alt}」出现 {pb} 处",
            "需人工判断是否「标题挂A、数据用B」混搭（脚本无法定性）")
    return matrix


def check_primary_order(blocks, industry, alt):
    """主次物理顺序：文本声明 X 为主口径时，X 对应的图/表须排在 Y 之前"""
    if not (industry and alt):
        return
    decl = None
    for kind, text, style in blocks:
        if kind == "p" and industry in text and alt in text and re.search(r"主(口径|业)|为主", text):
            if text.find(industry) < text.find(alt):
                decl = (industry, alt, text[:60])
                break
    if not decl:
        return
    prim, sec, where = decl
    seq = []
    for kind, text, style in blocks:
        if kind != "p":
            continue
        m = re.match(r"^(图|表)\s?\d+[：:]\s*(.{0,50})", text.strip())
        if not m:
            continue
        cap = m.group(2)
        if prim in cap:
            seq.append(prim)
        elif sec in cap:
            seq.append(sec)
    if len(seq) >= 2 and seq[0] != prim:
        add("BLOCK", "ORDER-INVERT", where,
            f"主次顺序颠倒：声明「{prim}」为主口径，但文档中先出现「{seq[0]}」",
            "只改了文字标签、没调数据块顺序（海目星 v2 事故）")
    elif seq:
        add("SUGGEST", "ORDER-OK", where, f"图表出现顺序：{seq}（与声明主次一致）", "")


def check_chapter_logic(blocks):
    """研报章序与主题单一性（A1 风险末章 / A2 结论在估值后 / A3 主题混杂）"""
    chaps = []
    for i, (kind, text, style) in enumerate(blocks):
        if kind != "p":
            continue
        m = re.match(r"^(?:#{1,6}\s*)?([%s]+)、\s*(.+)$" % CN_NUM, text)
        if m and len(m.group(1)) <= 2:
            chaps.append({"idx": i, "num": cn2int(m.group(1)), "title": text.strip()})
    if len(chaps) < 3:
        return
    for k, c in enumerate(chaps):
        c["end"] = chaps[k + 1]["idx"] if k + 1 < len(chaps) else len(blocks)
        c["body"] = "\n".join(t for _, t, _ in blocks[c["idx"] + 1:c["end"]])

    def find(words):
        return [c for c in chaps if any(w in c["title"] for w in words)]

    risk = find(["风险提示", "风险因素", "风险分析"])
    if risk:
        r = risk[-1]
        tail = [c for c in chaps if c["num"] > r["num"]]
        tail_ok = [c for c in tail if any(w in c["title"] for w in ("附录", "数据来源", "免责", "说明"))]
        bad = [c for c in tail if c not in tail_ok]
        if bad:
            add("BLOCK", "CH-RISK-NOT-LAST", r["title"][:30],
                f"风险提示不是正文末章，其后还有：{'、'.join(c['title'][:18] for c in bad)}",
                "风险应置于正文最后（其后只允许数据来源/免责声明/附录）")

    concl = find(["小结", "结论", "投资建议", "投资结论"])
    VAL_MARK = ("估值通道", "情景推演", "PS(", "PS（", "分位")
    val = []
    for c in chaps:
        if any(w in c["title"] for w in ("风险", "附录", "数据来源", "免责")):
            continue
        if any(w in c["title"] for w in ("估值", "PS", "PE", "情景")) or \
           sum(1 for w in VAL_MARK if w in c["body"]) >= 2:
            val.append(c)
    if concl and val:
        if max(c["num"] for c in concl) < max(c["num"] for c in val):
            add("FIX", "CH-CONCL-BEFORE-VAL", concl[-1]["title"][:30],
                f"结论章（第{concl[-1]['num']}章）排在估值章（第{max(c['num'] for c in val)}章）之前",
                "结论未覆盖估值，读者看完结论仍需往下翻；应把结论章移到估值之后")

    for c in chaps:
        if "技术" in c["title"] and not any(w in c["title"] for w in ("估值", "PS", "情景")):
            hits = [w for w in ("估值通道", "PS", "情景推演", "分位") if w in c["body"]]
            if len(hits) >= 2:
                add("SUGGEST", "CH-THEME-MIX", c["title"][:30],
                    f"标题为「{c['title'][:12]}」，但章内含 {'/'.join(hits)} 等估值内容",
                    "修法是并题改标题（一章一主题），不是拆出新章——章多时拆章只是把混杂搬进目录")


# ---------------------------------------------------------------- 入口

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--genre", default="",
                    choices=["", "general"] + sorted(GENRE_DEFAULTS.keys()),
                    help="体裁；不填则按参数推断（有 --industry 视为 research）")
    ap.add_argument("--must-have", action="append", default=[])
    ap.add_argument("--industry", default="")
    ap.add_argument("--industry-alt", default="")
    ap.add_argument("--claim-table", action="store_true", help="输出「主张→证据」对照表")
    ap.add_argument("--lang", default="zh", choices=["zh", "en"],
                    help="文档语言：zh 中文（默认）/ en 英文（跳过中文专属机械关，六关语义推理由 LLM 对英文文本执行）")
    a = ap.parse_args()
    if not os.path.isfile(a.path):
        ap.error(f"找不到文件：{a.path}")


    blocks = load_blocks(a.path)
    if not blocks:
        print("未抽取到任何内容（空文件或抽取失败）")
        return 2

    genre = a.genre or ("research" if a.industry else "general")
    must = a.must_have or GENRE_DEFAULTS.get(genre, [])

    check_chapters(blocks)
    check_placeholders(blocks)
    check_dangling(blocks)
    check_table_reading(blocks)
    check_fig_numbering(blocks)
    check_fig_ref(blocks)
    check_title_pair(blocks)
    check_vague(blocks)
    check_unit_mix(blocks)
    check_absolute(blocks)
    check_source_note(blocks, genre)
    if genre == "research":
        check_chapter_logic(blocks)
    elif genre not in ("report-gov", "plan"):
        # 公文/方案要求结论先行，不查"结论是否在最末"
        check_conclusion_pos(blocks)
    else:
        # 公文/方案：查结论是否前置（关三·6）
        check_conclusion_first(blocks, genre)
    check_must_have(blocks, must)
    matrix = check_industry_matrix(blocks, a.industry, a.industry_alt)
    check_primary_order(blocks, a.industry, a.industry_alt)
    # 全体裁补强：逻辑冲突 / 事实可复算 / 严谨性量级 / 有望条件句 / 摘要结论一致
    # 自相矛盾机械关依赖 3–4 字中文窗口，仅中文有效；英文交给 LLM 六关推理覆盖
    if a.lang == "zh":
        check_contradiction(blocks)
    else:
        print("（en 模式：跳过中文专属「自相矛盾」机械关；语义矛盾由 LLM 六关推理覆盖）")
    check_recompute(blocks)
    check_effect_size(blocks)
    check_condition_clause(blocks)
    check_abstract_conclusion(blocks)
    check_logic_gap(blocks)   # 关四·逻辑缺失（全体裁）
    claims = build_claim_table(blocks) if a.claim_table else []

    order = {"BLOCK": 0, "FIX": 1, "SUGGEST": 2}
    findings.sort(key=lambda f: order.get(f["level"], 9))
    cnt = {k: sum(1 for f in findings if f["level"] == k) for k in ("BLOCK", "FIX", "SUGGEST")}

    print(f"=== 机械检查 · {os.path.basename(a.path)} · 体裁={genre} ===")
    must_txt = "、".join((m[0] if isinstance(m, (list, tuple)) and m else str(m)) for m in must) or "（未指定）"
    print(f"抽取块数: {len(blocks)}  |  必写要素: {must_txt}")
    if matrix:
        print(f"[行业标签] 主「{matrix['primary']['word']}」{len(matrix['primary']['hits'])} 处 / "
              f"邻接「{matrix['alt']['word']}」{len(matrix['alt']['hits'])} 处")
    for f in findings:
        print(f"[{f['level']}] {f['code']} @ {f['pos']} :: {f['msg']} — {f['detail']}")
    if not findings:
        print("无机械级问题（注意：主张是否成立、推理是否终结，仍需语义复核）")

    if claims:
        print(f"\n--- 主张→证据 对照（共 {len(claims)} 条，证据列需人工确认） ---")
        for n, c in enumerate(claims[:20], 1):
            print(f"{n}. [{c['pos']}] {c['claim']}")
            print(f"   证据候选：{c['evidence_candidate']}")
        if len(claims) > 20:
            print(f"… 其余 {len(claims) - 20} 条见 JSON")

    print(f"\n汇总: BLOCK={cnt['BLOCK']} FIX={cnt['FIX']} SUGGEST={cnt['SUGGEST']}")

    out = os.path.splitext(a.path)[0] + "_audit.json"
    json.dump({"file": a.path, "genre": genre, "counts": cnt, "findings": findings,
               "industry_matrix": matrix, "claims": claims},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"明细已存: {out}")
    return 1 if cnt["BLOCK"] else 0


def check_must_have(blocks, must_have):
    """必写要素检查：每组是同义写法（list 或 "A/B" 形式），命中任一即算在位"""
    full = "\n".join(t for _, t, _ in blocks)
    for item in must_have or []:
        group = item if isinstance(item, (list, tuple)) else str(item).split("/")
        group = [g.strip() for g in group if g and g.strip()]
        if not group:
            continue
        if not any(g in full for g in group):
            add("BLOCK", "MUST-MISS", "全文",
                f"必写内容缺失：{group[0]}" + (f"（或其同义写法 {'/'.join(group[1:])}）" if len(group) > 1 else ""),
                "克隆模板漏整节 / 体裁要素缺失")


if __name__ == "__main__":
    sys.exit(main())
