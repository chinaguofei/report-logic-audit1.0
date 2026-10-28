# -*- coding: utf-8 -*-
"""格式审校器（report-logic-audit 模式三：排版与文字规范，不碰论证）。

为什么单独成一个脚本：
审校管逻辑，润色管表达，格式是第三件事——字体字号行距标题层级，
这些在 Word 里是"样式"，在文字里是"字符"，跟论证好坏无关，
但交付定稿前同样要过一遍。混进润色会让润色的边界失守。

四组检查：
  1. 错别字与易混词（只报告，人工确认——机器改错别字必误伤）
  2. 全角/半角字符与中英文空格规范（只报告）
  3. 标题层级与样式（只报告：跳级、正文误用标题样式）
  4. 字体字号与行距（--fix 可自动统一，见下）

--fix 的硬边界：
  只统一**字体（中文字体）与行距**，落在"占多数的值"上；
  **文字一个字符都不动**——落地前后逐段比对，多一个字符就整份放弃；
  字号不自动改（正文字号差异常是强调，机器分不清强调与失误）；
  错别字、全角字符、标题层级永不自动改。

用法:
    # 看报告，不动文件（默认）
    python check_format.py 文章.docx
    python check_format.py 文章.md          # md/txt 只做文字层三组检查

    # 自动统一字体与行距（docx 专属）：写新文件，文字逐字校验不变
    python check_format.py 文章.docx --fix
    python check_format.py 文章.docx --fix --out 文章_格式.docx

支持 .docx（全项）/ .md / .txt（文字层）
退出码: 0 正常（格式问题不阻断交付，故无"阻断"档）；2 文件读不了/缺依赖
"""
import argparse
import os
import re
import sys

# ---------------------------------------------------------------- 错别字与易混词
# 只收"错字几乎不可能成立"的固定词对；语境才能定对错的（权力/权利、作/做、登陆/登录）不进这张表，
# 走下面的 CONTEXT_PATTERNS。
TYPOS = {
    "帐号": "账号", "帐户": "账户", "帐单": "账单", "帐目": "账目",
    "迫不急待": "迫不及待", "一如继往": "一如既往", "甘败下风": "甘拜下风",
    "世外桃园": "世外桃源", "名符其实": "名副其实", "装璜": "装潢",
    "等侯": "等候", "侯选": "候选", "消声匿迹": "销声匿迹",
    "出奇不意": "出其不意", "按步就班": "按部就班", "变本加利": "变本加厉",
    "恰如其份": "恰如其分", "相辅相承": "相辅相成", "好象": "好像",
    "精减": "精简", "增涨": "增长", "部份": "部分",
    "水蒸汽": "水蒸气", "言简意骇": "言简意赅", "山青水秀": "山清水秀",
    "纷至踏来": "纷至沓来", "名信片": "明信片", "国藉": "国籍",
    "题纲": "提纲", "布署": "部署", "按装": "安装",
    "报歉": "抱歉", "必竟": "毕竟", "既使": "即使",
}

# 语境类：只有命中上下文才算错，报告为"建议确认"
CONTEXT_PATTERNS = [
    (re.compile(r"登陆(?=(?:网站|页面|系统|平台|界面|密码|账号|帐号|成功|失败))"),
     "登陆→登录", "网络语境下应为「登录」"),
    (re.compile(r"截止(?=\s*\d{4}年|\s*\d{1,2}月|\s*\d{1,2}日)"),
     "截止→截至", "后接具体时间应为「截至」（「截止」用于「报名日期截止」这类句尾）"),
    (re.compile(r"其它"), "其它→其他", "现行规范用「其他」"),
]

FULLWIDTH_RE = re.compile(r"[０-９Ａ-Ｚａ-ｚ＃＄％＆＋？！]")
UNIT = r"(?:GB|MB|KB|TB|kg|km|cm|mm|ml|GW|MW|GWh|MWh|亿元)"
NUM = r"\d+(?:\.\d+)?"

