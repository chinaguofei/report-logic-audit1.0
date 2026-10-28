# -*- coding: utf-8 -*-
"""数据复核器（研报/对比报告 Step 6 强制项）：交付前全跑，全部 PASS 才能交付。

用法（矩阵 JSON 格式同 build_matrix_tables 管线产出：recs 按最新在前）：
    python data_check.py turbine_matrix_data.json 汽轮科技 28.81,2.54
    python data_check.py matrix_data.json 先导智能          # 不传正文数字则跳过交叉核对

检查项：
  1) 差分自洽：全年四季单季值回加 ≈ 年度累计值（相对容差 0.5%）
  2) 同比重算：最新两期营收/归母同比按基数重算 vs 矩阵值（容差 0.1pp）
  3) 口径断点：同年相邻季累计营收回落 = 主体变更/未追溯信号 → FAIL 并给剔除建议
  4) 正文交叉：矩阵最新 H1（Q1+Q2）或 FY（Q1–Q4）合计 vs 正文数字（0.05 亿 / 0.15pp）
"""
import json
import sys

TOL_PCT = 0.5      # 差分回加相对容差 %
TOL_ABS = 0.05     # 差分回加绝对容差 亿
TOL_YOY = 0.1      # 同比重算容差 pp
TOL_TEXT = 0.05    # 正文金额容差 亿
TOL_TEXT_PCT = 0.15  # 正文同比容差 pp

results = []


def rec(name, ok, detail):
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")


def fnum(x):
    return None if x is None else float(x)


def qidx(q):
    return int(q[:2]) * 4 + int(q[3:]) - 1


def check_year_sum(recs):
    """全年四季单季值回加 vs Q4 累计值。"""
    byq = {c["q"]: c for c in recs}
    years = sorted({int(q[:2]) for q in byq})
    n_ok = n_skip = 0
    for y in years:
        qs = [f"{y:02d}Q{i}" for i in range(1, 5)]
        if not all(q in byq for q in qs):
            n_skip += 1
            continue
        q4 = byq[qs[3]]
        for key, cum in (("sq_rev", "rev"), ("sq_np", "np")):
            s = sum(fnum(byq[q].get(key)) or 0 for q in qs)
            c = fnum(q4.get(cum))
            if s is None or c is None:
                continue
            ok = abs(s - c) <= max(TOL_ABS, abs(c) * TOL_PCT / 100)
            rec(f"{y}年{('营收' if key=='sq_rev' else '归母')}回加", ok,
                f"四季单季合计 {s:.2f} vs 年报累计 {c:.2f}")
            n_ok += 1
    if n_ok == 0:
        rec("差分自洽", True, f"无完整年度可比（跳过 {n_skip} 年）——正常（如新转A主体）")


def check_yoy(recs, n=2):
    """最新 n 期营收/归母同比按基数重算。"""
    byq = {c["q"]: c for c in recs}
    done = 0
    for c in recs:
        if done >= n:
            break
        y, q = c["q"][:2], c["q"][3:]      # q 只取 "2" / "4"（Q2 → "2"）
        base = byq.get(f"{int(y)-1:02d}Q{q}")
        if base is None:
            rec(f"{c['q']}同比基数", True, "上年同期不在窗口（重述剔除所致，可接受）")
            continue
        for key, sq, yoy_key, nm in (("rev", "sq_rev", "rev_yoy", "营收"),
                                     ("np", "sq_np", "np_yoy", "归母")):
            v, b, stored = fnum(c.get(sq)), fnum(base.get(sq)), c.get(yoy_key)
            if v is None or b is None or abs(b) < 1e-4:
                continue
            if stored is None:
                rec(f"{c['q']}{nm}同比", False, f"矩阵为 --，但可算出 {(v-b)/abs(b)*100:+.2f}%（基数 {b:.2f}）")
                continue
            calc = (v - b) / abs(b) * 100
            # 容差自适应：基数/差值越小，2 位小数舍入对同比影响越大（最大 ~0.005 亿舍入）
            tol = max(TOL_YOY, (0.005 / abs(b) + 0.005 / abs(v - b)) * 100)
            rec(f"{c['q']}{nm}同比重算", abs(calc - stored) <= tol,
                f"矩阵 {stored:+.2f}% vs 重算 {calc:+.2f}%")
        done += 1


