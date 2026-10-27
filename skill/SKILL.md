---
name: boss-zhipin-deliver
description: |
  BOSS直聘自动化投递（DeepSeek Harness 插件版 v5.9.1）— 三层循环架构（关键词进化 + 职位页串行投递）。
  通过 Kimi WebBridge（127.0.0.1:10086）控制已登录浏览器，在 BOSS 职位页懒加载岗位，Agent 逐条语义决策后投递。
  支持环境自检、断点续传、每日目标检测、HTML 汇报生成。
  由 dsh-plugin-boss-zhipin 以技能 provider 形式注册；用户画像存放于工作目录，不随插件分发。
metadata:
  version: "5.9.1"
  platform: dsh
  plugin: "dsh-plugin-boss-zhipin"
---

# BOSS直聘自动化投递 · DSH 插件版 v5.9.1

> 本技能由 WorkBuddy 版 `boss-zhipin-assistant` v5.9 移植，并封装为 DSH 插件 `dsh-plugin-boss-zhipin`。
> **执行内核不变**：`scripts/serial_loop.py` 三层循环 + Kimi WebBridge 浏览器通道。
> **平台层已适配 DSH**：pwsh、DSH 自带 Python、工作区文件策略、UTF-8、`ask_user_question`。

---

## 安装

```powershell
# 从 GitHub 安装（tar.gz 直链，已验证）
dsh plugin add https://github.com/1bailan/dsh-plugin-boss-zhipin/archive/refs/heads/main.tar.gz

# 或在设置 → 插件 中搜索本地目录安装
```

安装后重启 DSH（或重新加载 profile），技能目录会出现 `boss-zhipin-deliver`。

> 如果之前装过独立技能版 `boss-zhipin-deliver`，请先移除其中一个，避免同名技能冲突。

**包信息**

| 项 | 值 |
|----|----|
| npm 包名 | `dsh-plugin-boss-zhipin` |
| 注册技能 | `boss-zhipin-deliver` |
| 仓库 | <https://github.com/1bailan/dsh-plugin-boss-zhipin> |
| 许可证 | MIT |

---

## 依赖与前置条件

> **外部依赖，插件装不上它**：本插件只注册技能，不包含浏览器控制能力。
> 真正操作 BOSS 的是本机独立运行的 Kimi WebBridge + 浏览器扩展。
> 用户必须自己装好扩展、启动 daemon、登录 BOSS直聘；缺失时先停下修环境，
> 不要继续投递。

1. **Kimi WebBridge daemon**：监听 `http://127.0.0.1:10086`。
   - 检查：`kimi-webbridge status` → `"running": true`
   - 启动：`kimi-webbridge start`（沙箱拒绝时见下文）
2. **Kimi 浏览器扩展**：已安装、已启用、已连接到 daemon，且浏览器已登录 BOSS直聘。
   - 扩展未连接时 `status` 显示 `"extension_connected": false`，任何页面操作都会失败。
   - 说明与安装：<https://www.kimi.com/products/kimi-webbridge>
3. **Python**：无需手动安装。`run.ps1` 会依次尝试：
   - `$env:DSH_PYTHON`
   - `%USERPROFILE%\.dsh\dsh-runtimes\*\dependencies\python\python.exe`
   - PATH 中的 `python`（跳过 WindowsApps 占位符）
4. **工作目录**：所有状态、画像和汇报都写在这里，推荐 `<DSH 工作区>\boss-run`。

### 用户画像不在插件包里

插件目录通常位于 `node_modules`（只读），因此**不要**把 `user_profile.json` 写进技能目录。
画像固定放在 `<WORK_DIR>\user_profile.json`：

```powershell
$work = Join-Path $env:USERPROFILE 'dsh-boss-run'
New-Item -ItemType Directory -Force -Path $work | Out-Null
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<SKILL_DIR>\scripts\run.ps1" -Script init_profile.py -WorkDir $work
```

然后把示例里的占位字段改成真实信息。

### 关于沙箱与 daemon

DSH 处于 `workspace-write` 时，`kimi-webbridge start` 需要写 `~/.kimi-webbridge` 下的日志和 PID，
会被沙箱拒绝（`Access is denied` / `rotate log` 失败）。二选一：

- 用一次 `danger-full-access` 重试启动（daemon 常驻后，脚本只走 localhost HTTP，不再需要放宽）；
- 或由用户在 DSH 之外的普通终端执行一次 `kimi-webbridge start`。

**永远不要**自行 `stop` / `restart` / `upgrade` daemon。

