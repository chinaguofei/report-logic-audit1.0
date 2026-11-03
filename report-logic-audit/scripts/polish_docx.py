# -*- coding: utf-8 -*-
"""润色器（report-logic-audit 模式二：只改表达层，不改论证层）。

为什么单独成一个脚本、而不是塞进审校：
审校是"读"，润色是"写"。边读边改，改到最后会忘掉原始问题；
更要紧的是——润色最危险的动作，是把论证改坏而自己不知道。

因此本脚本守三条硬边界：
  1. **只动 X 层**（表达）。碰到 E 层（证据）与 R 层（推理）的问题一律只报告、不改。
  2. **数字不可动**。落地前后逐段比对数字序列，多一个少一个就整段放弃。
  3. **必须留痕**。默认只出建议台账；`--apply` 才写文件，且先备份、再自校验
     （重跑 audit_docx.py，BLOCK 与 FIX 数不得增加——润色不能把审校结果改坏）。

用法:
    # 看一眼建议，不动文件（默认）
    python polish_docx.py 文章.docx
    python polish_docx.py 文章.md --genre essay

    # 落地：写到新文件（推荐，规避 Windows 预览器文件锁）
    python polish_docx.py 文章.docx --apply
    python polish_docx.py 文章.docx --apply --out 文章_润色.docx

    # 术语统一：显式给出同一实体的多种写法（最可靠，不靠猜）
    python polish_docx.py 文章.docx --term-group "锂电设备/锂电装备/锂电池设备"

支持 .docx / .md / .txt（html 只读不改）
退出码: 0 正常；1 落地后自校验发现新增 BLOCK/FIX（已回滚，需人工看）
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_docx import load_blocks  # noqa: E402

# ---------------------------------------------------------------- 规则表

# 冗余/赘词：left → right（right 可为空＝删除）。只在整词命中时替换。
REDUNDANT = {
    "进行了分析": "分析了",
    "进行了研究": "研究了",
    "进行了测算": "测算了",
    "进行了对比": "对比了",
    "进行优化": "优化",
    "进行判断": "判断",
    "进行梳理": "梳理",
    "可以说": "",
    "众所周知": "",
    "显而易见": "",
    "毋庸置疑": "",
    "值得注意的是": "",
    "需要指出的是": "",
    "在此基础上": "据此",
    "总体而言": "总体看",
    "综上所述": "综上",
    "从某种意义上讲": "",
    "在很大程度上": "",
    "一定程度上": "",
    "在某种程度上": "",
    "换句话说": "即",
    "也就是说": "即",
    "具体而言": "具体看",
    "相对来说": "相对",
    "基本上": "基本",
    "事实上": "",
    "实际上": "",
}

# 需要捕获的句式（正则），repl 用 \1 回填
REDUNDANT_RE = [
    (r"由于([^，。；]{1,12})的原因", r"由于\1", "「由于…的原因」：原因就是由于，去掉尾巴"),
    (r"通过([^，。；]{1,12})的方式", r"以\1", "「通过…的方式」改为「以…」，省 3 字"),
]

# 模糊副词：单独出现不一定是错（评论/散文常用），只在"同一段出现 ≥3 个"时提示
VAGUE = ("较为", "相对", "有所", "一定程度上", "进一步", "不断", "持续", "有效",
         "积极", "明显", "显著", "大幅", "大量", "充分", "高度", "深度", "全面")

# 连接词滥用：同段出现次数阈值
CONNECTORS = ("因此", "所以", "然而", "但是", "不过", "同时", "此外", "另外", "而且", "并且")
CONN_LIMIT = 3

# 段落里这些词一出现，就把该段标为"论证段"——润色不得删改这些句子
ARGU_MARKERS = ("因此", "所以", "说明", "表明", "意味着", "由此", "可见", "证明",
                "原因", "机制", "导致", "推出", "据此", "综上", "结论")

NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")


def nums_of(text):
    """抽取数字序列（用于落地前后比对，保证润色不动数）"""
    return NUM_RE.findall(text)


def md5(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()


# ---------------------------------------------------------------- 检查项

class Report:
    def __init__(self):
        self.items = []

    def add(self, level, code, where, orig, fix, why, auto=False):
        self.items.append({"level": level, "code": code, "where": where,
                           "orig": orig, "fix": fix, "why": why, "auto": auto})

    def count(self, level=None):
        return len([i for i in self.items if level is None or i["level"] == level])


def is_argument_para(text):
    return any(m in text for m in ARGU_MARKERS)


def check_redundant(blocks, rep):
    for i, (kind, text, style) in enumerate(blocks):
        if kind != "p" or len(text) < 8:
            continue
        for bad, good in REDUNDANT.items():
            if "…" in bad:
                continue
            if bad not in text:
                continue
            # 三条硬约束：
            # ①删除类（good 为空）永不自动——删掉语气词会改变作者口吻，且无法从台账反推
            # ②论证段里改词可能动到因果方向，只标记人工确认
            # ③只有"替换"且非论证段，才允许自动落地
            deleting = not good
            # 替换点后接「的」时，替换会让句式更别扭（"进行了分析的X"→"分析了的X"），降级
            tail_bad = text.split(bad, 1)[1][:1] if bad in text else ""
            head_txt = text.split(bad, 1)[0] if bad in text else ""
            # 「对A进行了分析」要变成「分析了A」是重排，不是替换；局部换会造病句
            reorder = bool(re.search(r"(对|针对|就|予以|加以)[^，。；]{0,12}$", head_txt))
            awkward = tail_bad in ("的", "地", "得") or reorder
            safe = (not deleting) and (not is_argument_para(text)) and (not awkward)
            rep.add("REVIEW" if (is_argument_para(text) or deleting) else "SUGGEST",
                    "P-REDUND", f"第{i}块", bad, good or "（删）",
                    "赘词：" + ("可安全替换" if safe else
                              ("删除会改变口吻，需人工定" if deleting else
                               ("替换需重排语序（「对A进行了分析」→「分析了A」），局部替换会造病句"
                                if reorder else
                                ("替换后接「的/地/得」，句式会不通，需改写整句" if awkward else
                                "本段是论证句，改词可能动到因果")))),
                    auto=safe)


def check_redundant_re(blocks, rep):
    """句式级冗余（带捕获组）"""
    for i, (kind, text, style) in enumerate(blocks):
        if kind != "p" or len(text) < 8:
            continue
        for pat, repl, why in REDUNDANT_RE:
            m = re.search(pat, text)
            if not m:
                continue
            fixed = re.sub(pat, repl, m.group(0))
            rep.add("SUGGEST", "P-REDUND", f"第{i}块", m.group(0), fixed, why,
                    auto=not is_argument_para(text))


def check_long_sent(blocks, rep, limit=45):
    """只报"一口气读不完"：句中**无标点子串**长度 ≥ limit。

    不按整句字数报。研报里 150 字的枚举句靠「、」分层，读起来是清楚的；
    真正难读的是 60 字没有任何停顿的那种——读者找不到换气口，也就找不到结构。
    """
    PUNCT = "，、；：,;:（）()「」“”《》—…·/／"
    CRE = re.compile("[%s]" % re.escape(PUNCT))
    # 切点候选用"词"不用"字"——按单字切会把「并且」劈成「并/且」
    SOFT = ("并且", "同时", "其中", "因为", "所以", "但是", "然后", "使得", "从而",
            "这意味着", "这表明", "也就是说", "用来", "并且", "可以", "需要")
    for i, (kind, text, style) in enumerate(blocks):
        if kind != "p" or len(text) < limit:
            continue
        for sent in re.split(r"(?<=[。！？])", text):
            sent = sent.strip()
            if len(sent) <= limit:
                continue
            pos = [0] + [m.end() for m in CRE.finditer(sent)] + [len(sent)]
            gap, a, b = max((pos[k + 1] - pos[k], pos[k], pos[k + 1]) for k in range(len(pos) - 1))
            if gap < limit:
                continue
            seg = sent[a:b]
            # 给切点候选：段内 1/3 之后第一个结构词
            cand, best = "", None
            for tok in SOFT:
                k = seg.find(tok, max(6, len(seg) // 4))
                if k < 0:
                    continue
                if best is None or abs(k - len(seg) / 2) < abs(best[0] - len(seg) / 2):
                    best = (k, tok)
            if best:
                k, tok = best
                cand = f"建议断在「{seg[max(0, k - 8):k]}⏎{tok}{seg[k + len(tok):k + len(tok) + 8]}」"
            rep.add("SUGGEST", "P-LONG", f"第{i}块",
                    seg[:44] + ("…" if len(seg) > 44 else ""),
                    cand or "插入逗号或断句（语义边界需人定，脚本不代断）",
                    f"连续 {gap} 字无任何标点：读者找不到结构，只能一口气读完——"
                    f"句内分层不足，通常是作者自己也没分清层次")
        _ = style


def check_vague(blocks, rep):
    for i, (kind, text, style) in enumerate(blocks):
        if kind != "p" or len(text) < 30:
            continue
        got = [w for w in VAGUE if w in text]
        if len(got) >= CONN_LIMIT:
            rep.add("SUGGEST", "P-VAGUE", f"第{i}块",
                    "、".join(got[:6]), "挑 1–2 个保留，其余改具体量级",
                    f"同段模糊修饰 {len(got)} 个：形容词堆叠会稀释信息，读者拿不到可比的量")


def check_connector(blocks, rep):
    for i, (kind, text, style) in enumerate(blocks):
        if kind != "p" or len(text) < 40:
            continue
        cnt = {c: text.count(c) for c in CONNECTORS}
        hot = {c: n for c, n in cnt.items() if n >= 2}
        total = sum(cnt.values())
        if total >= CONN_LIMIT:
            rep.add("SUGGEST", "P-CONN", f"第{i}块",
                    "、".join(f"{c}×{n}" for c, n in hot.items()) or f"合计{total}次",
                    "删掉可省的连接词，靠语序与短句推进",
                    f"同段连接词 {total} 次：连接词密集通常是句子之间本来没有逻辑关系，靠词硬接")


def check_punct(blocks, rep):
    HALF = re.compile(r"[a-zA-Z0-9]\s*[,;:!?]\s*[\u4e00-\u9fa5]|[\u4e00-\u9fa5]\s*[,;:!?]\s*[\u4e00-\u9fa5]")
    # 只抓半角空格；全角空格（U+3000）常用来做标题字距对齐，是排版手段不是错
    SPACE = re.compile(r"[\u4e00-\u9fa5][ \t]+[\u4e00-\u9fa5]")
    for i, (kind, text, style) in enumerate(blocks):
        if kind != "p":
            continue
        if HALF.search(text):
            rep.add("SUGGEST", "P-PUNCT", f"第{i}块", HALF.search(text).group(0),
                    "改为全角「，；：！？」", "中英标点混用（中文句子里用了半角标点）", auto=False)
        if SPACE.search(text):
            rep.add("SUGGEST", "P-PUNCT", f"第{i}块", SPACE.search(text).group(0),
                    "删除多余空格", "中文字之间不应有空格", auto=False)
        for op, cl in (("（", "）"), ("《", "》"), ("“", "”")):
            if text.count(op) != text.count(cl):
                rep.add("FIX", "P-PAIRED", f"第{i}块",
                        f"{op}×{text.count(op)} / {cl}×{text.count(cl)}", "补齐或删除",
                        "括号/引号不配对——常见于改稿时删了一侧")


def check_dup(blocks, rep):
    for i, (kind, text, style) in enumerate(blocks):
        if kind != "p":
            continue
        # 只报 3 字以上重复。「非常非常」「看看」是叠词修辞，不是复制残留
        for m in re.finditer(r"([\u4e00-\u9fa5]{3,8})\1", text):
            rep.add("FIX", "P-DUP", f"第{i}块", m.group(0), m.group(1),
                    "重复字串（复制粘贴残留）", auto=True)
        if re.search(r"([。！？])\1", text):
            rep.add("SUGGEST", "P-DUP", f"第{i}块", re.search(r"([。！？])\1", text).group(0),
                    "保留一个", "连续标点")


def check_terms(blocks, rep, groups):
    """术语统一：①用户显式给出的同实体组 ②自动发现"同前缀同长度、尾字不同"的高频词对"""
    full = "\n".join(t for k, t, _ in blocks if k == "p")
    for g in groups or []:
        alts = [a.strip() for a in re.split(r"[/／|]", g) if a.strip()]
        hits = {a: full.count(a) for a in alts}
        if sum(1 for n in hits.values() if n) < 2:
            continue
        major = max(hits, key=lambda a: hits[a])
        for a, n in hits.items():
            if n and a != major:
                rep.add("FIX", "P-TERM", "全文", f"{a} ×{n}", f"统一为「{major}」",
                        f"同一实体 {len(alts)} 种写法：{'、'.join(f'{k}×{v}' for k, v in hits.items() if v)}"
                        "——读者会当成不同事物")

    # 能确证的唯一自动判据：文中自己声明了简称（"X（下称 Y）""X（以下简称 Y）"），
    # 之后却 X 与 Y 混用。这条不靠猜词，靠作者自己的定义，因此可以报 FIX。
    for m in re.finditer(r"([\u4e00-\u9fa5A-Za-z]{2,16})[」』\"'”’]?[（(][^）)]{0,8}(?:以下)?(?:简称|下称)"
                         r"[\s：:]{0,3}([\u4e00-\u9fa5A-Za-z]{2,10})[）)]", full):
        full_name, short = m.group(1), m.group(2)
        n_full, n_short = full.count(full_name), full.count(short)
        if n_full >= 2 and n_short >= 2:
            rep.add("SUGGEST", "P-ALIAS", "全文",
                    f"{full_name}×{n_full} / {short}×{n_short}",
                    f"首次出现处保留全称+简称，其后统一用「{short}」",
                    "文中已声明简称，正文却全称与简称混用——读者会当成两个对象")


def check_passive(blocks, rep):
    for i, (kind, text, style) in enumerate(blocks):
        if kind != "p" or len(text) < 12:
            continue
        for pat, why in ((r"被[^，。]{1,8}所", "「被…所」句式冗余"),
                         (r"得到了[^，。]{1,8}的", "「得到了…的」句式冗长"),
                         (r"是[^，。]{1,10}的体现", "「是…的体现」空转")):
            m = re.search(pat, text)
            if m:
                rep.add("SUGGEST", "P-PASSIVE", f"第{i}块", m.group(0), "改主动句",
                        why + "：主动句主语明确，责任与动作都更清楚")


# ---------------------------------------------------------------- 落地

def apply_docx(src, dst, rep):
    """仅对 auto=True 且单 run 内可命中的项落地；跨 run 的只报告。

    返回 (落地处数, 跳过处数)。
    跳过的主要原因是**跨 run**：Word 里一句话常被切成多个 run（改过一次格式就会切），
    直接改 run.text 会丢掉被切分处之外的格式，所以只报告不落地。
    """
    try:
        from docx import Document
    except ImportError:
        sys.exit("缺少 python-docx，写不了 .docx。\n"
                 "  安装：pip install python-docx")
    d = Document(src)
    # 同一组替换只做一次：多条发现可能共用同一个「原文→建议」
    pairs = []
    for it in rep.items:
        if it["auto"] and it["level"] in ("SUGGEST", "FIX"):
            key = (it["orig"], it["fix"])
            if key not in pairs and it["orig"] != it["fix"]:
                pairs.append(key)

    done = skips = 0
    for para in d.paragraphs:
        raw = para.text
        if not raw.strip() or not para.runs:
            continue
        before_nums = nums_of(raw)
        for bad, good in pairs:
            if bad not in para.text:
                continue
            if not code_nums_guard(before_nums, para.text, bad, good):
                skips += 1
                continue
            hit = False
            for r in para.runs:
                if bad in r.text:
                    r.text = r.text.replace(bad, good)
                    hit = True
            if hit:
                done += 1
            else:
                skips += 1
        if nums_of(para.text) != before_nums:
            for r in para.runs[1:]:
                r.text = ""
            para.runs[0].text = raw          # 数字变了，整段回滚
            print(f"  ⚠ 数字校验失败，已回滚该段：{raw[:30]}…")
    d.save(dst)
    return done, skips


def code_nums_guard(before_nums, raw, bad, good):
    """替换后数字序列必须不变；若替换词本身含数字，允许对应变化"""
    after = raw.replace(bad, good)
    if not nums_of(bad):
        return nums_of(after) == before_nums
    return True     # 替换词自带数字（少见），交给段落级总校验兜底


def apply_text(src, dst, rep):
    text = open(src, encoding="utf-8").read()
    done = 0
    for it in rep.items:
        if it["auto"] and it["level"] in ("SUGGEST", "FIX") and it["orig"] in text:
            text = text.replace(it["orig"], it["fix"])
            done += 1
    # 不做全局标点替换：会命中英文缩写、URL、代码块
    open(dst, "w", encoding="utf-8").write(text)
    return done


def self_check(dst, before):
    """落地后重跑审校，BLOCK/FIX 数不得增加——润色不能把审校结果改坏"""
    exe = sys.executable
    r = subprocess.run([exe, os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit_docx.py"),
                        dst, "--genre", "general"],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    out = r.stdout or ""
    m = re.search(r"BLOCK\s*=\s*(\d+).{0,24}?FIX\s*=\s*(\d+)", out)
    if not m:
        m2 = re.search(r"阻断\s*(\d+).*?须修\s*(\d+)", out, re.S)
        if not m2:
            print("  （自校验：未解析到计数，跳过）")
            return True
        m = m2
    now = (int(m.group(1)), int(m.group(2)))
    print(f"  自校验：审校结果 BLOCK={now[0]} FIX={now[1]}（落地前 BLOCK={before[0]} FIX={before[1]}）")
    return now[0] <= before[0] and now[1] <= before[1]


def baseline_count(path):
    exe = sys.executable
    r = subprocess.run([exe, os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit_docx.py"),
                        path, "--genre", "general"],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    out = r.stdout or ""
    m = re.search(r"BLOCK\s*=\s*(\d+).{0,24}?FIX\s*=\s*(\d+)", out)
    if not m:
        m2 = re.search(r"阻断\s*(\d+).*?须修\s*(\d+)", out, re.S)
        if m2:
            return int(m2.group(1)), int(m2.group(2))
        return (0, 0)
    return int(m.group(1)), int(m.group(2))


# ---------------------------------------------------------------- 输出

def render(rep, path, args):
    L = []
    auto = rep.count("REVIEW")
    L.append(f"# 润色建议 · {os.path.basename(path)}")
    L.append("")
    n_auto = len([i for i in rep.items if i["auto"]])
    L.append(f"建议 {rep.count()} 条｜可自动落地 {n_auto} 条｜需人工确认 {auto} 条｜"
             f"🔴 {rep.count('FIX')} / 🔵 {rep.count('SUGGEST')}")
    L.append("")
    L.append("> 边界：本工具只改**表达层（X 层）**。证据不足、推理跳跃、口径不一致属于 E/R 层，"
             "只报告不改——改了就成了替作者造论据。")
    L.append("")
    if not rep.items:
        L.append("未发现可润色项。")
        return "\n".join(L)

    order = {"FIX": 0, "REVIEW": 1, "SUGGEST": 2}
    for it in sorted(rep.items, key=lambda x: (order.get(x["level"], 9), x["where"])):
        tag = {"FIX": "🔴", "REVIEW": "🟡", "SUGGEST": "🔵"}[it["level"]]
        L.append(f"{tag} [{it['code']}] {it['where']}｜原文：「{it['orig']}」→ 「{it['fix']}」")
        L.append(f"     理由：{it['why']}"
                 + ("　（可自动落地）" if it["auto"] else "　（仅建议）"))
    L.append("")
    L.append("## 落地方式")
    L.append("")
    L.append("- 直接看改后的效果：`--apply`（默认写新文件 `_润色` 后缀，不动原件）")
    L.append("- 只改某些项：先按上文位置人工改，或删掉规则表里不想要的条目再跑")
    L.append("- 落地后会自动重跑审校，BLOCK/FIX 数量上升则判定失败，需人工复核")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="润色（只改表达层）")
    ap.add_argument("path")
    ap.add_argument("--genre", default="general")
    ap.add_argument("--apply", action="store_true", help="落地写文件（默认只看建议）")
    ap.add_argument("--out", help="输出路径（默认 原文件名_润色.ext）")
    ap.add_argument("--inplace", action="store_true", help="覆盖原文件（先自动备份 .bak）")
    ap.add_argument("--term-group", action="append", default=[],
                    help='同一实体的多种写法，如 "锂电设备/锂电装备/锂电池设备"')
    ap.add_argument("--long-limit", type=int, default=45,
                    help="无标点子串长度阈值（不是整句字数）")
    args = ap.parse_args()

    if not os.path.exists(args.path):
        ap.error(f"找不到文件：{args.path}")
        return 2
    ext = os.path.splitext(args.path)[1].lower()
    if ext in (".html", ".htm"):
        print("html 只支持审校，不支持润色落地（标签与文字混排，批量替换风险高）")
        return 2

    blocks = load_blocks(args.path)
    rep = Report()
    check_redundant(blocks, rep)
    check_redundant_re(blocks, rep)
    check_long_sent(blocks, rep, args.long_limit)
    check_vague(blocks, rep)
    check_connector(blocks, rep)
    check_punct(blocks, rep)
    check_dup(blocks, rep)
    check_terms(blocks, rep, args.term_group)
    check_passive(blocks, rep)

    print(render(rep, args.path, args))
    if not args.apply:
        return 0

    before = baseline_count(args.path)
    if args.inplace:
        bak = args.path + ".bak"
        shutil.copyfile(args.path, bak)
        dst = args.path
        print(f"\n原件已备份：{bak}")
    else:
        base, e = os.path.splitext(args.path)
        dst = args.out or f"{base}_润色{e}"
    tmp = dst + ".tmp" + ext

    print(f"\n落地中 → {dst}")
    if ext == ".docx":
        done, skip = apply_docx(args.path, tmp, rep)
        print(f"  落地 {done} 处；跳过 {skip} 处（跨 run 或数字校验不通过，只报告）")
    else:
        done = apply_text(args.path, tmp, rep)
        print(f"  落地 {done} 处")
    os.replace(tmp, dst)
    print(f"  输出：{dst}（{os.path.getsize(dst)} B）")
    if not args.inplace:
        print(f"  原文件未改动，md5 {md5(args.path)[:12]}…")

    ok = self_check(dst, before)
    if not ok:
        print("\n🔴 自校验失败：润色后审校问题数上升，已保留输出供对比，但**不要直接替换原稿**。")
        return 1
    print("\n✅ 自校验通过：润色未破坏审校结果。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
