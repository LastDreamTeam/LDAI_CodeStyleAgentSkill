# LDAI CodeStyle Agent Skill

[简体中文](README.md)

Use this skill to keep LastDream’s coding conventions when handing implementation to an agent. The maintainer sets the interfaces and design intent, checks the result, and can take over the implementation. It gives people and agents shared rules, Markdown templates and small Python tools.

For example, when fixing repeated event callbacks, an agent traces who subscribes and unsubscribes, exercises repeated enable/disable cycles, and records the result where the next maintainer can find it. The [worked examples](README.md#使用前后会有什么不同) include the code and measured results for a small C# fixture. Project-specific behavior needs its own test.

## Quick start

Use an agent host that supports local skills or its own skill manager, with terminal and network access. The helpers require Python 3.10 or later. The Git installation route also requires Git. Give your agent this instruction:

> Read https://github.com/LastDreamTeam/LDAI_CodeStyleAgentSkill/blob/main/skills/install.md and install `ld-codestyle-online` for this agent. Verify the host discovers the complete skill and report its installed version and update status.

The [installation guide](skills/install.md) includes host-specific commands. Once installed, try “Read the module README, find the current decision, and rerun the relevant user workflow. Tell me what you verified.” The [skill entry](skills/ld-codestyle-online/SKILL.md) links the rules and tools.

## Scope and evidence

Commit attribution applies across repositories. A public commit starts with the change summary, a blank line, `##问题：` describing the problem and its impact, another blank line, and `##解决：` explaining what changed, why, and how it was verified. Public messages and shared-memory change records omit the `##模型：` identity by default. Use the approved public Git author and committer names and emails. Private commits require an accurate identity header.

This is a private working standard for LastDream / LastDreamTeam. Anyone who chooses to use it accepts responsibility for applying it. Use it directly when we own the target repository or participate as a member or collaborator, including public and lightweight projects under other owners. If the role is unclear, merge permission for the current Git account on the target repository is sufficient. Known permissions need no recurring check. Leave unrelated repositories and their existing memory files to their maintainers.

Shared Markdown memory is enabled by default. Everyday work requires no blacklist setup or lookup. An existing explicit exclusion still stops automatic maintenance of that project’s memory. The regional README indexes Agentic records. Coding tasks follow the relevant comment, architecture, commit, branch and review rules. Use the project’s actual structure for Unity and OOP conventions. The default branch and two-phase merge flow applies when the project has no rule of its own. User instructions and project rules take precedence, and merge permission does not authorize a particular merge.

Read the references needed for the current task. Check the skill version during installation, scheduled maintenance or on request. Coding, review and commit tasks can proceed without an update check.

Find the latest package in [Releases](https://github.com/LastDreamTeam/LDAI_CodeStyleAgentSkill/releases), behavior changes in the [changelog](CHANGELOG.md), and repeatable checks and limitations in the [verification notes](Agentic/DEBUG.md). See [contributing](CONTRIBUTING.md) for the review process and [LICENSE](LICENSE) for the documentation and code licenses.
