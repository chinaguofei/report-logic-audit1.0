# -*- coding: utf-8 -*-
"""report-logic-audit 公共件（v1.1.7 抽取）。

审计主脚本 audit_docx.py 与推理检查器 check_reasoning.py 共享：
- 发现发射器 add() 与全局 findings 列表（消除 audit_docx / check_reasoning 各抄一份）；
- 中文序号常量 CN_NUM；
- 严重度 → 退出码映射 severity_exit()（供各脚本统一映射，代码审查 C1-5）。

历史：v1.1.6 及之前，add() 在两个脚本逐字重复、CN_NUM 各定义一份。Pass A 架构评审
（软件工坊）裁定「抽公共件」而非拆巨石，本文件即为该裁定落地。
依赖：纯 Python 标准库（无第三方依赖）。
"""

CN_NUM = "一二三四五六七八九十"

# 每个 CLI 进程启动时为空；add() 向此列表追加。
# audit_docx / check_reasoning 均 `from common import findings, add`，共用同一实例。
findings = []


def add(level, code, pos, msg, detail=""):
    """level: BLOCK / FIX / SUGGEST"""
    findings.append({"level": level, "code": code, "pos": pos, "msg": msg, "detail": detail})


def severity_exit(counts):
    """严重度 → 退出码。BLOCK 命中 → 1，否则 0。供各脚本统一映射（代码审查 C1-5）。"""
    if counts.get("BLOCK", 0) > 0:
        return 1
    return 0
