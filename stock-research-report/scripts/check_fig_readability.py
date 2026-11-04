# -*- coding: utf-8 -*-
"""图表可读性门禁（第五关 · 交付前强制）

判据：图片被缩放进 A4 版心（16.0cm / 453.5pt 宽）后，
      最小文字的【实际物理字号】是否仍可读，以及脚注单行是否溢出画布。
      只查「有数据 / 有图 / 结构」不查「能不能读」，是 2026-11-04 事故根因。

用法：
    python check_fig_readability.py <图脚本目录> [匹配模式]
    python check_fig_readability.py data                 # 扫描 data/draw_*.py
    python check_fig_readability.py data "draw_*_688235.py"

退出码：0 = 无 FAIL（允许 WARN）；1 = 存在 FAIL（禁止交付）
WARN 只记录结构性风险（双 y 轴 / 45° 标签 / 多线叠加 / 密集图例），
需人工确认属设计需要，不计入阻断。
"""
import os
import re
import glob
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# 版心宽 = page_width 11906 twips − 左右各 1417 twips = 9072 twips = 16.0 cm = 453.5 pt
# （对应 insert_img.py 里 clamp 后的实际插图宽度；若改页边距需同步改此常量）
USABLE_PT = 453.5
FOOTNOTE_MIN_PT = 6.0      # 印刷可读下限
LABEL_MIN_PT = 7.0         # 轴标签可读下限
EPS = 1e-6                 # 浮点容差，避免 10 × 0.700 = 6.999... 误判


def _call_blocks(src, call):
    """按括号计数截取每个 call(...) 调用体（v1.2.2 审计修复）。

    旧实现用非贪婪正则 fig\\.text\\((?:.|\\n)*?\\)，遇 bbox=dict(...) 等
    嵌套圆括号会在首个 ')' 截断，导致脚注宽度高估、fontsize 归属错位。
    """
    blocks, i, n = [], 0, len(src)
    while True:
        j = src.find(call, i)
        if j < 0:
            break
        k = src.find("(", j)
        if k < 0:
            break
        depth, m = 1, k + 1
        while m < n and depth > 0:
            if src[m] == "(":
                depth += 1
            elif src[m] == ")":
                depth -= 1
            m += 1
        blocks.append(src[k + 1:m - 1])
        i = m
    return blocks


def scan(path):
    src = open(path, encoding="utf-8").read()

    # 画布宽度 → 缩放进版心的比例（与 savefig dpi 无关，只由 figsize 决定）
    # 同时兼容 plt.subplots(figsize=...) 与 plt.figure(figsize=...)
    m = re.search(r"figsize=\(\s*([\d.]+)\s*,\s*([\d.]+)\s*\)", src)
    fig_w_pt = float(m.group(1)) * 72 if m else 792.0
    scale = USABLE_PT / fig_w_pt

    # 字号常量（如 FS = 10.5），供 fontsize=FS 这类写法解析
    # v1.2.2：扩到大写+小写模块级常量（如 fs = 9.5），并收集 def 默认参数与调用点实参
    # （如 def box(fs=10) 但调用 box(..., fs=9.5)）。同一变量名多处取值时取【最小】——
    # 门禁是下限检查，必须保守；实测案例：draw_chain 盒标签 fs=9.5 → 进版心 6.65pt < 7.0pt，
    # 旧版解析不出 fontsize=fs 直接跳过，漏检（2026-11-04 审计实锤）。
    _cand = {}
    for k, v in re.findall(r"(?<![=!<>])\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(-?[\d.]+)\s*(?![\d.(=])", src):
        _cand.setdefault(k, []).append(float(v))
    consts = {k: min(vs) for k, vs in _cand.items()}

    def fsval(tok):
        tok = tok.strip()
        if re.fullmatch(r"[\d.]+", tok):
            return float(tok)
        return consts.get(tok)

    FS_RE = r"fontsize=\s*([A-Za-z_][A-Za-z_0-9]*|[\d.]+)"

    # fig.text 调用体（括号计数，防嵌套括号截断）
    blocks = _call_blocks(src, "fig.text")

    # fig.text 脚注字号（取每个 fig.text 调用的第一个 fontsize）
    foot = []
    for b in blocks:
        _m = re.search(FS_RE, b)
        if _m:
            v = fsval(_m.group(1))
            if v is not None:
                foot.append(v)
    eff_foot = [f * scale for f in foot]

    # 全部 fontsize 最小值（含轴标签）
    all_fs = [v for v in (fsval(x) for x in re.findall(FS_RE, src)) if v is not None]
    eff_min = min(all_fs) * scale if all_fs else None

    # 脚注单行是否溢出：fig.text 不自动换行，超出画布即被裁切。
    # 按「单个 fig.text 调用」分别估算后取最大，不跨调用累加（顶部标题各自独立）。
    note_m = re.search(r"^NOTE\s*=\s*[\"'](.+?)[\"']\s*$", src, re.M)
    note_len = len(note_m.group(1)) if note_m else 0
    # v1.2.2：blocks 已由括号计数得到（见 _call_blocks），不再用会截断嵌套括号的正则
    CJK = re.compile(r"[\u4e00-\u9fff]")
    per_call = []
    for b in blocks:
        # v1.2.2：先整体抹掉 f-string 花括号表达式再提字符串字面量——
        # 否则 {'、'.join(...)} 的内层引号会被当成正文拼接，脚注宽度虚高误报（draw_scorecard 实测 92 字符）
        b = re.sub(r"\{[^{}]*\}", "X", b, flags=re.S)
        lits = re.findall(r"[\"']([^\"']*)[\"']", b)
        # 相邻字符串字面量会拼成同一行；显式 \n 才换行，按最长行估宽度
        joined = "".join(re.sub(r"\{[^}]*\}", "X", x) for x in lits
                         if CJK.search(x) or re.search(r"\s", x))
        longest = max((len(seg) for seg in re.split(r"\\n|\n", joined)), default=0)
        per_call.append(longest + (note_len if re.search(r"\bNOTE\b", b) else 0))
    txt_len = max(per_call) if per_call else 0
    foot_pt = min(eff_foot) if eff_foot else (eff_min or 8.0)
    est_width = txt_len * foot_pt * 0.95
    overflow = est_width > USABLE_PT * 1.02

    risks = []
    if "twinx()" in src:
        risks.append("双y轴尺度不匹配")
    if re.search(r"rotation\s*=\s*45", src):
        risks.append("x标签旋转45°")
    ncol = max([int(x) for x in re.findall(r"ncol\s*=\s*(\d+)", src)] or [1])
    if ncol >= 5:
        risks.append("图例ncol=%d过密" % ncol)
    nlines = len(re.findall(r"\.plot\(", src))
    if nlines >= 6:
        risks.append("%d条线叠加" % nlines)
    nq = max([int(x) for x in re.findall(r"set_xticks\(range\((\d+)\)\)", src)] or [0])
    if nq >= 14:
        risks.append("%d季x标签" % nq)
    if re.search(r"set_ylim\([^)]*ks\[-1\]", src):
        risks.append("极值通道抬高y轴上限")

    fails = []
    if eff_foot and min(eff_foot) < FOOTNOTE_MIN_PT - EPS:
        fails.append("脚注等效%.2fpt < %.1fpt" % (min(eff_foot), FOOTNOTE_MIN_PT))
    if eff_min is not None and eff_min < LABEL_MIN_PT - EPS:
        fails.append("最小字号等效%.2fpt < %.1fpt" % (eff_min, LABEL_MIN_PT))
    if overflow:
        fails.append("脚注单行溢出被裁(估%.0fpt > %.0fpt)" % (est_width, USABLE_PT))

    pngs = re.findall(r"[\"']([^\"']+\.png)[\"']", src)
    return dict(
        name=os.path.basename(path), fig_w_pt=fig_w_pt, scale=scale,
        eff_foot=min(eff_foot) if eff_foot else None, eff_min=eff_min,
        foot_raw=min(foot) if foot else None, note_chars=txt_len,
        est_width=est_width, overflow=overflow, risks=risks, fails=fails, pngs=pngs,
    )


