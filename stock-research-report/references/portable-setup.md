# 跨设备使用与安装

用户会出差、换电脑。本技能通过**两条通道**提供，两边内容必须保持一致。

## 双通道说明

| 通道 | 位置 | 触发方式 |
|---|---|---|
| **A · 独立技能** | `~/.workbuddy/skills/stock-research-report/` | 对话中说到研报需求时自动加载 |
| **B · 专家** | `~/.workbuddy/plugins/marketplaces/my-experts/plugins/stock-analyst/skills/stock-research-report/` | 召唤「个股研报分析师」专家时随专家加载 |

两条通道并行生效，用户可按习惯任选。**改动技能后必须同步两边并刷新打包产物**。

## 同步方式（改完技能后必做）

```bash
cd <workspace>
python sync_skill.py
```

该脚本会：同步技能源 → 专家包内副本 → 校验两边逐字节一致 → 打包技能包 → 校验并重注册专家 → 打包专家包 → 备份到工作区 `skill-package/`。

> 若工作区没有 `sync_skill.py`，可手动执行：
> `cp -r ~/.workbuddy/skills/stock-research-report/* <专家目录>/skills/stock-research-report/`，
> 再依次跑 `validate_expert.py` → `register_expert.py` → `package_expert.py`。

## 换设备：三种带法（按省心程度）

### ⭐ 方案 A · 云端市场订阅（首选，真正"任意设备唤醒即用"）

WorkBuddy 原生支持从远程 Git 仓库/HTTPS URL 订阅插件市场，配 `autoUpdate` 自动更新。
把本能力包托管为云端市场后，**任意设备只需订阅一次，之后自动跟随更新**。

```bash
# 新设备一次性执行
/plugin marketplace add 你的用户名/personal-marketplace
/plugin install stock-analyst@personal-marketplace
```

- 云端仓库由工作区 `cloud-marketplace/` 生成（含 `marketplace.json` + 专家包）
- 推送更新：`python sync_skill.py` → `python publish_marketplace.py --push`
- 详细手册：`cloud-marketplace/SETUP.md`
- 优点：不重复说需求、不传模板、改完自动同步到所有设备

### 方案 B · 带专家 zip（离线兜底，推荐）

`Desktop/WB/stock-analyst.zip`（≈357 KB，2026-09-28 刷新）→ 新设备 WorkBuddy →「专家」→「我的专家」→ 导入专家包。
人设 + 方法论 + 技能 + 头像一体，导入后召唤即用。

### 方案 C · 带技能 zip（轻量）

`Desktop/WB/stock-research-report.zip`（≈47 KB，2026-09-28 刷新）→ 新设备 WorkBuddy →「技能」→「添加技能」→「上传技能」。
导入后在对话中直接说研报需求即可触发。

三个产物在工作区 `skill-package/` 与 `cloud-marketplace/` 均有备份。

## 新设备环境准备

技能脚本依赖 Python + 三个库。新设备上若缺依赖，先装：

```bash
# WorkBuddy 自带托管 Python（路径随版本号变化，先确认）
<托管python> -m venv <venv路径>
<venv>/Scripts/pip install python-docx matplotlib numpy
```

Windows 上 WorkBuddy 托管 Python 通常在：
`C:\Users\<用户名>\.workbuddy\binaries\python\envs\default\Scripts\python.exe`

若不存在，用 `install_binary` 工具安装 Python 3.x，或直接询问用户当前可用的 Python 路径。

**中文字体**：K 线图需要中文字体。脚本内置回退列表
（Microsoft YaHei → SimHei → SimSun → Noto Sans CJK SC → DejaVu Sans）。
macOS 上通常命中 Noto 或需 `brew install --cask font-noto-sans-cjk-sc`；
若图中中文显示为方块，说明字体全未命中，需补装中文字体。

## 目录路径差异（换机时需注意）

技能内脚本使用相对路径（`data/...`）与自动推导的桌面路径，换设备一般无需改代码。
若需调整，改这些常量：

| 文件 | 常量 | 说明 |
|---|---|---|
| `build_report.py` | `OUT_SRC` | 中间产物路径（相对 workspace） |
| `draw_kline.py` | `SRC` / `OUT` | 数据与图片路径（相对 workspace） |
| `insert_img.py` | `DST_DIR` | 输出目录，已用 `expanduser("~")/Desktop/WB` 自动适配 |

建议先在新设备上跑一次完整流程（选一只熟悉的股票）验证无误。

## 备用方案：无技能环境时

若新设备暂时无法安装技能或专家，可让 WorkBuddy 直接读本文件所在目录的其他文件，
或把 `SKILL.md` + `references/` 的内容粘贴给 WorkBuddy 作为上下文，
按其中规格手工执行（会慢一些，但产出一致）。
