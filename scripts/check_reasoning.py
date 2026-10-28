# -*- coding: utf-8 -*-
"""推理终结检查器（report-logic-audit 关卡五：推理有没有推到落点）。

"看起来有道理"和"推到了终点"是两件事。本脚本判的是后者：
每条结论性断言，是否给出 ①依据 ②机制 ③条件/边界 ④反例处理 ⑤可证伪判据。
五项全有 = 已终结；有机制无条件 = 半终结；只有主张 = 未终结。

机器只能给出"落点缺哪几项"的定位，判断仍需人来做——
它省掉的是逐句翻找的时间，不是判断本身。

用法:
    python check_reasoning.py 文章.docx
    python check_reasoning.py 文章.md --strict     # 未终结也阻断
    python check_reasoning.py 文章.docx --top 30   # 显示前 30 条未终结

退出码: --strict 且有未终结 → 1；否则只有绝对化无落点 → 1；其余 0
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_docx import load_blocks, cn2int  # noqa: E402

CN_NUM = "一二三四五六七八九十"

CLAIM_MARKERS = ["因此", "所以", "说明", "表明", "可见", "意味着", "证明", "反映出",
                 "显示", "显然", "必然", "应当", "必须", "核心是", "关键在于",
                 "本质是", "结论是", "由此", "综上", "由此可见"]

# 落点五要素的识别词族
SLOTS = {
    "依据": ("据", "来源", "年报", "公告", "数据", "统计", "样本", "测算", "调研", "报告"),
    "机制": ("因为", "由于", "导致", "带动", "源于", "通过", "机制", "传导", "取决于",
             "依赖", "驱动", "使得", "从而"),
    "条件": ("若", "如果", "条件下", "除非", "仅当", "前提", "假设", "上限",
             "下限", "区间", "情景"),
    "反例": ("但", "然而", "不过", "反例", "例外", "另一方面", "风险", "不及预期",
             "反面", "局限", "未能"),
    "判据": ("验证", "观察", "跟踪", "指标", "届时", "窗口", "证伪", "观察点",
             "复核", "一致性检验"),
}

# 正则类判据（词表判不了的形态）
SLOT_REGEX = {
    "依据": r"\d+(?:\.\d+)?\s*(?:亿|万|%|倍|元|台|GWh|吨|家|个|人|年|季)",
    "判据": r"若[^。]{0,40}则|一旦[^。]{0,30}就|届时[^。]{0,40}(?:看|核|验证)",
}

ABSOLUTE = ("必然", "一定会", "毫无疑问", "毋庸置疑", "绝对", "百分之百", "必将")

# 无连接词的"判断句"（要点式文章大量用这种写法：SST 是…的核心设备 / 需求本质：…）
JUDGE_NOUNS = ("核心", "关键", "本质", "标志", "转折", "前提", "基础", "主线",
               "拐点", "瓶颈", "决定性", "分水岭", "里程碑")
JUDGE_VERBS = ("是", "为", "属于", "构成", "处于", "代表", "标志着", "意味着")


def is_judgement(sent):
    """判断句：①编号要点句「1. 赛道定性：…」②判断动词 + 判断名词"""
    if re.match(r"^(\d{1,2}[.、．]|[（(]\d{1,2}[)）])\s*\S{2,10}[：:]", sent) and len(sent) >= 15:
        return True
    if not any(v in sent for v in JUDGE_VERBS):
        return False
    if not any(n in sent for n in JUDGE_NOUNS):
        return False
    return len(sent) >= 15

findings = []


def add(level, code, pos, msg, detail=""):
    findings.append({"level": level, "code": code, "pos": pos, "msg": msg, "detail": detail})


def split_sents(blocks):
    """按章节切分并分句，返回 [{chap, idx, sent}]"""
    out, chap = [], "开头"
    for kind, text, style in blocks:
        if kind != "p":
            continue
        m = re.match(r"^(?:#{1,6}\s*)?([%s]+)、\s*(.+)$" % CN_NUM, text)
        if m and len(m.group(1)) <= 2:
            chap = re.sub(r"^#{1,6}\s*", "", text)[:40]
            continue
        if re.match(r"^(图|表)\s?\d+[：:]", text.strip()):
            continue
        for s in re.split(r"[。！？；\n]", text):
            s = s.strip()
            if 10 <= len(s) <= 300:
                out.append({"chap": chap, "sent": s})
    return out


def slots_hit(window):
    """在上下文窗口中检查五要素命中（词表 + 正则两类判据）"""
    out = {}
    for k, words in SLOTS.items():
        hit = any(w in window for w in words)
        if not hit and k in SLOT_REGEX:
            hit = bool(re.search(SLOT_REGEX[k], window))
        out[k] = hit
    return out


def grade(slots):
    n = sum(slots.values())
    if n >= 4:
        return "已终结"
    if n >= 2:
        return "半终结"
    return "未终结"


def find_window(sents, i, span=3):
    """断言所在段 + 前 2 + 后 1 句作为证据窗口（真实写作中依据常在前后句）"""
    lo, hi = max(0, i - span), min(len(sents), i + 2)
    return "。".join(s["sent"] for s in sents[lo:hi])


def check_claims(sents, strict, top):
    claims = []
    for i, s in enumerate(sents):
        sent = s["sent"]
        if not any(k in sent for k in CLAIM_MARKERS) and not is_judgement(sent):
            continue
        # 排除纯方法/结构/定义说明句（不是主张）
        if re.search(r"^(本报告|本篇|以下|下面|上图|下表|图中|表中)", sent):
            continue
        if "＝" in sent or "=" in sent or "是指" in sent:
            continue
        # 证据句不是主张：「数据显示/据…/根据…」引的是证据本身
        if re.match(r"^(数据显示|据统计|根据|按照|据[^，,]{0,12}(报告|公告|统计|年报|调研))", sent):
            continue
        win = find_window(sents, i)
        slots = slots_hit(win)
        g = grade(slots)
        miss = [k for k, v in slots.items() if not v]
        claims.append({"chap": s["chap"], "claim": sent[:120], "grade": g,
                       "missing": miss, "abs": any(w in sent for w in ABSOLUTE),
                       "marker": next((k for k in CLAIM_MARKERS if k in sent), "判断句")})
        if g == "未终结":
            # 机械判据只看"落点位置"，不足以阻断交付；默认提示，--strict 升为须修
            add("FIX" if strict else "SUGGEST", "RSN-OPEN", s["chap"],
                f"未终结断言：{sent[:40]}", f"缺 {'/'.join(miss)}（窗口内无对应依据/机制/条件/反例/判据）")
        if any(w in sent for w in ABSOLUTE) and "条件" in miss:
            add("FIX" if strict else "SUGGEST", "RSN-ABS-NOCOND", s["chap"],
                f"绝对化结论无条件限定：{sent[:40]}", "「必然/一定会」类结论必须给成立条件")
    cnt = {k: sum(1 for c in claims if c["grade"] == k) for k in ("已终结", "半终结", "未终结")}
    if claims:
        density = len(claims) * 1000.0 / max(1, sum(len(s["sent"]) for s in sents))
        if density > 12:
            add("SUGGEST", "RSN-DENSE", "全文",
                f"结论句 {len(claims)} 条，密度 {density:.1f}/千字", "主张密度过高，主线不清")
    return claims, cnt


def check_jumps(sents):
    """推理跳跃待核表：把「前提 → 结论」成对列出，供人逐一核这一跳是否有机制"""
    LINK = ("因此", "所以", "由此", "可见", "故而", "从而", "于是")
    pairs = []
    for i, s in enumerate(sents):
        if not any(w in s["sent"] for w in LINK):
            continue
        if i == 0:
            continue
        prem = sents[i - 1]["sent"]
        if len(prem) < 10:
            continue
        pairs.append({"chap": s["chap"], "premise": prem[:100], "conclusion": s["sent"][:100]})
    if len(pairs) > 40:
        add("SUGGEST", "RSN-JUMP-MANY", "全文", f"因果/推论连接 {len(pairs)} 处",
            "逐跳核机制成本高；优先核涉及结论与量级的跳")
    return pairs


def check_circular(sents):
    """循环论证粗筛：结论句的实词大多在上一句已出现，且无新增数字/主体"""
    def words(t):
        return set(re.findall(r"[\u4e00-\u9fa5]{2,}", t))
    for i in range(1, len(sents)):
        cur, prev = sents[i]["sent"], sents[i - 1]["sent"]
        if not any(k in cur for k in ("因此", "所以", "可见", "说明", "证明")):
            continue
        wc, wp = words(cur), words(prev)
        if not wc:
            continue
        ov = len(wc & wp) / len(wc)
        if ov > 0.8 and not re.search(r"\d", cur):
            add("SUGGEST", "RSN-CIRCULAR", sents[i]["chap"],
                f"疑似循环论证：{cur[:40]}", "结论与前提用词几乎重合，需确认是否只是换了说法")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--strict", action="store_true", help="未终结断言按阻断处理")
    ap.add_argument("--top", type=int, default=20)
    a = ap.parse_args()

    blocks = load_blocks(a.path)
    if not blocks:
        print("未抽取到内容")
        return 2

    sents = split_sents(blocks)
    claims, cnt = check_claims(sents, a.strict, a.top)
    jumps = check_jumps(sents)
    check_circular(sents)

    order = {"BLOCK": 0, "FIX": 1, "SUGGEST": 2}
    findings.sort(key=lambda f: order.get(f["level"], 9))
    cc = {k: sum(1 for f in findings if f["level"] == k) for k in ("BLOCK", "FIX", "SUGGEST")}

    print(f"=== 推理终结检查 · {os.path.basename(a.path)} ===")
    print(f"分句 {len(sents)} 句 | 结论性断言 {len(claims)} 条 "
          f"（已终结 {cnt['已终结']} / 半终结 {cnt['半终结']} / 未终结 {cnt['未终结']}）")

    open_claims = [c for c in claims if c["grade"] != "已终结"]
    if open_claims:
        print(f"\n--- 待收口的断言（前 {min(a.top, len(open_claims))} 条）---")
        for n, c in enumerate(open_claims[:a.top], 1):
            print(f"{n}. [{c['grade']}][{c['chap'][:14]}] {c['claim']}")
            print(f"   缺：{'/'.join(c['missing'])}")
    else:
        print("所有结论性断言均有落点（建议人工抽 3 条复核）")

    if jumps:
        print(f"\n--- 推理跳跃待核（前 {min(8, len(jumps))} 对，核「这一跳有没有机制」）---")
        for n, j in enumerate(jumps[:8], 1):
            print(f"{n}. [{j['chap'][:14]}] 前提：{j['premise']}")
            print(f"   结论：{j['conclusion']}")

    print("\n--- 发现 ---")
    for f in findings:
        print(f"[{f['level']}] {f['code']} @ {f['pos'][:16]} :: {f['msg']} — {f['detail']}")
    if not findings:
        print("未发现机械可判的推理缺口（注意：机制是否成立仍需人读）")
    print(f"\n汇总: BLOCK={cc['BLOCK']} FIX={cc['FIX']} SUGGEST={cc['SUGGEST']}")

    out = os.path.splitext(a.path)[0] + "_reasoning.json"
    json.dump({"file": a.path, "claims": claims, "counts": cnt,
               "jumps": jumps[:40], "findings": findings},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"明细已存: {out}")
    return 1 if cc["BLOCK"] else 0


if __name__ == "__main__":
    sys.exit(main())
