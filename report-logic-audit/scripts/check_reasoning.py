# -*- coding: utf-8 -*-
"""推理终结检查器（report-logic-audit 关卡五：推理有没有推到落点）。

"看起来有道理"和"推到了终点"是两件事。本脚本判的是后者：
每条结论性断言，是否给出 ①依据 ②机制 ③条件/边界 ④反例处理 ⑤可证伪判据。
已终结：五落点齐，或含「机制 + 可证伪判据」且至少 3 项（可证伪判据是真正的分水岭，
带判据的结论不再被压低）；半终结：≥2 项但缺可证伪判据；未终结：只有主张。

v1.1.2 增强：
- 主张识别扩到「我们认为/看好/警惕/将成为/是趋势」等观点研判写法；
- 「依据」改为节级数据感知（数据落表格/隔段不再漏判为无依据）；
- 新增 R1 相关当因果 / R3 中间环节缺失 / R10 归因单一 的可识别形态（SUGGEST）；
- 新增「推理厚度」指标（平均落点/5），快速看全文是否"只甩结论不论证"。

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
from common import findings, add, CN_NUM
from audit_docx import load_blocks, cn2int, _sections  # noqa: E402

CLAIM_MARKERS = ["因此", "所以", "说明", "表明", "可见", "意味着", "证明", "反映出",
                 "显示", "显然", "必然", "应当", "必须", "核心是", "关键在于",
                 "本质是", "结论是", "由此", "综上", "由此可见"]

# 观点/研判类主张（v1.1.2 新增识别）：研报/评论里大量用这类写法承载结论
VIEWS = ("我们认为", "笔者", "看好", "警惕", "值得关注", "需要重视", "需重视",
         "将成为", "是趋势", "预计将", "倾向于", "不难看出", "足以说明", "有理由认为")

# 落点五要素的识别词族
# 注意：「机制」只收"解释性"词（因为/由于/源于/通过/机制/传导…）。
# 因果断言动词（导致/带动/使得/从而…）不放这里——否则"X带动Y"这种断言本身就被当成
# 机制已满足，R3 永远报不出来。那些词交给 R3-MECH-MISS 单独识别。
SLOTS = {
    "依据": ("据", "来源", "年报", "公告", "数据", "统计", "样本", "测算", "调研", "报告"),
    "机制": ("因为", "由于", "源于", "通过", "机制", "传导", "取决于",
             "依赖", "驱动", "在于", "受.*影响", "受制于", "背后是", "本质上是",
             "根源", "推手", "关键在", "得益于", "受益于", "其原因是", "原因在于"),
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

def split_sents(blocks):
    """按章节切分并分句，返回 [{chap, sent, bi, sec}]（bi=块序号，sec=所属节序号）"""
    out, chap = [], "开头"
    secs = _sections(blocks)
    sec_of = {}
    for si, s in enumerate(secs):
        for bi in range(s["start"], s["end"]):
            sec_of[bi] = si
    for bi, (kind, text, style) in enumerate(blocks):
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
                out.append({"chap": chap, "sent": s, "bi": bi, "sec": sec_of.get(bi, -1)})
    return out


# 节级"数据供给"判定：该节是否含「数字 + 数据类词」的句子（避免表格数据隔段被漏判为无依据）
_SEC_DATA_WORDS = ("数据", "年报", "公告", "来源", "统计", "测算", "调研", "样本",
                   "案例", "显示", "据", "研报", "文献", "图表", "披露", "报告", "口径",
                   "同比", "环比", "增速", "增幅", "%", "亿元", "万元", "GWh", "万台", "倍")


def compute_sec_data(blocks, secs):
    res = {}
    for si, s in enumerate(secs):
        present = False
        for i in range(s["start"], s["end"]):
            kind, text, style = blocks[i]
            if kind != "p":
                continue
            if re.search(r"\d", text) and re.search("|".join(_SEC_DATA_WORDS), text):
                present = True
                break
        res[si] = present
    return res


def slots_hit(window, sec_has_data=False):
    """在上下文窗口中检查五要素命中（词表 + 正则两类判据）。

    「依据」额外接受节级数据供给：若整节含数字+数据词，则视为依据在场——
    数据常落在表格或隔段，强制只看前2后1句会把这类正常结论误判为无依据。
    """
    out = {}
    for k, words in SLOTS.items():
        hit = any(w in window for w in words)
        if not hit and k in SLOT_REGEX:
            hit = bool(re.search(SLOT_REGEX[k], window))
        if k == "依据" and not hit and sec_has_data:
            hit = True
        out[k] = hit
    return out


def grade(slots):
    n = sum(slots.values())
    has_mech = slots["机制"]
    has_cri = slots["判据"]
    # 已终结：五落点齐，或（含机制且含判据且至少 3 项）。可证伪判据是真正的分水岭——
    # 修复：旧版「n>=4 即已终结」会让「依据+机制+条件+反例（无判据）」被判定强于
    # 「依据+机制+判据」，与「可证伪性才是核心增量」自相矛盾；现改为带判据即更强。
    if n == 5 or (has_mech and has_cri and n >= 3):
        return "已终结"
    if n >= 2:
        return "半终结"
    return "未终结"


def find_window(sents, i, span=3):
    """断言所在段 + 前 2 + 后 1 句作为证据窗口（真实写作中依据常在前后句）"""
    lo, hi = max(0, i - span), min(len(sents), i + 2)
    return "。".join(s["sent"] for s in sents[lo:hi])


def check_claims(sents, sec_data, strict, top):
    claims = []
    for i, s in enumerate(sents):
        sent = s["sent"]
        if not (any(k in sent for k in CLAIM_MARKERS)
                or is_judgement(sent)
                or any(v in sent for v in VIEWS)):
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
        sec_has_data = sec_data.get(s["sec"], False)
        slots = slots_hit(win, sec_has_data)
        g = grade(slots)
        miss = [k for k, v in slots.items() if not v]
        has_claim_marker = any(k in sent for k in CLAIM_MARKERS) or any(v in sent for v in VIEWS)
        claims.append({"chap": s["chap"], "claim": sent[:120], "grade": g,
                       "missing": miss, "abs": any(w in sent for w in ABSOLUTE),
                       "slots_sum": sum(slots.values()),
                       "marker": next((k for k in CLAIM_MARKERS if k in sent), "判断句")})
        # —— 五落点缺口（原有逻辑）——
        if g == "未终结":
            # 机械判据只看"落点位置"，不足以阻断交付；默认提示，--strict 升为须修
            add("FIX" if strict else "SUGGEST", "RSN-OPEN", s["chap"],
                f"未终结断言：{sent[:40]}", f"缺 {'/'.join(miss)}（窗口内无对应依据/机制/条件/反例/判据）")
        if any(w in sent for w in ABSOLUTE) and "条件" in miss:
            add("FIX" if strict else "SUGGEST", "RSN-ABS-NOCOND", s["chap"],
                f"绝对化结论无条件限定：{sent[:40]}", "「必然/一定会」类结论必须给成立条件")
        # —— v1.1.2 新增：可识别的推理病灶（SUGGEST，需人确认）——
        # R3 中间环节缺失：断言了因果动词，但机制落点缺失
        if has_claim_marker and "机制" in miss and \
                any(w in sent for w in ("导致", "带动", "推动", "使得", "引发", "拉动", "驱动", "带来", "推升", "从而")):
            add("SUGGEST", "R3-MECH-MISS", s["chap"],
                f"直接断言因果但无传导机制：{sent[:40]}", "从 A 到 B 中间环节缺失（R3）；补传导链每一环、标注时滞与卡点")
        # R1 相关当因果：在共现/背景下直接下因果结论，且机制缺失
        if has_claim_marker and "机制" in miss and \
                any(w in sent for w in ("随着", "伴随", "背景下", "同期", "与此同时", "在此情况下")):
            add("SUGGEST", "R1-CORR-CAUSE", s["chap"],
                f"相关/共现当因果：{sent[:40]}", "同时发生≠它引起（R1）；给机制或排除共同原因（第三变量）")
        # R10 归因单一（β当α）：行业/整体向好 + 公司/个股受益，且无同业对照
        if has_claim_marker and \
                any(w in sent for w in ("行业", "板块", "整体", "大盘", "需求", "景气度", "产业")) and \
                any(w in sent for w in ("提升", "增长", "上行", "回暖", "向好", "高增", "改善")) and \
                any(w in sent for w in ("公司", "个股", "该企业", "该标的", "龙头", "公司层面", "其自身")) and \
                any(w in sent for w in ("受益", "驱动", "带动", "利好", "弹性", "抢占")):
            add("SUGGEST", "R10-ATTRIB", s["chap"],
                f"疑似将行业β当公司α：{sent[:40]}", "行业涨≠公司强（R10）；拆分 β 与 α、给同业对照基线")
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
    if not os.path.isfile(a.path):
        ap.error(f"找不到文件：{a.path}")


    blocks = load_blocks(a.path)
    if not blocks:
        print("未抽取到内容")
        return 2

    sents = split_sents(blocks)
    sec_data = compute_sec_data(blocks, _sections(blocks))
    claims, cnt = check_claims(sents, sec_data, a.strict, a.top)
    jumps = check_jumps(sents)
    check_circular(sents)

    order = {"BLOCK": 0, "FIX": 1, "SUGGEST": 2}
    findings.sort(key=lambda f: order.get(f["level"], 9))
    cc = {k: sum(1 for f in findings if f["level"] == k) for k in ("BLOCK", "FIX", "SUGGEST")}

    avg_slots = (sum(c["slots_sum"] for c in claims) / len(claims)) if claims else 0.0
    print(f"=== 推理终结检查 · {os.path.basename(a.path)} ===")
    print(f"分句 {len(sents)} 句 | 结论性断言 {len(claims)} 条 "
          f"（已终结 {cnt['已终结']} / 半终结 {cnt['半终结']} / 未终结 {cnt['未终结']}）")
    print(f"推理厚度：平均落点 {avg_slots:.1f}/5（越高越扎实；<2.5 多为「只甩结论不论证」）")

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
