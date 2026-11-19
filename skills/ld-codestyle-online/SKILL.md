---
name: ld-codestyle-online
description: "Use LD/LastDreamTeam rules when writing, reviewing or committing in repositories where we are an owner, member or collaborator. If our role is unclear, merge permission for the current Git account on the target repository is sufficient. Load references as needed for comments, shared memory, architecture, branches, PRs, Issues, README files and reporting results."
version: 0.7.1
author: "LD (LastDream / 最后的梦), Hermes Agent"
license: "CC-BY-SA-4.0; scripts: AGPL-3.0-only"
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [unity, governance, human-agent, codestyle]
---
> **来源标记**：AI 自建 · 人类设计：LD · 整理实现：列克星敦 · 2026-09-28

# LD CodeStyle Online

让人类用 Markdown、自然语言和小而清楚的代码契约表达设计，Agent 承接实现与验证。这是 LastDream / LastDreamTeam 的组织内部规范，基于 LD v6 实践，独立版本 **0.7.1**。主动使用本技能即表示了解这套规范并自行负责。

## 何时启用

我们作为主人、成员或合作者参与的仓库直接适用，不限归属、公开性、项目规模、引擎或语言。角色不确定时，当前 Git 账号对目标仓库有合并权限即可使用，无需每次查权限。没有参与关系且无合并权限的他人仓库不接管。

1. **提交身份是全仓库规则**。公开默认首行只写摘要，正文写清问题和解决办法；主人可明确要求公开名称。私有提交保留准确的 Bot/Agent 身份。可见性未知时不向未核目标推送，公开前审查隐私。
2. **共享记忆在适用仓库默认启用**。所属 README 所在区域确定范围，README 指向本区的 `Agentic/USER.md`、`Agentic/MEMORY.md`、`Agentic/DEBUG.md`。只读任务按需读取，写任务在触及区域维护有来源的内容，首次需要时补齐入口。
3. 日常无需配置或查询黑名单。已有明确排除继续有效，保留该项目已有资料。需要核实或调整例外时才用[项目范围工具](references/memory-scope.md#cli-与生效判定)。
4. **源码风格适用于适用仓库的一方代码，不论是否Unity。** 强制保留改动函数的头部文档、核心原理旁的注释和已有人工归属。按用户当次明确要求、`AGENTS.md` 和区域 README 核结构；`LD:`、`I<类型>Base`、`.Agentic` 是线索，不能仅凭目录、fork 或孤立标记判定。配对 Base、Model/Manager/ViewModel/View 随实际架构执行。Unity 专属规则要求同时存在 `Assets/` 和 `ProjectSettings/ProjectVersion.txt`。
5. **协作流程与写作约定**适用于上述仓库。项目未声明流程时采用[分支与两次合并请求](references/branch-workflow.md)。在主分支开始改动、提出 PR 或合并时再读。当前明确指令与项目已有约定优先。记忆、源码与流程规则均不扩大权限，生成代码和第三方插件仍按原边界处理。

## 按需阅读

每行对应实际任务。普通编码沿源码、当前责任区记忆及适配的架构入口开展。

| 当前任务 | 阅读入口 |
|---|---|
| 编写或审查一方源码 | [函数文档与强制注释](references/comments.md)、[注释归属](references/comments.md#注释归属)、[局部格式整理](references/contract.md#代码格式整理)、[插件边界](references/contract.md#插件纯净与必要改写) |
| 触及架构、引擎或资产 | [模块控制边界](references/contract.md#模块结构与控制边界)、[Unity Inspector 与序列化](references/contract.md#cinspector-与文档)；UE、Cocos、Godot 等按[引擎实际路径](references/memory-scope.md#模块目录怎样适配)与已有结构处理 |
| 读取、记录或整理区域记忆 | [目录共享上下文](references/directory-context.md)；责任区明确采用 SQLite 精选历史时读[区域历史](references/memory-history.md) |
| 提交、推送或核公开资料 | [提交规范](references/commit.md)、[默认推送边界](references/commit.md#默认提交与推送边界完整复现更新)；无法安全决定时见[推送前求助](references/interaction.md#推送前无法安全决策时的求助) |
| 对 PR 做技术审查 | [合并请求的技术审查](references/pr-review.md) |
| 写 Issue 或根 README，或收尾任务内的 Issue | [公开写作](references/public-writing.md)、[先核验、再勾选、后关闭](references/branch-workflow.md#任务范围内的-issue-必须收尾) |
| 向人询问、交付结果或操作前台桌面 | [交互与最终回执](references/interaction.md#给人类的最终回执)、[前台桌面立即释放](references/interaction.md#前台桌面操作用完立即释放) |
| 准备验收页、截图、日志或构建 | [工作准备与验收文件](references/contract.md#工作准备与验收文件)，交付入口放项目目录或用户指定的项目工作区 |
| 安装验收、专门维护或用户要求检查技能 | [安装与维护](references/maintenance.md)、[许可分区](references/licensing.md)；配置命令见 [README 参数设置](https://github.com/LastDreamTeam/LDAI_CodeStyleAgentSkill#参数设置) |

## 硬规则

- Codex、Cursor、DSH 等宿主默认沿用本地 Git 作者和本地 GitHub 账号。只有本地确实缺少账号且用户未禁用连接器时，才用连接器办理已授权的远端操作。账号选择、隐私和按主人保留的例外见[本地账号优先](references/commit.md#本地账号优先)。
- 私有混合贡献使用 `##主人 + 模型：<已核身份> | <摘要>`；`human_commit_name` 是混合提交显示名，`human_name` 是人类注释标识。配置改名不改变版权主体，也不授权修改人工注释。
- 开发和验收文件留在项目工作区。前台桌面用完、失败、取消或交接都立即归还鼠标和键盘。提交、推送、合并和发布须有相应授权；用户已明确的决定无需再次批准。
- 普通编码、审查和提交无需检查或更新本技能。安装需核版本；维护时支持原生管理器或 Git fast-forward，保留本地修改和私有配置，需要更新且安装空闲才用 `sync --idle`。

## 共享记忆要点

平时记录在所属 README/Agentic，打扫另行处理；README原有职责与权威索引保持不变。每份文件头部须让未安装本技能的人也能确定用途与边界。致命级故障优先记录在相关人员必读处，附触发条件和证据，见[记在哪里](references/directory-context.md#记在哪里)。去重、整合或压缩前核对[权限与依据](references/directory-context.md#去重整合与内容压缩的权限)。

复发缺陷按[已验证修复的记录方法](references/directory-context.md#复发缺陷的修复经验闭环)回核旧提交并更新 DEBUG/MEMORY。推送后与合并后都在准确版本按区域 DEBUG [复测业务流程](references/directory-context.md#推送后与合并后的回归)，未验项保留未验状态。

## 合并请求的技术审查

审查 PR 时按[技术审查判据、实测与结论](references/pr-review.md)执行。

## 流程与验收

按[协作契约](references/contract.md#修改迁移与验证)核改动范围、真实依赖、编译与效果。回执默认只报结果、缺口和必要的验收入口。任务内的 Issue 核验后再勾选，完整完成且有权限才关闭。

## 常见误用

不把 Base/Agentic 当扩大权限的理由，不为消除报错删引用、加替代桩或改插件原件。技术栈轻量不豁免记忆、注释、分支或已适配的架构规则。