---

## 统一调用方式

DSH 的 PowerShell 执行策略默认禁止直接 `& .\xxx.ps1`。**必须**用：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<SKILL_DIR>\scripts\run.ps1" -Step <step> [-Index N] [-Keyword "..."] [-WorkDir "<WORK_DIR>"]
```

- `<SKILL_DIR>`：本 SKILL.md 所在目录（插件安装后为 `...\dsh-plugin-boss-zhipin\skill`）。
- `run.ps1` 负责：定位 Python、设置 `BOSS_WORK_DIR`、强制 UTF-8、组装参数。
- 运行其他脚本：`-Script env_check.py`、`-Script init_profile.py`（不需要 `-Step`）。

> 首次运行若报找不到 Python，先调用 `load_workspace_dependencies`，
> 把返回的 `python` 路径设成 `$env:DSH_PYTHON` 后重试。

---

## 执行流程

### 步骤 0：准备工作目录与画像

```powershell
$work = Join-Path $env:USERPROFILE 'dsh-boss-run'
New-Item -ItemType Directory -Force -Path $work | Out-Null
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<SKILL_DIR>\scripts\run.ps1" -Script init_profile.py -WorkDir $work
```

若画像已存在，`init_profile.py` 只打印路径，不会覆盖。
后续所有命令都带 `-WorkDir $work`。

### 步骤 1：初始化（`--step init`）

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<SKILL_DIR>\scripts\run.ps1" -Step init -WorkDir $work
```

脚本会：检查 WebBridge → 建立标签页 → 重置状态 → 导航到 BOSS 职位页。

> ⚠️ **URL 陷阱（必须遵守）**：`/web/geek/recommend` 是**已沟通/已投递历史页**，不是推荐页。
> 页面标题为「BOSS直聘」且含「已投递」「沟通过」字样时即为错误页面。
> 正确的职位页 URL 是 **`https://www.zhipin.com/web/geek/job`**（实际跳转后 `/web/geek/jobs`，标题「{城市名}招聘」）。
> 导航后必须确认标题含目标城市名。

### 步骤 1.5：确认投递方向（强制）

> 本技能面向多用户复用，**严禁跳过**。

读取 `<WORK_DIR>\user_profile.json`，用 `ask_user_question` 展示并确认：

- 姓名 `user_name`
- 目标城市 `target_city` / `city_code`
- 最低薪资 `min_salary_k`（K，0 = 不限）
- 日投递目标 `daily_target`
- 目标领域 `domain_description`
- 偏好 `prefer`、排除 `avoid`
- 是否排除大厂 `prefer_no_big_company`、猎头 `prefer_no_headhunter`
- 搜索关键词 `search_keywords`（前 10 个）

用户确认后才进入步骤 2。

### 步骤 2：中层循环 — 滚动加载（`--step next-batch`）

```powershell
... -Step next-batch -WorkDir $work
```

输出本批约 50 条岗位（`[page_order] 标题 薪资 公司 行业`）。**控制台输出不含 `jobId`**，
完整字段在 `<WORK_DIR>\surface_cache.json`（7 字段：`page_order, jobId, title, salary, salary_max_k, company, industry`）。

**Agent 初筛**：

1. `read` 打开 `surface_cache.json`；
2. 按本批输出的 `page_order` 取出本批条目；
3. 按画像的 prefer/avoid/domain_description 语义筛选；
4. 合资格岗位用 `write` 整份写入 `<WORK_DIR>\jd_to_read.json`（数组，`page_order` 升序）：

```json
[
  {"page_order": 1, "jobId": "xxxxxxxx", "title": "嵌入式软件工程师", "salary": "12-18K", "salary_max_k": 18, "company": "某某科技", "industry": "智能硬件"}
]
```

必须保留 `jobId`、`page_order`、`title`；其余字段从缓存原样带上。
`next-batch` 已删除旧文件，`write` 可直接新建。

### 步骤 3：内层循环 — 逐条读 JD + 决策 + 投递

**3a. 读取 JD**

```powershell
... -Step read -Index N -WorkDir $work
```

JD 写入 `<WORK_DIR>\current_jd.json`。

**3b. Agent 决策**

`read` 读取 `current_jd.json`，按画像判断：

- **APPROVE**：匹配 prefer，薪资 ≥ `min_salary_k`，城市匹配，不在 avoid
- **REJECT**：命中 avoid / 排除领域 / 猎头外包 / 大厂（按开关）/ 机械预筛项（保安、保洁、销售、主播、实习生等）
- 不确定宁可 REJECT

