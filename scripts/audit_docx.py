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

CN_NUM = "一二三四五六七八九十"

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

findings = []


def add(level, code, pos, msg, detail=""):
    """level: BLOCK / FIX / SUGGEST"""
    findings.append({"level": level, "code": code, "pos": pos, "msg": msg, "detail": detail})


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
    pats = [r"\[\[", r"\{\{", r"TODO", r"XXX", r"PLACEHOLDER", r"待补", r"待填"]
    for kind, text, style in blocks:
        for p in pats:
            if re.search(p, text, re.I):
                add("BLOCK", "PH-RESIDUE", text[:40], f"占位符残留：{p}", "内容/图片/变量未替换")
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
    a = ap.parse_args()

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
    check_must_have(blocks, must)
    matrix = check_industry_matrix(blocks, a.industry, a.industry_alt)
    check_primary_order(blocks, a.industry, a.industry_alt)
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
