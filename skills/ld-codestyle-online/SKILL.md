---
name: ld-codestyle-online
description: "Use LD/LastDreamTeam rules when writing, reviewing or committing in repositories where we are an owner, member or collaborator. If our role is unclear, merge permission for the current Git account on the target repository is sufficient. Load references as needed for comments, shared memory, architecture, branches, PRs, Issues, README files and reporting results."
version: 0.7.0
author: "LD (LastDream / 最后的梦), Hermes Agent"
license: "CC-BY-SA-4.0; scripts: AGPL-3.0-only"
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [unity, governance, human-agent, codestyle]
---
> **来源标记**：AI 自建 · 人类设计：LD · 整理实现：列克星敦 · 2026-09-28

# LD CodeStyle Online

让人类通过 Markdown、自然语言和小而清楚的代码契约表达创意、设计与边界；Agent 承接可替换的实现与验证。本技能分层适用：**提交身份覆盖一切仓库；共享 Markdown 记忆在适用仓库默认启用；Unity/OOP 架构规则仅在适配范围使用。**不同引擎使用真实模块路径映射 README 与 Agentic，不把 Unity 目录生搬过去。规则覆盖不代表所有宿主与引擎均已实机验收。本在线版基于 LD v6 实践整理，独立版本 **0.7.0**，不与旧版叠加执行。

这是 LastDream / LastDreamTeam 的组织内部规范。主动使用本技能即表示了解这套规范并自行负责。适用仓库包括我们作为主人、成员或合作者参与的仓库，不限归属、公开性、引擎或语言。已知参与关系就直接使用。角色不确定时，当前 Git 账号对目标仓库有合并权限即可使用，无需每次查权限。没有参与关系且无合并权限的他人仓库不接管。按当前任务阅读，编码时照常遵守记忆、提交、分支审查、注释和适配的架构约定。

## 何时启用