# ---------------------------------------------------------------- 通用工具


def iter_lines(text):
    for i, line in enumerate(text.splitlines(), 1):
        if line.strip():
            yield i, line


def scan_text(text, src=""):
    """文字层三组检查（md/txt/docx 通用）。返回 findings 列表。"""
    out = []

    def add(tier, code, where, detail, fix):
        out.append((tier, code, where, detail, fix))

    # 1) 错别字
    for i, line in iter_lines(text):
        plain = src and f"{src} 第{i}行" or f"第{i}行"
        for w, r in TYPOS.items():
            for m in re.finditer(re.escape(w), line):
                s = max(0, m.start() - 10)
                add("须修", "F-TYPO", plain,
                    f"「{w}」应为「{r}」（…{line[s:m.end() + 10]}…）",
                    f"改为「{r}」")
        for pat, label, why in CONTEXT_PATTERNS:
            for m in pat.finditer(line):
                s = max(0, m.start() - 10)
                add("建议", "F-TYPO", plain,
                    f"{label}（…{line[s:m.end() + 10]}…）：{why}",
                    f"确认后改为「{label.split('→')[1]}」")

    # 2) 全角字符
    for i, line in iter_lines(text):
        plain = src and f"{src} 第{i}行" or f"第{i}行"
        hits = FULLWIDTH_RE.findall(line)
        if hits:
            shown = " ".join(sorted(set(hits))[:12])
            add("须修", "F-FULLWIDTH", plain,
                f"全角字符 {shown}（正文应为半角）",
                "改为半角；确需全角排版的除外")

    # 3) 中英文空格：只做"同一份文档内不一致"的判断，不绑架风格
    cjk = r"[\u4e00-\u9fff]"
    latin = r"[A-Za-z0-9]"
    spaced = len(re.findall(cjk + r" " + latin + "|" + latin + r" " + cjk, text))
    tight = len(re.findall(cjk + latin + "|" + latin + cjk, text))
    if spaced and tight and min(spaced, tight) >= 3 and min(spaced, tight) / max(spaced, tight, 1) < 0.35:
        add("建议", "F-PANGU", "全文",
            f"中英文之间加空格与不加两种写法混用（加 {spaced} 处 / 不加 {tight} 处）",
            "选定一种风格统一；推荐加空格（盘古之白）")
    elif not spaced and tight >= 10:
        add("建议", "F-PANGU", "全文",
            "全文中英文之间均未加空格",
            "可保持现状；若平台/期刊要求盘古之白再统一加")

    # 4) 数字与单位：同一单位两种写法并存才报
    with_u = set(re.findall(NUM + r" ?" + UNIT, text))
    styles = {}
    for m in with_u:
        u = re.search(UNIT, m).group(0)
        styles.setdefault(u, set()).add("带空格" if " " in m else "不空格")
    for u, st in styles.items():
        if len(st) > 1:
            add("建议", "F-UNIT", "全文",
                f"单位 {u} 前空格写法不一致（{' 与 '.join(sorted(st))}）",
                f"统一为其中一种（GB 系推荐「数字 {u}」）")
    return out


# ---------------------------------------------------------------- docx 专属

HEADING_RE = re.compile(r"^(?:Heading|标题)\s*(\d)", re.I)
MONO_FONTS = {"consolas", "courier", "menlo", "monaco", "simsun", ""}
# 等宽/代码字体不参与"字体混用"判断，避免把行内代码当错排


def load_docx(path):
    try:
        from docx import Document
    except ImportError:
        print("缺 python-docx，请先安装：pip install python-docx")
        print("或者：把文档另存为 .md / .txt —— 文字层检查不需要任何第三方包。")
        sys.exit(2)
    return Document(path)