def main():
    argv = sys.argv[1:]
    fig_dir = os.path.abspath(argv[0]) if argv else os.getcwd()
    pattern = argv[1] if len(argv) > 1 else "draw_*.py"
    if not os.path.isdir(fig_dir):
        print("图脚本目录不存在：%s" % fig_dir)
        return 1
    files = sorted(glob.glob(os.path.join(fig_dir, pattern)))
    if not files:
        print("未匹配到图脚本：%s / %s" % (fig_dir, pattern))
        return 1
    rows = [scan(f) for f in files]
    print("扫描目录：%s   匹配：%s   脚本：%d 个" % (fig_dir, pattern, len(rows)))
    hdr = "%-34s %7s %7s %9s %9s %8s %-5s %s" % (
        "脚本", "图宽pt", "缩放比", "脚注等效", "最小等效", "脚注宽", "判定", "风险项")
    print(hdr)
    print("-" * 160)
    nfail = 0
    for r in rows:
        st = "FAIL" if r["fails"] else ("WARN" if r["risks"] else "PASS")
        if r["fails"]:
            nfail += 1
        print("%-34s %7.0f %7.3f %9s %9s %8s %-5s %s" % (
            r["name"], r["fig_w_pt"], r["scale"],
            ("%.2fpt" % r["eff_foot"]) if r["eff_foot"] else "-",
            ("%.2fpt" % r["eff_min"]) if r["eff_min"] else "-",
            ("%.0fpt" % r["est_width"]), st, "; ".join(r["risks"]) or "-"))
        for f in r["fails"]:
            print("      └─ FAIL: %s" % f)
    print("-" * 160)
    print("脚本 %d 个 | FAIL %d | WARN %d | PASS %d" % (
        len(rows), nfail,
        sum(1 for r in rows if not r["fails"] and r["risks"]),
        sum(1 for r in rows if not r["fails"] and not r["risks"])))
    print("\n判据：缩放进版心后脚注 < %.1fpt 或最小字号 < %.1fpt 或脚注单行 > %.1fpt 即不可读。" %
          (FOOTNOTE_MIN_PT, LABEL_MIN_PT, USABLE_PT))
    print("修复公式：脚本字号 = 目标进版心字号 ÷ (%0.1f ÷ (figsize宽 inch × 72))" % USABLE_PT)
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