1. **提交身份是全仓库规则**：所有 AI 的新提交均适用，与引擎、语言、项目重量、是否采用OOP及共享记忆黑名单无关。私有按 Bot/Agent 强制准确身份。公开默认首行只写摘要，不写 `##模型：` 身份段；主人可明确要求公开名称。细则见[提交规范](references/commit.md)。
2. **共享 Markdown 记忆在适用仓库默认启用**。从所属 `README.md` 找到本区域的 `Agentic/USER.md`、`Agentic/MEMORY.md` 和 `Agentic/DEBUG.md`。只读任务按需读取，写任务在触及的区域维护有来源的内容，首次需要记录时补齐相应入口。
3. 日常使用无需配置或查询黑名单。已有明确排除继续有效。只有需要核实或调整某个项目的例外时才用[项目范围工具](references/memory-scope.md#cli-与生效判定)。
4. **源码风格适用于适用仓库的一方代码，不论是否Unity。** 编写或审查时读[函数文档与原理注释](references/comments.md)、[注释归属](references/comments.md#注释归属)、[局部格式整理](references/contract.md#代码格式整理)和[插件边界](references/contract.md#插件纯净与必要改写)。按用户当次明确要求、`AGENTS.md` 和区域 README 核对采用的结构。`LD:`、`I<类型>Base`、`.Agentic` 是定位线索，不能仅凭目录、fork、孤立标记或随包示例判断。Unity 工程同时有 `Assets/` 和 `ProjectSettings/ProjectVersion.txt` 时采用 Inspector 和资产规则。配对 Base、Model/Manager/ViewModel/View 等随实际结构执行，精选 SQLite 历史由责任区另行声明。
5. **协作流程与写作约定**：[分支与两次合并请求](references/branch-workflow.md)、[合并请求的技术审查](#合并请求的技术审查)是项目未声明自己分支、合并或审查规则时的默认做法，适用于上述适用仓库，与引擎或项目是否轻量无关。真正涉及分支、PR 或合并，或在主分支上开始改动时再读该页。项目 `AGENTS.md`/README 有约定以项目为准。[Issue 与根 README](references/public-writing.md)和[给人类的最终回执](references/interaction.md#给人类的最终回执)适用于 AI 在适用仓库写给人看的产物，目标项目已有规则优先。它们不新增提交、推送、合并或发布授权，也不把用户当前已明确的决定再设一道闸。
6. 当前请求和最近工程规则优先；默认记忆维护不扩大业务任务、提交、发布、重构或第三方修改授权。生成代码、第三方原插件和无关工程不因路径映射被接管。

## 按需阅读

先看当前任务在做什么，再打开对应说明。不要在任务开头把下列页面全部读完。

| 当前任务 | 再读 |
|---|---|
| 提交、署名、推送内容或公开前脱敏 | [提交规范](references/commit.md)，含[默认推送边界](references/commit.md#默认提交与推送边界完整复现更新) |
| 编写或审查已采用的一方源码 | [强制注释](references/comments.md) 与 [协作契约](references/contract.md) 中的格式、插件部分 |
| 项目确实是 Unity（同时有 `Assets/` 和 `ProjectSettings/ProjectVersion.txt`） | [协作契约](references/contract.md) 中的 Unity、Inspector、资产与 OOP 部分。不要把 `I*Base`、画面验收或场景/预制件规则套到普通非 Unity 脚本上 |
| 项目确实是 UE、Cocos、Godot 或同类引擎 | [跨项目记忆与黑名单](references/memory-scope.md) 里对应的路径映射，以及该引擎已采用的结构约定 |
| 适用仓库的编码任务，或在授权范围内读取已有 `Agentic/USER.md`、`MEMORY.md`、`DEBUG.md` | [记忆范围](references/memory-scope.md)、[目录共享上下文](references/directory-context.md)、需要时再读 [区域历史](references/memory-history.md)。每份文件头部须自足说明用途与边界 |
| 任务实际涉及分支、PR、合并，或收尾任务范围内的 Issue | [分支与两次合并请求](references/branch-workflow.md)，含[Issue 收尾](references/branch-workflow.md#任务范围内的-issue-必须收尾) |
| 正在写 Issue 或项目根 README | [Issue 与根 README](references/public-writing.md) |
| 正在向人询问、写回执，或推送前无法安全决策 | [交互约定](references/interaction.md)，含[最终回执](references/interaction.md#给人类的最终回执)和[推送前求助](references/interaction.md#推送前无法安全决策时的求助) |
| 占用真实前台桌面或使用 Computer Use | [前台桌面操作用完立即释放](references/interaction.md#前台桌面操作用完立即释放) |
| 创建验收页、脚本、截图、日志或临时构建 | [工作准备与验收文件](references/contract.md#工作准备与验收文件) |
| 用户要求检查或更新本技能，或这是专门的维护回合 | [安装与维护](references/maintenance.md) |

普通编码、审查和提交直接做当前任务。安装验收、专门维护或用户要求检查本技能时，再核对已安装版本以及官方有没有新版。需要更新且安装空闲时才运行 `sync --idle`。

改配置字段的含义与安全边界见[安装与维护](references/maintenance.md)；修改命令仍只在 [README 参数设置](https://github.com/LastDreamTeam/LDAI_CodeStyleAgentSkill#参数设置)。

## 硬规则

- 不发明提交、推送、合并或发布授权。用户当前已经明确的决定不再设闸。
- 先核目标仓库可见性。未知或查询失败不默认私有，不向未核目标推送。公开与私有格式见[提交规范](references/commit.md)。公开前须做隐私检查与脱敏。私有混合贡献首行使用 `##主人 + 模型：<已核身份> | <摘要>`，其中 `主人` 取独立配置的 `human_commit_name`。
- 改配置时，`human_name` 是人类注释标识，`human_commit_name` 是混合提交显示名，两者分开；修改命令仍只在 README 参数设置。
- 已被明确排除的项目保留已有资料，停止自动创建和维护共享记忆。在上述范围之外，也不接管他人仓库已有的 `Agentic/`。
- 普通 Agent 仅在有可核对的重复依据时，才剔除明显重复或做无损整合：同一条目标识、同一来源哈希，或当前摘要中已逐字重复的同一事实。依据不清、不能确定信息等价或有歧义时，直接忽略该整理并保留原文。**内容压缩**通常仅由专门获授权允许的审计/辅助模型执行，不能借去重删掉独立信息。已采用[区域历史](references/memory-history.md)的区域，授权区域维护者可在精选原文入库、读回核验和旧摘要保全后压缩该区三份摘要；README/人类资料及未采用区域不适用此例外。
- 不为消除眼前报错删引用、加替代桩或改插件原件来“拆东墙补西墙”。不把 Base/Agentic 当扩大权限的理由。配置改名不是修改已有人工注释的授权，更不是改变版权主体。
- 开发和验收文件只放项目目录或用户指定的项目工作区，不往桌面、系统目录或其他位置散放，见[工作准备与验收文件](references/contract.md#工作准备与验收文件)。
- 占用真实前台桌面时，用完、失败、取消或交接都立即归还鼠标和键盘，见[前台桌面操作用完立即释放](references/interaction.md#前台桌面操作用完立即释放)。
- 许可义务见 [许可分区](references/licensing.md)。更新本技能时使用原生管理器或 Git fast-forward，保留本地修改和私有配置。

## 共享记忆要点

适用仓库默认执行以下规则，读写范围跟随当前任务。细则见[目录共享上下文](references/directory-context.md)。

- 记忆跟随所属 **README 所在区域**及其明确声明，物理放在对应 `Agentic/`，**不扩大权限**。**README原有职责与权威索引**保持不变。每份文件头部须自足说明用途与边界，让**未安装本技能**的 Agent 也能理解。
- **平时（任务中顺手做）**：记东西就放在所属目录的 README/Agentic 里。一条坑记在出事那块目录自己的 README/Agentic 里。**打扫**是不定期的专门整理，不是每次任务；做不完记一句“还差哪些”。
- **致命级例外优先**：死机、崩溃、掉数据、工程/存档损坏，要往外挪到「凡是动这块东西的人都得先看」的那一份文件（含它的索引）；XR 就是 XR 那套文件里最外面的那一份，不是项目根，也不是只留在出事那个子目录。条目标注「死机级」，带触发条件和一手证据（版本/提交）。
- **复发缺陷**要沉淀有效修复经验：尤其 Git 曾修过时，核旧提交后，在已验证修复后更新正确关联层级的 DEBUG/MEMORY 同类条目。阶段性/番茄切片已成功验证即可记录。见[修复经验闭环](references/directory-context.md#复发缺陷的修复经验闭环)。
- 推送后回读远端准确提交，按本区域 DEBUG 实际尝试受影响业务流程；合并后核合并结果并对新版本再测。未合并或没有加载目标版本时保留未验状态。

## 合并请求的技术审查

采用本技能的项目，代码层面的技术判定默认归本技能管。人类当前明确指令优先，其次是项目 `AGENTS.md` 和区域 `README.md` 的约定，其余按本技能默认规则。项目可自行规定参与者是否必须安装技能。未安装的审查者也按项目采用的同一份公开判据审查，安装状态不改变结论。

1. **确定影响范围。** 从此次改动的真实入口沿调用链核直接依赖与受影响调用者。顺带发现的无关问题单列一句，技术结论仅针对本次影响范围，无需全仓审计。见[修改、迁移与验证](references/contract.md#修改迁移与验证)。
2. **核对适用的原判据。** 按项目采用范围逐项查原文。
   - 对照[模块结构与控制边界](references/contract.md#模块结构与控制边界)和[插件改写约定](references/contract.md#插件纯净与必要改写)，检查配对接口、Base 扩展面、命名空间与插件边界。遇到超出授权、需要裁决的接口或 Base 变更，将该项交给人类或项目已授权的架构负责人。
   - 对照[序列化与 Inspector 暴露面](references/contract.md#cinspector-与文档)核变更的必要性与兼容性。按[强制注释验收](references/comments.md#执行委派与提交验收)检查改动函数的有效头部文档和核心原理旁的行注释，按[代码格式整理](references/contract.md#代码格式整理)检查是否只整理改动范围。
   - 触及共享记忆时按[读取、更新和权限](references/directory-context.md#读取更新和权限)核真实增量和旧正文保全。按[提交消息的格式](references/commit.md#格式与工具)核提交及贡献归属，不能把审查者记成实现者。
3. **亲自运行项目已有且适用的门禁。** 在待审提交上实跑语法检查、项目编译、测试和文档契约测试，按影响范围实测可运行入口及实际效果。不能凭作者自述签字放行。分别记录被测提交、运行结果、未验项及原因，编译通过不能代替效果验收。
4. **给出技术结论和缺口清单。** 写明哪条判据受影响、证据在哪、还需谁裁决。审查默认只出意见，不顺手改作者代码。确需修改时，在授权范围内另起改动，用自己的提交身份署名。自审不算独立复审，技术通过仅回答该版本是否满足适用判据。是否合并由人决定。合并动作、快进或压缩等方式，以及合并前后如何读回核验，归执行侧发布与流程规范。何时提交材料、何时可考虑合并见[分支与两次合并请求](references/branch-workflow.md)。

本节暂定。遇到判据分歧，先在本项目的 PR/Issue 或所属区域记忆里保留原审查、分歧和处理依据。通用经验经脱敏并获授权对外分享后，在[审查规则议题 #27](https://github.com/LastDreamTeam/LDAI_CodeStyleAgentSkill/issues/27)追加可公开的案例与依据，保留原文。私有项目记录留在原可见范围内。上游根据实际案例补充入口，判据仍在各自原章节维护。

## 流程与验收

编写或审查已采用源码、以及 Unity 编译和效果验收，按[协作契约](references/contract.md#修改迁移与验证)执行。提交前核可见性、格式、验证边界和隐私脱敏。

向人类交付时优先说办好没有、有什么变化、还差什么，默认只报结果，按需给真实对照或证据入口，见[给人类的最终回执](references/interaction.md#给人类的最终回执)。任务结束时按[Issue 收尾](references/branch-workflow.md#任务范围内的-issue-必须收尾)复核范围内的 Issue：先核验、再勾选，完整完成且有权限才关闭，不扫无关单。验收文件的入口放在项目目录内，见[工作准备与验收文件](references/contract.md#工作准备与验收文件)。

## 常见误用

- 源码注释、格式与归属适用于所有参与维护的仓库。按目标可见性使用提交规则，按项目结构使用 Unity/OOP 规则。
- 分支审查、共享记忆和架构规则随任务读取。在范围外的他人仓库，保留其原有流程和资料。
- 不把接口全锁死，也不把 Base/Agentic 当扩大权限的理由。
- 配置改名不是修改已有人工注释的授权，更不是改变版权主体。
