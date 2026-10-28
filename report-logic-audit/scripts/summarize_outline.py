# -*- coding: utf-8 -*-
"""论证骨架抽取器 —— report-logic-audit 的「先复述、再挑刺」工具。

为什么要它：审校最容易犯的错是"局部挑刺"——盯着某句没证据，
却没看出这一句根本不在主线论证上。判据是：**能不能把全文还原成一条链**。
搭不出骨架，就是没读懂；此时报出的问题，多半是文字洁癖而非逻辑问题。

反向也成立：每条审核发现都必须能挂到骨架的某个节点或某条边上。
挂不上的，先怀疑是误报。这是本脚本对"去噪"的最大贡献。

同时也是结项交付（逻辑总结）的底稿：脚本给出客观骨架，
五问的答案（中心论点/分论点/验证路径/承重点/最弱一环）由模型填。

用法:
    python summarize_outline.py 文章.docx
    python summarize_outline.py 报告.docx --md 骨架.md
    python summarize_outline.py 文章.md --genre essay --top 6

支持 .docx / .md / .txt / .html
退出码: 恒为 0（这是描述性工具，不下判决）
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_docx import load_blocks, cn2int  # noqa: E402
from check_reasoning import CLAIM_MARKERS, is_judgement  # noqa: E402

CN_NUM = "一二三四五六七八九十"

# 标题特征词 → 论证路径
PATH_SIGNALS = [
    ("问题—方案", (("问题", "痛点", "现状", "困境", "挑战"), ("方案", "对策", "路径", "建议", "怎么办", "解法"))),
    ("驳论（先破后立）", (("误区", "反驳", "质疑", "不是", "并非", "真相", "谣言"), ())),
    ("因果链（A→B）", (("驱动", "传导", "带动", "影响", "因为", "导致", "如何", "机制"), ())),
    ("递进（时间/层级推进）", (("第一步", "第二步", "短期", "中期", "长期", "过去", "现在", "未来",
                             "初级", "进阶", "底层", "上层", "上篇", "下篇"), ())),
    ("总—分（并列展开）", (("一、", "二、", "综述", "概览", "全景"), ())),
]

# 需要"多组关键词同时命中"才算数的路径（顺序即读者的接受顺序）
CHAIN_SIGNALS = [
    ("自上而下（标的→行业→可比→估值）",
     (("概况", "基本面", "公司"), ("景气", "行业"), ("对标", "可比", "同业"), ("估值", "技术分析"))),
]


def detect_path(chaps):
    """从章标题特征词猜论证路径，给出可反驳的理由"""
    titles = " ".join(c["title"] for c in chaps if c["num"])
    for name, groups in CHAIN_SIGNALS:
        hits = [[w for w in g if w in titles] for g in groups]
        if all(hits):
            return name, "标题依次出现『%s』——读者被要求按此顺序接受结论" % "/".join(h[0] for h in hits)
    for name, (need, also) in PATH_SIGNALS:
        hit = [w for w in need if w in titles]
        if name.startswith("问题—方案"):
            hit2 = [w for w in also if w in titles]
            if hit and hit2:
                return name, f"标题同时出现『{hit[0]}』与『{hit2[0]}』"
        elif hit:
            return name, f"标题出现『{'/'.join(hit[:2])}』"
    return "并列（弱信号）", "章标题无明确推进/转折词，按并列处理——若实际是递进，需在导语写清「本章回答什么」"

# 结论类章名（用于判断"结论先行"还是"结论后置"）
CONCL_WORDS = ("结论", "总结", "小结", "结语", "收尾", "展望", "下一步")
FRONT_WORDS = ("核心结论", "摘要", "一页版", "执行摘要", "要点", "速览", "观点")


def split_chapters(blocks):
    """切章：中文「一、」或 markdown「# 」；无章节则全文算一章"""
    marks = []
    md_seq = 0          # markdown 用出现顺序编号——用 # 的层数当章号会撞车（两个「1」）
    for i, (kind, text, style) in enumerate(blocks):
        if kind != "p":
            continue
        t = text.strip()
        # 先认「一、」式明编号（允许 markdown 井号前缀）；认不出才退回按 # 层级编号
        m = re.match(r"^(?:#{1,6}\s*)?([%s]{1,2})、\s*(.{2,60})$" % CN_NUM, t)
        if m:
            marks.append((i, m.group(2).strip(), cn2int(m.group(1))))
            continue
        m = re.match(r"^(#{1,3})\s+(.{2,60})$", t)
        if m:
            if len(m.group(1)) == 1 and not marks:
                continue        # 首个 H1 是文章标题，不是章
            md_seq += 1
            marks.append((i, m.group(2).strip(), md_seq))

    if not marks:
        stats = _block_stats(blocks, 0, len(blocks))
        return [{
            "title": "（全文，无章节标记）", "num": 1,
            "start": 0, "end": len(blocks), **stats,
        }]

    chaps = []
    for k, (idx, title, num) in enumerate(marks):
        end = marks[k + 1][0] if k + 1 < len(marks) else len(blocks)
        # 章内内容从标题下一块开始
        stats = _block_stats(blocks, idx + 1, end)
        chaps.append({"title": title, "num": num, "start": idx, "end": end, **stats})
    # 首个标题之前的内容（导语/摘要）
    if marks[0][0] > 0:
        lead = _block_stats(blocks, 0, marks[0][0])
        if lead["chars"] >= 40:
            chaps.insert(0, {"title": "（导语 / 摘要，标题之前）", "num": 0,
                             "start": 0, "end": marks[0][0], **lead})
    return chaps


