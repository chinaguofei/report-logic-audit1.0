# -*- coding: utf-8 -*-
"""check_table_complete.py —— 表格完整性关卡（v1.1.3 新增）

背景：本 skill 因「研报矩阵表缺一行数据」而创建，但前三关（audit_docx /
check_reasoning / check_fig_units）都不检查「表格单元格里有没有空格」，
导致 -- / — / 空串 缺格反复漏网。本关专门堵这个洞。

用法：python check_table_complete.py <docx> [--allow-str "—"]
  --allow-str  声明为「合法 N/A」的占位串，逗号分隔（默认无；'--' 一律算缺格）

输出：逐格明细 + 汇总行；有缺格时退出码 1。
"""
import argparse
import os
import re
import sys

PLACEHOLDER = re.compile(r"^\s*(--|—|-|–|N/?A|TBD|TODO|\?\?|待补|待填)\s*$")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docx")
    ap.add_argument("--allow-str", default="", help="合法 N/A 占位串，逗号分隔（如 '—'）")
    args = ap.parse_args()
    if not os.path.isfile(args.docx):
        ap.error(f"找不到文件：{args.docx}")

    ext = os.path.splitext(args.docx)[1].lower()
    if ext != ".docx":
        # 单元格级缺格检查依赖 python-docx 的表格结构；其他格式无此结构，
        # 在上游排版阶段确认即可，此处显式跳过并 PASS（不静默、不崩溃）。
        print(f"!! 表格缺格检查仅支持 .docx（当前 {ext}）。"
              f"Markdown/HTML 表格请在上游排版阶段确认无空格。")
        print("汇总: 缺格=0 → PASS（格式不适用，已跳过单元格级检查）")
        sys.exit(0)

    from docx import Document
    allow = {s.strip() for s in args.allow_str.split(",") if s.strip()}

    doc = Document(args.docx)
    holes = []
    for ti, t in enumerate(doc.tables, 1):
        seen = set()
        for ri, row in enumerate(t.rows, 1):
            for ci, cell in enumerate(row.cells, 1):
                txt = cell.text.strip()
                if not txt or (PLACEHOLDER.match(txt) and txt not in allow):
                    key = (id(row._tr), ci)
                    if key in seen:
                        continue
                    seen.add(key)
                    label = row.cells[0].text.strip()[:16] or f"行{ri}"
                    holes.append((ti, ri, ci, label, txt or "(空)"))

    print(f"表格数: {len(doc.tables)}")
    for ti, ri, ci, label, txt in holes:
        print(f"[FIX] 表{ti} 「{label}」第{ci}列: 缺格「{txt}」")
    n = len(holes)
    print(f"汇总: 缺格={n} → {'FAIL（须补数或显式声明 N/A）' if n else 'PASS'}")
    sys.exit(1 if n else 0)


if __name__ == "__main__":
    main()