def east_asia(run):
    """读 run 的中文字体（w:eastAsia），读不到返回 None。"""
    rpr = run._element.rPr
    if rpr is None or rpr.rFonts is None:
        return None
    return rpr.rFonts.get(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia")


def set_east_asia(run, font):
    rpr = run._element.rPr
    if rpr is None:
        rpr = run._element.get_or_add_rPr()
    if rpr.rFonts is None:
        rpr.get_or_add_rFonts()
    rpr.rFonts.set(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia", font)


def classify(doc):
    """把段落分成标题/正文两组。"""
    heads, body = [], []
    for p in doc.paragraphs:
        if not p.text.strip():
            continue
        m = HEADING_RE.match(p.style.name or "")
        (heads if m else body).append(p)
    return heads, body


def scan_docx(doc):
    out = []
    heads, body = classify(doc)

    def add(tier, code, where, detail, fix):
        out.append((tier, code, where, detail, fix))

    # 3) 标题层级
    seq = []
    for p in heads:
        m = HEADING_RE.match(p.style.name or "")
        seq.append((int(m.group(1)), p.text.strip()[:20]))
    prev = 0
    for lv, t in seq:
        if prev and lv > prev + 1:
            add("须修", "F-HEAD", f"标题「{t}」",
                f"标题跳级：上一级 H{prev}，这里直接 H{lv}",
                "插入中间层级或把本标题升一级")
        prev = lv
    for p in heads:
        if len(p.text.strip()) > 60:
            add("须修", "F-HEAD", f"标题「{p.text.strip()[:24]}…」",
                f"正文误用标题样式：{len(p.text.strip())} 字的长段落挂在标题样式上",
                "改为正文样式；确为摘要式大段标题则忽略")

    # 4) 字体
    for label, group in (("正文", body), ("标题", heads)):
        fonts = {}
        for p in group:
            for r in p.runs:
                if not r.text.strip():
                    continue
                f = east_asia(r)
                if f and f.lower() not in MONO_FONTS:
                    fonts.setdefault(f, 0)
                    fonts[f] += 1
        if len(fonts) > 1:
            maj = max(fonts, key=fonts.get)
            minor = {k: v for k, v in fonts.items() if k != maj}
            detail = "、".join(f"{k}×{v}" for k, v in sorted(minor.items(), key=lambda x: -x[1]))
            add("须修", "F-FONT", f"{label}中文字体",
                f"混用：多数「{maj}」之外还有 {detail}",
                f"统一为「{maj}」（--fix 可自动落地）")

    # 字号：只统计与提示，不自动改
    sizes = {}
    for p in body:
        for r in p.runs:
            if r.text.strip() and r.font.size:
                sizes.setdefault(r.font.size.pt, 0)
                sizes[r.font.size.pt] += 1
    if len(sizes) > 1:
        detail = "、".join(f"{k:g}pt×{v}" for k, v in sorted(sizes.items(), reverse=True))
        add("建议", "F-SIZE", "正文字号",
            f"多种字号并存：{detail}",
            "确认小字号是否为图表注/强调；非刻意强调的统一到主字号")

    # 行距
    spacing = {}
    for p in body:
        ls = p.paragraph_format.line_spacing
        if ls is not None:
            key = f"{ls:g}倍" if isinstance(ls, float) else str(ls)
            spacing.setdefault(key, [0, ls])
            spacing[key][0] += 1
    if len(spacing) > 1:
        detail = "、".join(f"{k}×{v[0]}" for k, v in spacing.items())
        add("建议", "F-SPACING", "正文行距",
            f"多种行距并存：{detail}",
            "统一为占多数的行距（--fix 可自动落地）")
    return out


def fix_docx(doc, src, dst):
    """只统一中文字体与行距（占多数的值），文字逐字校验不变。"""
    heads, body = classify(doc)
    changed = 0

    for group in (body, heads):
        fonts = {}
        for p in group:
            for r in p.runs:
                if r.text.strip():
                    f = east_asia(r)
                    if f and f.lower() not in MONO_FONTS:
                        fonts[f] = fonts.get(f, 0) + 1
        if len(fonts) > 1:
            maj = max(fonts, key=fonts.get)
            for p in group:
                for r in p.runs:
                    f = east_asia(r)
                    if f and f != maj and f.lower() not in MONO_FONTS:
                        set_east_asia(r, maj)
                        changed += 1

    spacing = {}
    for p in body:
        ls = p.paragraph_format.line_spacing
        if ls is not None:
            spacing[ls] = spacing.get(ls, 0) + 1
    if len(spacing) > 1:
        maj = max(spacing, key=spacing.get)
        for p in body:
            if p.paragraph_format.line_spacing is not None and p.paragraph_format.line_spacing != maj:
                p.paragraph_format.line_spacing = maj
                changed += 1

    before = [p.text for p in doc.paragraphs] + \
             [c.text for t in doc.tables for row in t.rows for c in row.cells]
    doc.save(dst)
    from docx import Document as D2
    after_doc = D2(dst)
    after = [p.text for p in after_doc.paragraphs] + \
            [c.text for t in after_doc.tables for row in t.rows for c in row.cells]
    if before != after:
        os.remove(dst)
        print("  ⚠ 文字逐字校验失败（字体修正不该动文字），已删除输出，放弃落地")
        return changed, False
    return changed, True


# ---------------------------------------------------------------- 主流程

def report(findings):
    tiers = [("须修", "🟡"), ("建议", "🔵")]
    shown = 0
    for tier, icon in tiers:
        rows = [f for f in findings if f[0] == tier]
        if not rows:
            continue
        print(f"\n{icon} {tier}（{len(rows)}）")
        for _, code, where, detail, fix in rows:
            shown += 1
            print(f"  {code}｜{where}")
            print(f"    {detail}")
            print(f"    → {fix}")
    if not shown:
        print("\n（未发现格式问题）")
    print(f"\n—— 须修 {sum(1 for f in findings if f[0]=='须修')}｜"
          f"建议 {sum(1 for f in findings if f[0]=='建议')}｜"
          f"格式问题不阻断交付，逐条人工判断即可")


def main():
    ap = argparse.ArgumentParser(description="格式审校（排版/字体/错别字/中英文规范）")
    ap.add_argument("path")
    ap.add_argument("--fix", action="store_true",
                    help="自动统一中文字体与行距（docx 专属；文字不动，逐字校验）")
    ap.add_argument("--out", help="输出路径（默认 原文件名_格式.docx）")
    args = ap.parse_args()
    if not os.path.exists(args.path):
        print(f"找不到文件：{args.path}")
        sys.exit(2)

    ext = os.path.splitext(args.path)[1].lower()
    findings = []

    if ext == ".docx":
        doc = load_docx(args.path)
        heads, body = classify(doc)
        n_chars = sum(len(p.text) for p in doc.paragraphs)
        print(f"格式审校：{args.path}")
        print(f"规模：{n_chars} 字｜标题段 {len(heads)}｜正文段 {len(body)}\n")

        text = "\n".join(p.text for p in doc.paragraphs)
        findings += scan_text(text)
        findings += scan_docx(doc)
        report(findings)

        if args.fix:
            dst = args.out or re.sub(r"\.docx$", "_格式.docx", args.path)
            print(f"\n统一中文字体/行距 → {dst}")
            n, ok = fix_docx(doc, args.path, dst)
            if ok:
                print(f"  落地 {n} 处；文字逐字校验通过（一个字符未动）")
                print(f"  输出：{dst}（{os.path.getsize(dst)} B）")
            else:
                sys.exit(1)
    else:
        with open(args.path, encoding="utf-8", errors="ignore") as f:
            text = f.read()
        print(f"格式审校（文字层）：{args.path}")
        print(f"规模：{len(text)} 字符\n")
        findings += scan_text(text)
        report(findings)
        if args.fix:
            print("\n--fix 仅支持 .docx（md/txt 没有字体与行距属性）")
    sys.exit(0)


if __name__ == "__main__":
    main()
