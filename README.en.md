# LDAI CodeStyle Agent Skill

The coding and review conventions used by LastDream / LastDreamTeam. Maintainers record design decisions in interfaces and module READMEs. Agents implement against those decisions, verify affected workflows, and leave a record that the next maintainer can use.

**Source version 0.7.1** · [Latest release and downloads](https://github.com/LastDreamTeam/LDAI_CodeStyleAgentSkill/releases/latest) · [Changelog](CHANGELOG.md) · [简体中文](README.md)

[![Skill validation on main](https://github.com/LastDreamTeam/LDAI_CodeStyleAgentSkill/actions/workflows/validate.yml/badge.svg?branch=main)](https://github.com/LastDreamTeam/LDAI_CodeStyleAgentSkill/actions/workflows/validate.yml?query=branch%3Amain)

## Quick start

Give this instruction to your agent:

```text
Read https://github.com/LastDreamTeam/LDAI_CodeStyleAgentSkill/blob/main/skills/install.md and install the complete ld-codestyle-online skill for this host. Verify that the host discovers the skill and report the installed version.
```

Use a host that supports skills. The helper scripts require Python 3.10 or later. The Git installation also requires local Git. Existing installations can retain their settings when upgraded. [Installation guide](skills/install.md)

## Everyday use

Start with the module README and open references as the task calls for them. When changing code, read the local architecture, comments, and shared-memory conventions. When preparing a commit or PR, read the corresponding review and attribution rules. Version checks belong to installation, maintenance, or an explicit request. [Skill entry](skills/ld-codestyle-online/SKILL.md)

**Prefer the local account by default.** Local commits use the Git author and email configured for the repository. Pushes, PRs, and Issues use the local account authorized for the target host. Use an email approved for publication in public commits. Save a standing opt-out only when an owner explicitly requests it, and only for that owner. An account specified for one operation applies to that operation. [Local account policy](skills/ld-codestyle-online/references/commit.md#本地账号优先)

## Scope and evidence

The rules apply to repositories where we are an owner, member, or collaborator, including public repositories and small scripts. When the role is unclear, the current Git account’s merge permission on the target repository is sufficient to establish scope. Project rules and the user’s instructions govern the work.

| Task | What to check | Guide |
| --- | --- | --- |
| Change or review code | Document changed functions and explain the reason behind consequential choices. Follow the project’s existing architecture and plugin boundaries. | [Comments](skills/ld-codestyle-online/references/comments.md) · [Architecture](skills/ld-codestyle-online/references/contract.md) |
| Resume a module | Follow its README to the local `Agentic/` records. A module may declare an optional local SQLite history. Shared Markdown memory is enabled by default in the applicable repository. | [Shared context](skills/ld-codestyle-online/references/directory-context.md) |
| Commit or open a PR | A public commit uses a summary, a blank line, `##问题：` with the problem and impact, a blank line, and `##解决：` with the change, reason, and verification. Private commits use the applicable identity header. | [Commits](skills/ld-codestyle-online/references/commit.md) · [Branches and PRs](skills/ld-codestyle-online/references/branch-workflow.md) |
| Verify and hand off | Reproduce the user workflow, report what changed, and identify anything still unverified. | [Reporting results](skills/ld-codestyle-online/references/interaction.md) |

The [illustrated walkthrough](README.md#使用前后会有什么不同) compares two C# implementations. Adding documentation preserves timing values, including a negative pre-roll. Pairing event subscription with cleanup reduces four callbacks to one after repeated enable/disable cycles in the test fixture. The [handoff diagram](README.md#模块交接图) shows where the next agent finds decisions and regression steps.

[Detailed manual in Chinese](README.md#详细手册) · [Repository verification notes](Agentic/DEBUG.md) · [Contributing](CONTRIBUTING.md) · [License](LICENSE)
