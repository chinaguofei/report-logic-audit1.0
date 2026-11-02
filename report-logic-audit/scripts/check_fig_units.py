# -*- coding: utf-8 -*-
"""
关卡五 · 图文口径一致性检查（单位/量纲/标签-数值对应）

背景（2026-10-27 海目星 688559 实战）：
    docx 审核脚本只读 **正文文字**；图里的标题、轴名、数据标签是 matplotlib
    画进 PNG 的像素，audit_docx.py 一个字都读不到 —— 11 张图的图内文字
    全部是审核盲区。订单图右轴写「同比增速（%）」，三根柱的标签却是
    「同比翻倍 / 同比 +1.5 倍 / +192.5%」，一个轴里两种单位，连续 5 轮
    BLOCK=0 都没拦住。

本脚本的做法：不读像素，读**图源脚本的配置常量**。
约定：每张图的数据标签、轴标题、注释都以模块级常量声明
（如 AMT / AMT_TXT / YOY / YOY_TXT / NOTE），脚本用 ast 解析这些常量，
即可对图内文字做确定性的机械校验。

检查项：
    FU1 同一指标组内单位混用（% 与 倍 并存）            BLOCK
    FU2 轴标题为 %，标签却用「倍/翻倍」                  BLOCK
    FU3 标签里的数字与对应数值列表不一致                  BLOCK
    FU4 轴标题缺单位                                     SUGGEST
    FU5 正文增速类词后跟「倍/翻倍」                       BLOCK
    FU6 同一句内「倍」与「%」并列指同一指标               SUGGEST

用法：
    python check_fig_units.py --figs ../data --docx 报告.docx
    python check_fig_units.py --figs ../data --docx 报告.docx --json out.json
"""
import argparse
import ast
import glob
import io
import json
import os
import re
import sys

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── 单位识别 ───────────────────────────────────────────────
UNIT_RULES = [
    ("PCT", re.compile(r"[%％]")),
    ("TIMES", re.compile(r"翻倍|翻了|[0-9.]+\s*倍")),
    ("CNY", re.compile(r"亿")),
    ("GWH", re.compile(r"GWh")),
    ("COUNT", re.compile(r"[万台条座个家]")),
]

# 允许出现「倍」的组：估值倍数是正当用法，不参与增速单位检查
VALUE_GROUPS = ("PE", "PB", "PS", "VAL", "MULT")

GROWTH_GROUP = re.compile(r"(YOY|YOY_|RATE|GROWTH|GROW|CAGR|REVYOY|NPYOY|同比|增速)", re.I)

GROW_WORDS = r"(同比|环比|增速|增长率|增幅|增长|CAGR)"
TIMES_WORDS = r"(翻倍|翻了[0-9一二三四五六七八九十.]+倍|[0-9]+(?:\.[0-9]+)?\s*倍)"


def units_in(text):
    out = set()
    for name, pat in UNIT_RULES:
        if pat.search(text):
            out.add(name)
    return out


def numbers_in(text):
    # 负号、正号、千分位一并处理
    return re.findall(r"[-+]?\d+(?:\.\d+)?", text.replace(",", ""))


# ── 解析图源脚本 ───────────────────────────────────────────
def load_fig_module(path):
    """返回 (assign: dict[str, obj], axis_labels: list[(func, text)], title: str|None)"""
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    assign = {}
    axis_labels = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            tgt = node.targets[0]
            if isinstance(tgt, ast.Name):
                try:
                    assign[tgt.id] = ast.literal_eval(node.value)
                except Exception:
                    pass
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            fn = ""
            if isinstance(call.func, ast.Attribute):
                fn = call.func.attr
            if fn in ("set_xlabel", "set_ylabel", "set_title", "suptitle", "text"):
                if call.args and isinstance(call.args[0], ast.Constant) \
                        and isinstance(call.args[0].value, str):
                    axis_labels.append((fn, call.args[0].value))
    return assign, axis_labels


def pair_groups(assign):
    """X 与 X_TXT（或 X_TEXT / X_LABEL）配对，返回 [(base, values, labels)]"""
    pairs = []
    for k, v in assign.items():
        base = re.sub(r"_(TXT|TEXT|LABEL|LABELS|STR)$", "", k)
        if base == k:
            continue
        for cand in (base, base + "_LABEL", base + "_LABELS"):
            if cand in assign:
                labels = v
                if isinstance(labels, str):
                    labels = [labels]
                if not isinstance(labels, list) or not all(isinstance(x, str) for x in labels):
                    continue
                vals = assign.get(cand)
                pairs.append((cand, vals, labels))
                break
    # 去重（同一 base 只保留一次）
    seen, out = set(), []
    for base, vals, labels in pairs:
        if base in seen:
            continue
        seen.add(base)
        out.append((base, vals, labels))
    return out