用 `write` 写 `<WORK_DIR>\decision.json`（无需先读，`decide` 每轮删除）：

```json
{"decision": "APPROVE", "reason": "STM32 + FreeRTOS，1-3 年，12-18K，符合方向"}
```

**3c. 执行决策**

```powershell
... -Step decide -Index N -WorkDir $work
```

APPROVE 时自动投递并检查目标。

**3d. 终止条件**

- 投递目标达标 → **强制跳到步骤 5**
- 致命错误（每日上限）→ **强制跳到步骤 5**
- 本批处理完 → 回步骤 2

### 步骤 4：外层循环 — 关键词进化（`--step evolve`）

```powershell
... -Step evolve -WorkDir $work
... -Step navigate-search -Keyword "STM32" -WorkDir $work
```

**关键词穷尽 → 强制跳到步骤 5**。

### 步骤 5：生成汇报（`--step finish`，强制）

> 以下任一条件触发必须执行：目标达标、每日上限、页面穷尽无新关键词、用户要求停止。

```powershell
... -Step finish -WorkDir $work
```

生成 `<WORK_DIR>\投递汇总.html`（只统计本轮，口径由 `run_baseline.json` 决定）。
若技能目录存在 `assets\wechat_qr.jpg` / `assets\alipay_qr.jpg`，报告附赞赏码；没有则自动省略。

---

## 命令速查

| 目的 | 参数 |
|------|------|
| 环境自检 | `-Script env_check.py` |
| 初始化 | `-Step init` |
| 加载下一批 | `-Step next-batch` |
| 读第 N 条 JD | `-Step read -Index N` |
| 执行第 N 条决策 | `-Step decide -Index N` |
| 关键词进化 | `-Step evolve` |
| 搜索新关键词 | `-Step navigate-search -Keyword "关键词"` |
| 生成汇报 | `-Step finish` |
| 查看进度 | `-Step status` |
| 初始化画像 | `-Script init_profile.py` |

统一前缀：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<SKILL_DIR>\scripts\run.ps1" ... -WorkDir $work
```

---

## 状态文件（均在 WORK_DIR）

| 文件 | 作用 |
|------|------|
| `user_profile.json` | 用户画像（**唯一用户数据源**） |
| `page_state.json` | 页面级进度 |
| `batch_state.json` | 分批级进度 |
| `surface_cache.json` | 全量岗位缓存（7 字段） |
| `jd_to_read.json` | 本批待读列表（Agent 写） |
| `current_jd.json` | 当前 JD（脚本写，Agent 读） |
| `decision.json` | 当前决策（Agent 写，脚本读后删除） |
| `stream_progress.json` | 投递断点续传（跨天累积） |
| `run_baseline.json` | 本轮基线（`init` 锁定，决定汇报口径） |
| `daily_baseline.json` | 今日基线（决定「今日新增」达标判定） |
| `投递汇总.html` | 最终汇报 |

---

## 故障排查

### 1. WebBridge 不可达

```powershell
& "$env:USERPROFILE\.kimi-webbridge\bin\kimi-webbridge.exe" status
& "$env:USERPROFILE\.kimi-webbridge\bin\kimi-webbridge.exe" start
```

- `rotate log ... Access is denied` → 沙箱限制，用一次 `danger-full-access` 重试，或让用户在外面启动。
- 端口被占用 → 按 `kimi-webbridge` 技能说明改 `~/.kimi-webbridge/config.json` 的 `addr`，并让用户把扩展连到新端口。
- `update_available` / `version_mismatch` → 只提示用户，不要自行升级。

### 2. `extension_connected: false`

请用户：

1. 确认浏览器里 Kimi 扩展已启用；
2. 扩展侧边栏 → 设置 → 本地 Agent 远程控制 → 连接地址 `ws://127.0.0.1:10086/ws`；
3. 确认 BOSS直聘 已登录。

然后重跑 `-Script env_check.py`。

### 3. 中文输出乱码

`run.ps1` 已设置 `PYTHONIOENCODING=utf-8`、`PYTHONUTF8=1`、`[Console]::OutputEncoding`。
不要绕过 `run.ps1` 直接调用 python。

### 4. 找不到 Python

先 `load_workspace_dependencies`，把返回的 `python` 设为 `$env:DSH_PYTHON` 再重试。

### 5. 执行策略拒绝运行 .ps1

