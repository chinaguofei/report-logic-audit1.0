# -*- coding: utf-8 -*-
"""check_residue.py —— 跨报告模板残留关卡（v1.1.4 新增）

背景：迅捷兴（688655）报告复用了北芯生命（688712）的图脚本模板，
图 3 的数据区已改成 PCB，但左右子图标题/注释仍残留「IVUS」（北芯语境），
渲染出「标题与数据互相矛盾」的图，且此前三关全部漏过——
机械关只查 docx 文本，不查图脚本配置区与渲染产物的一致性。

本关扫 docx 全文（段落 + 表格 + 页眉页脚）中「上一份报告的标识词」，
并在 SKILL.md 流程层要求：克隆图脚本后、出图前，对脚本源文件跑同名检查。

用法：
  python check_residue.py <docx> --ban "北芯,688712,IVUS"
  --ban   逗号分隔的禁词列表（旧公司简称 / 旧代码 / 旧领域词 / 旧模板变量名）

输出：逐条命中明细 + 汇总行；有命中时退出码 1。
"""
import argparse
import os
import re
import sys


def load_texts(path):
    """返回 [(where, text)]，覆盖 .docx/.md/.txt/.html。
    与 audit_docx.load_blocks 同款多格式分发，保证残留禁词扫描不挑格式。"""
    ext = os.path.splitext(path)[1].lower()
    out = []
    if ext == ".docx":
        try:
            from docx import Document
        except ImportError:
            print("!! 缺少 python-docx，读不了 .docx；请 pip install python-docx，"
                  "或改用 .md/.txt/.html（这几种格式不需要第三方包）")
            sys.exit(2)
        d = Document(path)
        for p in d.paragraphs:
            if p.text.strip():
                out.append(("正文", p.text))
        for ti, t in enumerate(d.tables, 1):
            for r in t.rows:
                for c in r.cells:
                    if c.text.strip():
                        out.append((f"表{ti}", c.text))
        for si, sec in enumerate(d.sections, 1):
            for block, tag in ((sec.header, "页眉"), (sec.footer, "页脚")):
                for p in block.paragraphs:
                    if p.text.strip():
                        out.append((f"页{tag}{si}", p.text))
    elif ext in (".md", ".txt"):
        for i, line in enumerate(open(path, encoding="utf-8", errors="ignore"), 1):
            if line.strip():
                out.append((f"行{i}", line))
    elif ext in (".html", ".htm"):
        raw = open(path, encoding="utf-8", errors="ignore").read()
        raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
        for i, m in enumerate(re.finditer(
                r"(?is)<(h[1-6])[^>]*>(.*?)</\1>|<t[dr][^>]*>(.*?)</t[dr]>|"
                r"<p[^>]*>(.*?)</p>|<div[^>]*>(.*?)</div>", raw), 1):
            txt = re.sub(r"(?s)<[^>]+>", "", "".join(g for g in m.groups()[1:] if g))
            txt = re.sub(r"\s+", " ", txt).strip()
            if txt:
                out.append((f"区块{i}", txt))
    else:
        print(f"!! 不支持的格式：{ext}（支持 .docx/.md/.txt/.html）")
        sys.exit(2)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docx")
    ap.add_argument("--ban", required=True,
                    help="逗号分隔禁词（上一份报告的公司简称/代码/领域词等）")
    args = ap.parse_args()
    if not os.path.isfile(args.docx):
        ap.error(f"找不到文件：{args.docx}")

    bans = [w.strip() for w in args.ban.split(",") if w.strip()]
    if not bans:
        print("!! --ban 为空，无检查内容")
        sys.exit(2)

    hits = []
    for where, text in load_texts(args.docx):
        for w in bans:
            if w in text:
                hits.append((where, w, text.strip()[:60]))

    for where, w, snippet in hits:
        print(f"[FIX] 残留 {w!r} @ {where}: {snippet}")
    n = len(hits)
    print(f"汇总: 残留命中={n} 禁词数={len(bans)} → {'PASS' if n == 0 else 'FAIL'}")
    sys.exit(1 if n else 0)


if __name__ == "__main__":
    main()