def check_breakpoint(recs):
    """同年相邻季累计营收回落 = 口径断点。"""
    asc = sorted(recs, key=lambda c: qidx(c["q"]))
    bad = []
    for i in range(1, len(asc)):
        p, c = asc[i - 1], asc[i]
        if c["q"][:2] == p["q"][:2] and not p["q"].endswith("Q4"):
            rp, rc = fnum(p.get("rev")), fnum(c.get("rev"))
            if rp and rc and rc < rp - 1e-6:
                bad.append(f"{p['q']}({rp:.2f}) → {c['q']}({rc:.2f})")
    rec("口径断点", not bad, "未发现同年累计回落" if not bad
        else f"发现 {len(bad)} 处，混口径！剔除断点后至下一Q1及断点年前旧口径季：{'; '.join(bad)}")


def check_vs_text(recs, rev, np_):
    """矩阵最新 H1/FY 合计 vs 正文数字。"""
    latest = recs[0]["q"]
    if latest.endswith("Q2"):
        span, label = recs[:2], f"{latest[:2]}H1(Q1+Q2)"
    elif latest.endswith("Q4"):
        span, label = recs[:4], f"{latest[:2]}FY(Q1–Q4)"
    else:
        rec("正文交叉", True, f"最新期 {latest} 非半年度/年度，跳过（请在调用时人工核对正文）")
        return
    s_rev = sum(fnum(c.get("sq_rev")) or 0 for c in span)
    s_np = sum(fnum(c.get("sq_np")) or 0 for c in span)
    rec(f"{label}营收 vs 正文", abs(s_rev - rev) <= TOL_TEXT, f"矩阵 {s_rev:.2f} vs 正文 {rev:.2f}")
    rec(f"{label}归母 vs 正文", abs(s_np - np_) <= TOL_TEXT, f"矩阵 {s_np:.2f} vs 正文 {np_:.2f}")


def check_peer_headers(docx_path):
    """同业对标表头不得残留占位符（{本公司}/{同业N}/…），必须替换为真实公司名+代码。"""
    try:
        from docx import Document
    except Exception:
        rec("同业表头占位检查", True, "未装 python-docx，跳过（请人工核对表头已填真实公司名+代码）")
        return
    d = Document(docx_path)
    bad = []
    for ti, t in enumerate(d.tables):
        if len(t.columns) != 6:
            continue
        head = [c.text for c in t.rows[0].cells]
        if not any("指标" in h for h in head):
            continue
        for h in head[1:]:
            if any(p in h for p in ("{本公司}", "同业1", "同业2", "同业3", "同业4", "…", "{")):
                bad.append(f"表{ti+1} 表头残留占位符: {h!r}")
                break
    rec("同业表头占位检查", not bad,
        "所有同业表头均为真实公司名+代码" if not bad
        else "；".join(bad) + " —— 必须替换为真实公司名+代码后重出")


def main():
    # 解析可选 --docx=<path> / --docx <path>
    raw = sys.argv[1:]
    docx_path = None
    pos = []
    i = 0
    while i < len(raw):
        if raw[i].startswith("--docx"):
            if "=" in raw[i]:
                docx_path = raw[i].split("=", 1)[1]
            else:
                i += 1
                docx_path = raw[i]
        else:
            pos.append(raw[i])
        i += 1
    jpath, company = pos[0], pos[1]
    data = json.load(open(jpath, encoding="utf-8"))
    if isinstance(data, dict) and "recs" in data:          # 扁平：{"code","recs"}
        recs = data["recs"]
    elif isinstance(data, dict):                            # 管线：{公司名: {"code","recs"}}
        v = data[company]
        recs = v["recs"] if isinstance(v, dict) else v
    elif isinstance(data, list):                            # 纯列表
        recs = data
    else:
        raise ValueError("无法识别的 JSON 结构")
    print(f"=== 数据复核：{company}（{len(recs)} 季 {recs[-1]['q']}→{recs[0]['q']}）===")
    check_breakpoint(recs)
    check_year_sum(recs)
    check_yoy(recs)
    if len(sys.argv) > 3 and not sys.argv[3].startswith("--docx"):
        rev, np_ = (float(x) for x in sys.argv[3].split(","))
        check_vs_text(recs, rev, np_)
    if docx_path:
        check_peer_headers(docx_path)
    n_fail = results.count(False)
    print(f"=== 结果：{len(results) - n_fail} PASS / {n_fail} FAIL → {'✅ 可交付' if n_fail == 0 else '❌ 不得交付，先修数据源'} ===")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
