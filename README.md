# report-logic-audit · 文章逻辑审校

文章交付前的查漏补缺、逻辑校验与推理终结。适用于任何已完成的中文文章（英文格式关加 `--lang en`）：上市公司研报与行业报告、评论时评、学术论文与综述、科普解释文、方案与可行性、汇报与公文、白皮书与营销文案、讲稿、教程 SOP。

**当前版本：v1.1.9**（与 SkillHub 同步发布）

## 六关审校

论点—证据闭环 / 概念与口径一致 / 结构完整与衔接 / 逻辑链条 / 推理终结 / 数据与图文一致

输出分级清单（阻断 / 须修 / 建议），每条带定位、原文、病灶代号与最小改法，附证伪台账。

## 其他模式

- **论证骨架**：断言密度与承重章分析
- **逻辑总结五问**：结项前快速自检
- **润色模式**：只改表达层、不动数字
- **格式审校**：错别字 / 全角字符 / 标题层级 / 字体字号行距与中英文空格；`--fix` 只统一字体行距且逐字校验文字不变；英文加 `--lang en`（pyspellchecker 离线拼写检查）

## 安装

把 `report-logic-audit/` 目录放入 Agent 技能目录（如 WorkBuddy 的 `~/.workbuddy/skills/`），或直接下载 `report-logic-audit_v1.1.9.zip` 解压使用。

## 更新说明

见 [CHANGELOG.md](report-logic-audit/CHANGELOG.md)。v1.1.9（2026-11-03）：新增英文格式审校 `--lang en`，中文六关回归零退化；文档与中英文样例同步更新。

## 在线页面

- SkillHub：https://www.skillhub.cn/skills/user_baa858e7/article-logic-audit

---

作者：**行者无疆** · MIT License
