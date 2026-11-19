# LDAI CodeStyle Agent Skill

[简体中文](README.md)

Use this skill to keep LastDream’s coding conventions when handing implementation to an agent. The maintainer sets the interfaces and design intent, checks the result, and can take over the implementation. It gives people and agents shared rules, Markdown templates and small Python tools.

For example, when fixing repeated event callbacks, an agent traces who subscribes and unsubscribes, exercises repeated enable/disable cycles, and records the result where the next maintainer can find it. The [worked examples](README.md#使用前后会有什么不同) include the code and measured results for a small C# fixture. Project-specific behavior needs its own test.

## Quick start

Use an agent host that supports local skills or its own skill manager, with terminal and network access. The helpers require Python 3.10 or later. The Git installation route also requires Git. Give your agent this instruction:

> Read https://github.com/LastDreamTeam/LDAI_CodeStyleAgentSkill/blob/main/skills/install.md and install `ld-codestyle-online` for this agent. Verify the host discovers the complete skill and report its installed version and update status.

The [installation guide](skills/install.md) includes host-specific commands. Once installed, try “Read the module README, find the current decision, and rerun the relevant user workflow. Tell me what you verified.” The [skill entry](skills/ld-codestyle-online/SKILL.md) links the rules and tools.

## Scope and evidence

Commit attribution applies across repositories. Public commits default to a summary-only first line, with no `##模型：` identity section; private commits still require an accurate identity header. Shared Markdown memory is on by default for heavy production engines (Unity, Unreal, Cocos, Godot and similar) and off by default for Web, Vue, Node.js, PHP, TypeScript, Python and no-engine projects, unless the project already has Agentic memory files, its AGENTS.md or README adopts shared memory, or the user asks to enable it. Existing memory files continue to be maintained. An explicit blacklist still excludes even heavy-engine projects. LD source style (function header docs, in-place rationale comments, provider-tagged AI comments, scoped formatting, plugin isolation) applies in LD/LastDreamTeam first-party repositories, in projects that declare adoption, and on explicit request, regardless of engine. Unity and object-oriented structure rules (paired `I<Type>Base` interfaces, `.Agentic` layers, Inspector tooltips) apply only where that structure is adopted. From 0.7.0 the skill entry is a short index: load comment, memory, branch and engine rules only when the current task needs them, and do not start a coding task with the maintenance script. Heavy-engine projects still default to the branch and two-phase merge flow when the project has no rule of its own; light projects need not ask before every small main-branch fix. A project's own rules and the user's current instruction take precedence, and they grant no extra push or merge authority.

Find the latest package in [Releases](https://github.com/LastDreamTeam/LDAI_CodeStyleAgentSkill/releases), behavior changes in the [changelog](CHANGELOG.md), and repeatable checks and limitations in the [verification notes](Agentic/DEBUG.md). See [contributing](CONTRIBUTING.md) for the review process and [LICENSE](LICENSE) for the documentation and code licenses.