必须走 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ...`，
不要 `& .\run.ps1`，不要 `Set-ExecutionPolicy`。

### 6. 画像不存在

```
用户画像文件不存在: <WORK_DIR>\user_profile.json
```

运行 `-Script init_profile.py -WorkDir $work`，然后填写字段。

### 7. `write` 报「先读后写」

正常情况下 `decision.json` / `jd_to_read.json` 已被脚本删除，`write` 可直接新建。
若仍提示，先 `read` 一次旧文件再 `write`。

---

## 红线

1. `/web/geek/recommend` 是历史页，禁止作为岗位来源；职位页唯一正确 URL 是 `https://www.zhipin.com/web/geek/job`。
2. 绝不 navigate 到 `job_detail` URL 读 JD（必须在原页面点卡读）。
   - **唯一例外**：`deliver_detail.py` 详情页直投兜底，见 `references/pitfalls.md` B35。
3. 投递后绝不点「继续沟通」，选「留在此页」。
4. 投递后必须验证实际结果。
5. 每日上限是致命错误，立即停止并生成汇报。
6. 浏览器操作全部经 WebBridge；禁止 CDP 直连、禁止 `bsk_*` 混用。
7. **强制 finish**：任何终止路径都必须生成 `投递汇总.html`。
8. **汇报口径 = 本次投递**；全量历史用 `report_builder.py --all`。

---

## 配置字段（user_profile.json）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_name` | string | 否 | 姓名，用于账户匹配和报告 |
| `role_summary` | string | 否 | 一句话角色概述 |
| `experience` | string | 否 | 详细经验，用于决策 |
| `domain_description` | string | 推荐 | 目标领域详细描述；不填则由 prefer/avoid 拼接 |
| `target_city` | string | 是 | 目标城市（如「深圳」） |
| `city_code` | string | 是 | 城市编码（如 `101280600`） |
| `min_salary_k` | number | 否 | 最低薪资（K），0 = 不限 |
| `max_salary_k` | number | 否 | 参考上限（用于判断职级） |
| `daily_target` | number | 是 | 每日投递目标 |
| `session_name` | string | 否 | WebBridge 会话名，默认 `boss-main` |
| `prefer` | string[] | 否 | 偏好岗位关键词 |
| `avoid` | string[] | 否 | 排除岗位关键词 |
| `prefer_no_big_company` | boolean | 否 | 排除大厂（已上市 / 2000 人以上） |
| `prefer_no_headhunter` | boolean | 否 | 排除猎头岗位 |
| `search_keywords` | string[] | 是 | 搜索关键词（纯职位词，不含城市） |
| `c_exclude` | string[] | 否 | 公司名黑名单；不填用内置通用值 |
| `t_exclude` | string[] | 否 | 标题排除词；不填用内置通用值 |

**城市编码**：打开 <https://www.zhipin.com/> → 选城市 → URL `...?city=XXXXXX`，数字即 `city_code`。

---

## 脚本结构

```
skill/
├── SKILL.md
├── user_profile.example.json
├── scripts/
│   ├── run.ps1               — DSH 启动器（Python / WORK_DIR / UTF-8）
│   ├── init_profile.py       — 首次生成 user_profile.json
│   ├── profile_loader.py     — 中央配置加载器（工作目录优先）
│   ├── env_check.py          — 环境自检 + 自动修复
│   ├── webbridge_client.py   — WebBridge HTTP 客户端（10086）
│   ├── recommend_loader.py   — 职位页导航 + 分批懒加载
│   ├── surface_cache.py      — 精简字段缓存
│   ├── jd_reader.py          — 页面内点卡读 JD
│   ├── deliver_engine.py     — 投递执行 + 目标检查
│   ├── deliver_detail.py     — 详情页直投兜底
│   ├── report_builder.py     — HTML 汇报
│   ├── keyword_evolver.py    — 关键词进化 + 搜索导航
│   ├── serial_loop.py        — 三层循环主控制器
│   └── ...
└── references/               — DOM 结构、筛选规则、坑位、薪资解密
```

---

## 版本历史

| 版本 | 变更 |
|------|------|
| 5.9.1 | 封装为 DSH 插件：技能 provider 注册、画像改存工作目录、新增 `init_profile.py`、插件安装说明 |
| 5.9-dsh | DSH 适配：`run.ps1`、`write` 工具写决策、UTF-8、执行策略与沙箱排障 |
| 5.9 | 汇报口径改为「本次投递」，新增 `run_baseline.json` |
| 5.8 | 详情页直投兜底 |
| 5.7 | 修复跨天假达标 |