def _block_stats(blocks, a, b):
    chars, figs, tabs, asserts = 0, 0, 0, 0
    sents, first, last = [], "", ""
    for kind, text, style in blocks[a:b]:
        if kind == "table":
            tabs += 1
            # 表头也计入信息量，但不计字数（避免表头虚增篇幅）
            continue
        t = text.strip()
        if not t:
            continue
        if re.match(r"^图\s?\d+[：:]", t) or style.lower().startswith("caption"):
            figs += 1
            continue
        if re.match(r"^表\s?\d+[：:]", t):
            continue
        chars += len(t)
        if not first and len(t) >= 10:
            first = t[:60]
        if len(t) >= 10:
            last = t[-60:]
        for s in re.split(r"[。！？；\n]", t):
            s = s.strip()
            if 10 <= len(s) <= 300:
                sents.append(s)
                if any(k in s for k in CLAIM_MARKERS) or is_judgement(s):
                    asserts += 1
    return {"chars": chars, "figs": figs, "tables": tabs, "asserts": asserts,
            "first": first, "last": last, "nsent": len(sents)}


def concl_position(chaps):
    """结论先行 / 后置 / 无独立结论章。

    注意两点坑：①导语伪章（num=0）标题含「摘要」，不能算"结论先行章"；
    ②研报末章是风险提示，结论常在倒二章，故末两章都要看。
    """
    real = [c for c in chaps if c["num"]]
    body = real[:-2] if len(real) > 2 else []
    have_front = any(any(w in c["title"] for w in FRONT_WORDS) for c in body)
    tail = " ".join(c["title"] for c in real[-2:]) if real else ""
    have_last = any(w in tail for w in CONCL_WORDS)
    if have_front and have_last:
        return "先说后结（双落点）", "开头有摘要章、末章为结论——两处结论必须同一件事、同一口径"
    if have_front:
        return "结论先行", "只有开头摘要，末章不是结论——公文/方案的正确形态"
    if have_last:
        return "结论后置", "末章才是结论——研报/论文/评论的正确形态"
    return "无独立结论章", "全文没有可识别的结论章：结论散落在各章末尾，读者难以确认主张"


def fmt_pct(a, b):
    return f"{a / b * 100:.1f}%" if b else "—"


