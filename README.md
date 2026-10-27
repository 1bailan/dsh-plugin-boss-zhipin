# dsh-plugin-boss-zhipin

BOSS直聘 自动化投递技能，以 **DeepSeek Harness（DSH）插件** 形式分发。

插件本身不做浏览器自动化，而是把一套经过实战打磨的投递技能注册进 DSH：
三层循环（关键词进化 → 分批加载 → 逐条读 JD / 决策 / 投递）、画像驱动语义筛选、
断点续传、每日目标检测、HTML 汇报。浏览器通道走
[Kimi WebBridge](https://www.kimi.com/products/kimi-webbridge)（`127.0.0.1:10086`）。

> A DSH plugin that registers the BOSS直聘 automated job-application skill.
> It provides the skill; the actual browser control is delegated to Kimi WebBridge.

---

## 外部依赖（必须，插件装不上它）

本插件**只注册技能，不包含浏览器控制能力**。真正操作 BOSS 的是本机独立运行的
[Kimi WebBridge](https://www.kimi.com/products/kimi-webbridge)：

| 依赖 | 要求 | 检查方式 |
|------|------|----------|
| Kimi WebBridge daemon | 监听 `127.0.0.1:10086` | `kimi-webbridge status` → `"running": true` |
| Kimi 浏览器扩展 | 已安装、已启用、已连接到 daemon | `"extension_connected": true` |
| 已登录的浏览器 | BOSS直聘 账号已登录（建议 Edge / Chrome） | 能看到职位列表 |
| Python | DSH 自带运行时即可 | `run.ps1` 自动探测 |

**这两样必须由用户自己准备，插件无法代装、无法代登录。** 缺失时技能会在
`env_check.py` 处停下并打印修复步骤，不会盲目开始投递。

安装扩展：<https://www.kimi.com/products/kimi-webbridge>

启动/检查 daemon：

```powershell
& "$env:USERPROFILE\.kimi-webbridge\bin\kimi-webbridge.exe" status
& "$env:USERPROFILE\.kimi-webbridge\bin\kimi-webbridge.exe" start
```

> DSH 处于 `workspace-write` 时，`start` 需要写 `~/.kimi-webbridge` 的日志与 PID，
> 会被沙箱拒绝。用一次 `danger-full-access` 重试，或先在 DSH 外部的终端启动一次。
>
> daemon 提示 `update_available` / `version_mismatch` 时只提示用户，不要自动升级。

---

## 安装

```powershell
# 从 GitHub 安装（tar.gz 直链，已验证）
dsh plugin add https://github.com/1bailan/dsh-plugin-boss-zhipin/archive/refs/heads/main.tar.gz

# 也可以从本地目录安装（设置 → 插件 → 本地目录）
```

> 部分网络环境下 `git clone github.com` 会超时；上面的 tar.gz 直链走
> `codeload.github.com`，通常不受影响。如果你的网络能直连 GitHub，
> 也可以用 `dsh plugin add github:1bailan/dsh-plugin-boss-zhipin`。

安装后重启 DSH / 重新加载 profile。技能列表里会出现 **`boss-zhipin-deliver`**。

要求：

- DSH `>= 0.2.0-0 < 0.3.0`（在 `0.2.1-rc.3` 上开发）
- Node.js `>= 22.19`
- Python：优先使用 DSH 自带运行时，无需单独安装
- **Kimi WebBridge daemon + 已连接的浏览器扩展**（见上方「外部依赖」）

---

## 首次使用

1. 准备一个工作目录（所有状态、画像、汇报都写在这里）：

   ```powershell
   $work = "$env:USERPROFILE\Documents\dsh-boss-run"
   New-Item -ItemType Directory -Force -Path $work | Out-Null
   ```

2. 生成用户画像：

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass `
     -File "<SKILL_DIR>\scripts\run.ps1" -Script init_profile.py -WorkDir $work
   ```

   `<SKILL_DIR>` 是技能目录（安装后通常是
   `%USERPROFILE%\.dsh\profiles\<profile>\node_modules\dsh-plugin-boss-zhipin\skill`，
   或 DSH 报告的 resourceBase）。然后编辑 `<WORK_DIR>\user_profile.json`。

3. 在 DSH 里直接说「帮我投 BOSS 直聘」，或显式加载 `boss-zhipin-deliver` 技能。

完整流程与红线写在 [`skill/SKILL.md`](skill/SKILL.md)。

---

## 它如何工作

```
DSH skill (SKILL.md)
  └── scripts/run.ps1          定位 Python、设置 WORK_DIR、UTF-8
        └── serial_loop.py     三层循环控制器
              ├── recommend_loader.py  职位页懒加载
              ├── jd_reader.py         原页面点卡读 JD
              ├── deliver_engine.py    投递 + 目标检查
              ├── keyword_evolver.py   关键词进化
              └── report_builder.py    HTML 汇报
                        │
                        └── HTTP → Kimi WebBridge :10086 → 已登录浏览器
```

Agent 负责两件需要语义判断的事：

- 对本批岗位做初筛，写 `jd_to_read.json`
- 读 `current_jd.json`，写 `decision.json`（APPROVE / REJECT）

其余全部由 Python 脚本确定性执行。

---

## 用户画像

`skill/user_profile.example.json` 是模板；真实画像保存在 **工作目录** 的
`user_profile.json`，不会随插件分发，也不会写进 `node_modules`。

字段说明见 `skill/SKILL.md` 的「配置字段」一节。

---

## 安全与边界

- 只在用户已登录的浏览器里操作，不读取、不导出 cookie / token / 密码。
- 不绕过 BOSS 的验证码、风控或每日上限；遇到上限立即停止。
- 不自动点击「继续沟通」；投递后验证结果。
- 插件只注册技能，不包含常驻进程、不上传任何数据。

请遵守 BOSS直聘的服务条款，控制投递频率，风险自负。

---

## 仓库结构

```
.
├── index.js              # 技能 provider：ctx.skills.register(...)
├── cordis.patch.yml      # DSH bundle 层：插入插件行
├── package.json
├── locale/{zh,en}.json   # 展示元数据
├── icon.svg
└── skill/
    ├── SKILL.md
    ├── user_profile.example.json
    ├── scripts/          # Python 执行内核 + run.ps1
    └── references/       # DOM、筛选规则、坑位、薪资解密
```

---

## 开发

```powershell
node --check index.js
npm pack --dry-run        # 查看发布内容
```

本地试装：把仓库目录作为 bundle 安装到干净的 DSH profile，确认
`boss-zhipin-deliver` 出现在技能目录、`skill/scripts/run.ps1 -Step status` 可运行。

---

## License

MIT © 2026 1bailan

上游技能基于 WorkBuddy `boss-zhipin-assistant` v5.9 改写，保留其业务逻辑与参考资料。