# ── 检查 ──────────────────────────────────────────────────
def check_figs(figs_dir):
    findings = []
    files = sorted(glob.glob(os.path.join(figs_dir, "draw_*.py")))
    files = [f for f in files if "_688559" in os.path.basename(f) or True]
    for f in files:
        name = os.path.basename(f)
        try:
            assign, axis_labels = load_fig_module(f)
        except SyntaxError as e:
            findings.append(dict(level="SUGGEST", code="FU0", file=name,
                                 msg="脚本语法解析失败，跳过：%s" % e))
            continue

        pairs = pair_groups(assign)
        if not pairs:
            continue

        # 轴标题单位
        pct_axes = [t for fn, t in axis_labels if units_in(t) == {"PCT"}]
        all_label_units = set()
        for base, vals, labels in pairs:
            for s in labels:
                all_label_units |= units_in(s)

        for base, vals, labels in pairs:
            is_value = any(g.upper() in base.upper() for g in VALUE_GROUPS)
            units = set()
            for s in labels:
                units |= units_in(s)

            # FU1 同组单位混用
            if "PCT" in units and "TIMES" in units:
                bad = [s for s in labels if "TIMES" in units_in(s)]
                findings.append(dict(
                    level="BLOCK", code="FU1", file=name, group=base,
                    msg="同一指标组 %s 内 %d 个标签混用「%%」与「倍」：%s"
                        % (base, len(labels), " / ".join(bad)),
                    fix="统一为 %%（=倍×100），增速不用「倍」表达"))

            # FU2 % 轴 vs 倍标签
            if "TIMES" in units and pct_axes and not is_value and GROWTH_GROUP.search(base):
                findings.append(dict(
                    level="BLOCK", code="FU2", file=name, group=base,
                    msg="轴标题为「%s」，但 %s 组标签用「倍」：%s"
                        % (pct_axes[0], base, " / ".join(labels)),
                    fix="标签改为百分数，与轴单位一致"))

            # FU3 标签数字 vs 数值
            if isinstance(vals, list) and len(vals) == len(labels) \
                    and all(isinstance(x, (int, float)) for x in vals):
                for v, s in zip(vals, labels):
                    nums = numbers_in(s)
                    if len(nums) != 1:
                        continue
                    try:
                        got = float(nums[0])
                    except ValueError:
                        continue
                    if "TIMES" in units_in(s):
                        got *= 100.0
                    want = float(v)
                    if abs(want) < 1e-9:
                        continue
                    if abs(got - want) / abs(want) > 0.02:
                        findings.append(dict(
                            level="BLOCK", code="FU3", file=name, group=base,
                            msg="标签「%s」里的数字 %.4g 与数值 %.4g 不一致（换算后）"
                                % (s, got, want),
                            fix="核对数据与标签，二者必须可互相换算"))

        # FU4 轴标题缺单位
        for fn, t in axis_labels:
            if fn not in ("set_xlabel", "set_ylabel"):
                continue
            if not units_in(t) and not re.search(r"[（(][^）)]{1,8}[）)]", t):
                findings.append(dict(
                    level="SUGGEST", code="FU4", file=name,
                    msg="轴标题「%s」未标注单位" % t,
                    fix="补单位，如「同比增速（%）」「金额（亿元）」"))

        # 该图是否声明了数据口径
        if not any(k in assign for k in ("NOTE", "SOURCE", "DATA_NOTE")):
            findings.append(dict(
                level="SUGGEST", code="FU4b", file=name,
                msg="图脚本未声明 NOTE/SOURCE 口径常量",
                fix="补口径与数据源，便于图注与审核对齐"))
    return findings


def check_docx(docx_path):
    findings = []
    if not docx_path or not os.path.exists(docx_path):
        return findings
    try:
        try:
            from docx import Document
        except ImportError:
            sys.exit("缺少 python-docx，读不了 .docx。\n"
                     "  安装：pip install python-docx")
    except ImportError:
        findings.append(dict(level="SUGGEST", code="FU0",
                             msg="未安装 python-docx，跳过正文单位检查"))
        return findings

    d = Document(docx_path)
    texts = [p.text for p in d.paragraphs]
    for t in d.tables:
        for r in t.rows:
            for c in r.cells:
                texts.append(c.text)
    texts = [t.strip() for t in texts if t and t.strip()]

    grow_then_times = re.compile(GROW_WORDS + r"[^。；;！？\n]{0,10}?" + TIMES_WORDS)
    times_and_pct = re.compile(TIMES_WORDS + r"[^。；;！？\n]{0,12}[%％]")

    for t in texts:
        for m in grow_then_times.finditer(t):
            findings.append(dict(
                level="BLOCK", code="FU5", scope="正文",
                msg="增速用「倍」表达：…%s…" % m.group(0),
                snippet=t[:110],
                fix="改为百分数（翻倍=+100%%，1.5 倍=+150%%）"))
        if times_and_pct.search(t):
            findings.append(dict(
                level="SUGGEST", code="FU6", scope="正文",
                msg="同一句内「倍」与「%%」并列，需确认是否指同一指标",
                snippet=t[:110],
                fix="同一指标统一单位；不同指标则各自标单位"))
    return findings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--figs", default=".", help="图源脚本目录（含 draw_*.py）")
    ap.add_argument("--docx", default=None, help="待检报告 docx")
    ap.add_argument("--json", default=None, help="输出 JSON 路径")
    args = ap.parse_args()

    findings = check_figs(args.figs) + check_docx(args.docx)
    blk = [x for x in findings if x["level"] == "BLOCK"]
    sug = [x for x in findings if x["level"] != "BLOCK"]

    print("=" * 68)
    print("关卡五 · 图文口径一致性（单位/量纲/标签-数值）")
    print("=" * 68)
    print("BLOCK=%d  SUGGEST=%d" % (len(blk), len(sug)))
    for tag, group in (("🔴 BLOCK", blk), ("🔵 SUGGEST", sug)):
        for x in group:
            print("\n%s [%s] %s" % (tag, x["code"], x.get("file") or x.get("scope", "")))
            print("   %s" % x["msg"])
            if x.get("snippet"):
                print("   原文：%s" % x["snippet"])
            if x.get("fix"):
                print("   改法：%s" % x["fix"])

    if args.json:
        json.dump(findings, open(args.json, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print("\nJSON -> %s" % args.json)

    sys.exit(1 if blk else 0)


if __name__ == "__main__":
    main()