def render(path, blocks, chaps, args):
    total = sum(c["chars"] for c in chaps)
    nfig = sum(c["figs"] for c in chaps)
    ntab = sum(c["tables"] for c in chaps)
    nass = sum(c["asserts"] for c in chaps)
    pname, preason = detect_path(chaps)
    cpos, creason = concl_position(chaps)

    L = []
    L.append(f"# 论证骨架 · {os.path.basename(path)}")
    L.append("")
    nchap = len([c for c in chaps if c["num"]]) or len(chaps)
    L.append(f"体裁：{args.genre}｜正文 {total} 字｜章 {nchap}｜图 {nfig}｜表 {ntab}"
             f"｜断言 {nass}｜约 {max(1, round(total / 450))} 分钟读完")
    L.append("")
    L.append("## 一、结构骨架")
    L.append("")
    L.append("| 章 | 标题 | 字数 | 占比 | 图表 | 断言 | 断言/千字 |")
    L.append("|---|---|---|---|---|---|---|")
    for c in chaps:
        dens = c["asserts"] / c["chars"] * 1000 if c["chars"] else 0
        L.append(f"| {c['num'] or '—'} | {c['title'][:28]} | {c['chars']} | "
                 f"{fmt_pct(c['chars'], total)} | {c['figs']}/{c['tables']} | {c['asserts']} | {dens:.1f} |")
    # 编号连续性（骨架里就该看出撞号/跳号，不必等审校脚本）
    nums = sorted({c["num"] for c in chaps if c["num"]})
    gaps = [n for n in range(1, (max(nums) if nums else 0) + 1) if n not in nums]
    dup = len([c for c in chaps if c["num"]]) - len(nums)
    if gaps or dup:
        L.append("")
        L.append("**编号异常**：" + "、".join(
            ([f"缺第 {g} 章" for g in gaps] if gaps else []) +
            ([f"有 {dup} 处重号"] if dup else [])) +
            " —— 批量改稿「假成功」最常见症状，先修编号再谈内容")
    L.append("")
    L.append(f"**论证路径（脚本猜测）**：{pname} — {preason}")
    L.append("")
    L.append(f"**结论位置**：{cpos} — {creason}")
    L.append("")

    # 篇幅体检
    L.append("## 二、篇幅体检")
    L.append("")
    flags = []
    for c in chaps:
        share = c["chars"] / total * 100 if total else 0
        dens = c["asserts"] / c["chars"] * 1000 if c["chars"] else 0
        if c["num"] == 0:
            continue
        if share < 3 and c["chars"] > 0:
            flags.append(f"- 「{c['title'][:24]}」仅 {share:.1f}%（{c['chars']} 字）——"
                         f"若标题承诺了独立议题，此处是空壳章；要么补，要么并章")
        if share > 40:
            flags.append(f"- 「{c['title'][:24]}」占 {share:.1f}%——一章吞掉四成篇幅，读者会在中途失去结构感")
        if dens >= 8 and share <= 12:
            flags.append(f"- 「{c['title'][:24]}」断言密度 {dens:.1f}/千字、篇幅仅 {share:.1f}%——"
                         f"**结论倾倒区**：判断堆在最短的章里，通常没有论证过程，只有宣言")
        if c["chars"] >= 400 and c["asserts"] == 0:
            flags.append(f"- 「{c['title'][:24]}」{c['chars']} 字、0 条断言——资料汇编段，未形成主张")
    L += flags or ["- 未发现明显篇幅失衡"]
    L.append("")

    # 承重章
    L.append("## 三、承重结构（哪一章倒了全文就倒）")
    L.append("")
    ranked = sorted([c for c in chaps if c["chars"] > 80], key=lambda c: -c["asserts"])
    for ri, c in enumerate(ranked[:args.top], 1):
        L.append(f"{ri}. **{c['title'][:30]}** — 断言 {c['asserts']} 条、"
                 f"{c['chars']} 字（占 {fmt_pct(c['chars'], total)}）")
        if c["first"]:
            L.append(f"   - 起：「{c['first']}」")
        if c["last"]:
            L.append(f"   - 收：「{c['last']}」")
    L.append("")
    L.append("> 审校纪律：每条发现都要能挂到上面某一章、或章与章之间那条边上。"
             "挂不上的，先怀疑是误报。")
    L.append("")

    # 模板
    L.append("## 四、逻辑总结五问（需填，脚本不代答）")
    L.append("")
    L.append("1. **一句话主张**：作者最想让读者相信的那一件事是____（若填不出，说明全文没有主张，只有话题）")
    L.append("2. **分论点与证据**：支撑它的 ____ 条分论点，各自证据等级是 ____（数据／案例／引用／推理）")
    L.append("3. **验证路径**：读者照什么顺序被说服（____ → ____ → ____），中间有没有需要读者自己补的一跳")
    L.append("4. **承重点**：哪一环倒了全文就倒（见上节），这一环的证据是否比其余环节更硬")
    L.append("5. **三句话版**：如果只能留三句，是哪三句；留下的三句能否独立成理")
    L.append("")
    L.append("## 五、复述自检")
    L.append("")
    L.append("- [ ] 我能不看原文，把这个论证讲给第三个人听，且他不会问「那凭什么」")
    L.append("- [ ] 我复述出的主张，与文中原话是同一件事、同一强度（没有偷偷加强或减弱）")
    L.append("- [ ] 我知道作者**没有**主张什么（边界清楚，才说明读懂了）")
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="论证骨架抽取（逻辑总结底稿）")
    ap.add_argument("path", help=".docx / .md / .txt / .html")
    ap.add_argument("--genre", default="general", help="体裁（仅用于抬头）")
    ap.add_argument("--top", type=int, default=5, help="承重章显示条数")
    ap.add_argument("--md", help="另存 markdown 骨架到指定路径")
    args = ap.parse_args()

    if not os.path.exists(args.path):
        print(f"找不到文件：{args.path}")
        return 2
    blocks = load_blocks(args.path)
    if not blocks:
        print("没读到任何文本块（可能是扫描件或图片型 PDF，需先 OCR）")
        return 2
    chaps = split_chapters(blocks)
    out = render(args.path, blocks, chaps, args)
    print(out)
    if args.md:
        with open(args.md, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"\n已保存：{args.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
