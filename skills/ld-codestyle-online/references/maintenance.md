# 安装、配置与检查/更新

首次安装请把[给 Agent 的安装说明](https://github.com/LastDreamTeam/LDAI_CodeStyleAgentSkill/blob/main/skills/install.md)交给当前 Agent；它须完成环境识别、完整技能接入、实际检查及宿主发现验证，不只复制文档。

需要 Python 3.10+；Git 克隆更新另需 Git，Hermes 安装使用当前环境的 `hermes` 命令。没有 Python 时规范仍可阅读，但脚本未运行就不能声称已自动检查或更新。

维护与交互CLI的机器stdout使用ASCII转义JSON；调用方先解析JSON再显示中文等Unicode值，不把转义文本当数据丢失。磁盘配置与HTTP仍为UTF-8，此输出约定避免Windows传统代码页破坏管道传输。

命令在本技能目录运行；通过 Agent 的终端工具调用（Hermes 使用 `terminal`）。Windows 若只有 Python Launcher，可用 `py -3` 替换 `python`，先确认其版本。

```sh
python -B scripts/maintain.py show
python -B scripts/maintain.py check
python -B scripts/maintain.py sync --idle
python -B scripts/maintain.py health
```

可修改参数的命令集中在[README 参数设置](https://github.com/LastDreamTeam/LDAI_CodeStyleAgentSkill#参数设置)，这里仅说明读取、维护和安全行为。数据根等全局参数位于子命令之前，须与该安装已有调用方式一致。

- `show`：读/初始化该实例配置，显示实际数据位置、`effective_interval_days=1` 与离线重算的 `health`，无网络。安装清单尚不存在时仍可管理偏好，但健康为 `unknown` 且 `dirty=true`。
- `interaction`是同一配置内的可选交互偏好，`show`同时显示真实`config_path`及解析后的开关、回答等待、可选空闲阈值。旧schema-1缺新字段沿默认且不丢旧值，非法类型/值拒绝写入。字段语义和命令见README；路由/超时续行见[交互规范](interaction.md)。当前HTML辅助不采全局键鼠，保存空闲阈值不等于开启监控；该偏好不是宿主审批或无人值守授权。
- `human_name` 是人类注释标识，默认 `LD`；`human_commit_name` 是混合提交显示名，默认 `主人`。它们是独立偏好，不改技能正文、项目注释或 Git 身份；值约束和修改方式见 README。
- `check`：只查官方 `main` 的版本清单，不更新技能。每个安装实例**每24小时最多联网检查一次，包含失败尝试**；`check --force` 兼容保留，但不能绕过此上限。未到期返回 `not_due` 和缓存状态。即使 `auto_update=true`，此命令也只检查。
- `sync --idle`：执行相同的每日检查与更新策略。新安装默认 `auto_update=true`，新鲜缓存表明版本落后时，在安全空档直接调用受支持的后端；当天先 `check` 或忙时 `sync`，随后空闲再 `sync --idle`，可以复用缓存更新，无须等下一天、也不重新查版本。
- 已有 `auto_update=false` 保留为关闭；有新版且刚完成检查时返回 `update_confirmation_required`，同日重复返回 `not_due` 避免反复催问。`sync --idle --approve-update` **只在用户明确同意本次更新后**使用，不改变长期开关；更新成功后关闭偏好仍使健康为脏。
- **迁移不猜偏好来源**：旧 schema-1 中的显式 `false` 无法区分旧默认和用户主动关闭，因此保留，并在健康说明中提示可以显式开启。缺少 `auto_update` 才补新默认 `true`；缺少 `human_commit_name` 补“主人”。保留人类标识、其他未知偏好及合法旧 `interval_days` 原值，实际周期固定为每日，`effective_interval_days=1`。新设置周期只接受 `1`；非法旧类型/值拒绝，不静默重置。参数修改命令见 README。
- `--idle` 是调用方确认此安装未被业务任务占用，不自动探测所有 CLI/桌面会话。无空档返回 `deferred_until_idle`。更新后重新读 SKILL.md，新任务采用新规则；运行中的任务不切换。
- 更新后端有独立的**每24小时最多一次尝试**上限，失败也记录，未到期返回 `update_retry_not_due`；`--force` 不能越过检查或后端上限、不授予同意，也不覆盖本地修改、换分支、改变来源或突破原生门禁。时钟倒退按未到期处理，不能借此密集重试。
- “一次联网检查”指官方版本清单请求。一次维护轮次还可能调用 Git fetch 或原生下载后端，不宣称整个更新过程只有一个物理网络请求；缓存检查和安装后端的节流分别持久化。

## 离线健康与依赖方门禁

`health` **不联网、不更新技能**，从磁盘实际版本清单、配置和检查状态重算，原子保存到该实例的 `health.json`，并向 stdout 返回标准 JSON。`show`、`config`、`check`、`sync` 同样在持锁期间刷新快照，业务结果中的 `health` 是同一结构；检查/更新异常也尽量持久化当前事实。锁冲突或无法写盘时返回错误和非健康信息，不能宣称新快照已保存，也不抢锁覆盖其他进程。

健康是机器可查的事实报告，不是全局封禁：普通 `health` 对 `dirty`/`unknown` 返回0，依赖方按自身要求选择门禁：

```sh
python -B scripts/maintain.py health --require-healthy
python -B scripts/maintain.py health --min-version 0.5.0
python -B scripts/maintain.py health --require-version 0.5.0 --require-healthy
```

| 字段 | 含义 |
|---|---|
| `schema_version`、`skill` | 健康协议版本，当前为1；稳定技能标识。独立于偏好schema和技能版本。 |
| `installed_version`、`latest_version` | 实际磁盘版本与最近成功检查获知的官方版本；未知为null，不使用旧安装收据冒充当前版本。 |
| `auto_update`、`dirty`、`status` | 配置开关（无法读取为null）；有未满足条件即 `dirty=true`；`status` 为 `healthy`、`dirty` 或 `unknown`。 |
| `reasons`、`notes` | 稳定原因代码数组与迁移说明。关闭更新和版本落后任一成立都标脏。 |
| `checked_at`、`last_attempt_at` | 最近成功检查与最近检查尝试的Unix秒时间；失败只推进尝试时间。 |
| `freshness`、`age_seconds`、`expires_at` | `fresh`/`stale`/`unknown`、成功证据年龄、24小时到期时间；未知时间为null。 |
| `evaluated_at`、`effective_interval_days`、`health_path` | 本次离线评估时间、实际每日周期、快照真实路径。 |
| `check_error`、`update_error` | 最近失败类型或中断标记；无错误为null。 |

`auto_update_disabled` 与 `version_behind` 分别表达两个必要脏条件。首次未检查、缺失/非法版本、配置/状态损坏、检查过期、时钟倒退、检查/更新失败或中断同样不能报健康。对应代码包括 `check_unknown`、`latest_version_unknown`、`installed_version_unknown`、`config_invalid`、`state_invalid`、`check_stale`、`clock_rollback`、`check_failed`、`check_incomplete`、`update_failed`、`update_incomplete`；清单无法解析另有 `installed_manifest_invalid`。失败不会覆盖旧成功时间或删除有效诊断，更新部分写入后失败会回读真实磁盘版本并保留脏状态，不把版本相等当作完整更新成功。

健康快照不会自己计时改写。直接读 `health.json` 的依赖方必须核schema、`evaluated_at`/`expires_at`和字段有效性；过期、无法读取或未知一律按不满足健康处理。需要当前判断时使用 `health --require-healthy`，不能长期缓存曾经的 `dirty=false`。`health` 只生成报告，不修复损坏的 `config.json`/`state.json`。

| 退出码 | 依赖方可采用的含义 |
|---|---|
| `0` | 报告成功；如果选择了门禁，其约束均通过。未选择健康门禁时不代表健康。 |
| `1` | I/O、锁、配置命令或版本参数值等执行/验证错误。 |
| `2` | argparse命令语法错误，例如未知选项或互斥参数。 |
| `3` | 显式选择 `--require-healthy`，但健康不满足。 |
| `4` | 显式版本要求不满足或安装版本未知。组合门禁时优先于3。 |

版本要求只检查已安装版本：`--min-version` 为三段稳定版本下限，`--require-version` 为精确版本；二者可组合，并可与 `--require-healthy` 组合要求新鲜健康证据。门禁退出码作为CLI响应的 `gate_exit_code` 返回，不把某个依赖方的选择写进共享健康快照。技能不会自动将这些门禁安装到其他项目、hook或所有Agent入口。

## 更新后端

1. **Hermes 原生安装**：核该安装所属 profile 的 `.hub/lock.json`，技能名、精确来源标识、官方 GitHub 固定 SHA URL 和安装路径必须吻合。兼容原生记录为 `github` 或 `skills.sh` / `skills-sh` 的同一官方目录，不接受任意同名来源。只调用 `hermes skills update ld-codestyle-online`，不加原生 `--force`。继承原生扫描和本地改动保护，再回读版本，不能因为退出码为零就报已更新。
2. **独立 Git 克隆**：技能须位于仓库的 `skills/ld-codestyle-online`，`origin` 必须是本项目官方 HTTPS 地址，分支须为 `main` 且无本地修改/未跟踪文件。fetch 后检查忽略文件冲突、fast-forward 祖先关系并再次检查工作树，再备份并执行 `merge --ff-only --no-overwrite-ignore`。不 stash/reset/clean，不强推，不改远端，不更新业务工程。
3. 手动文件拷贝、其他管理器或固定 tag/开发分支：可以读规范/配置/查版本，但不会擅自重装或自动转换管理方式。需用该产品正式更新入口或改成独立克隆后再接入。

检查请求有 10 秒网络超时；单条后端命令有 120 秒上限。更新失败不自动循环重试；保留快照、记录更新阶段错误并回读磁盘实际版本，不冒称已经回滚或原文件一定未变。后续人工/Agent 核原因，在后端尝试满24小时、更新授权仍有效且安装空闲时再同步；`--force` 不能缩短重试间隔。版本被钉住、存在脏修改、来源不匹配或配置损坏时，明确报错而非自动“修复”。

## 仓库更名兼容

正式仓库为 `LastDreamTeam/LDAI_CodeStyleAgentSkill`；唯一旧名 `LastDreamTeam/LDCodeStyleAgentSkill` 仅用于已有安装兼容。新链接、克隆和版本检查使用正式地址，技能名与配置schema仍保持不变。

- **旧Git安装**：保留原安装路径和数据根，旧版脚本可经GitHub现有更名重定向发现并获取新版；新版同时识别精确的新旧官方HTTPS origin，不自动改远端。重定向不可用时先核官方仓库身份和当前配置，再在用户授权下修正原origin，不移动目录或重建配置来绕过失败。
- **旧Hermes安装**：允许旧名称的原生登记与重定向后的新固定SHA地址组合；仍核来源类型、完整标识、SHA与安装路径，不接受fork、同名仓库、分支URL或相似域名。原生登记无需手工改写；由原生管理器管理更新。
- **首次升级前的旧脚本**若因登记已改新名而报来源不匹配，不改认证、不删登记、不放宽校验；检查真实登记后走该宿主原生的同名技能更新，按其本地修改/扫描/审批流程完成并回读版本。当前profile或审批不明时停止该更新，不另装第二份覆盖偏好。
- 新版本备份包含新增 `templates/`。偏好按原安装真实路径保留；克隆目录更名会改变实例标识，**不要为了跟仓库更名而改本地安装目录名**。
- 不能保证GitHub旧URL永远重定向；新用户一律走新入口。新版兼容旧标识不表示可以让旧名被他人重新占用后仍无条件信任，若仓库身份出现变化须停下核验。

## 数据位置、隔离与并发

按 `--data-root` → 可选 `LD_CODESTYLE_DATA_ROOT` → 已识别 Hermes profile 的 `skill-data` → 技能自身 `.ld-codestyle-data` 选择。外部共享根后追加技能名与**真实安装绝对路径摘要**，配置 schema 独立于技能版本。路径更换是新实例，不自动复制另一终端偏好；同一路径原地升级保留偏好。

Hermes 的原生更新会替换安装目录，因此它使用外部数据目录；显式给 Hermes 配置技能目录内数据时，拒绝更新，避免丢失。不要用全机单一 `human_name` 环境变量，也不修改 Agent 的配置/记忆/凭据。

状态写入用临时文件后原子替换；同一数据实例采用排他锁，重复调用立即失败，不无限等待。进程异常退出遗留 `maintenance.lock` 时，先核其中 PID 及是否有维护进程，再手工移走；不自动按时间抢锁。多个终端若故意共享真实安装，应统一数据根、单写者并协调任务空档；需不同版本则独立克隆。

更新前保存技能内容快照（不含配置和状态），每实例仅保留最近 **3** 份 `backups/snapshot-*.zip`，不上传仓库、不自动还原。配置损坏或 schema 未识别时停止，不用默认值覆盖原文件。备份是故障恢复材料，不是业务验收证明。

## 频率与调度的区别

相关任务采用技能时由 `SKILL.md` 指导调用维护入口：首次可立即检查，之后每24小时最多联网检查一次；失败同样计入。用户主动检查也遵守这个上限，未到期返回缓存及健康。普通脚本不调用模型 API，但 Agent 触发/理解结果仍属于该次会话的正常工作。

新安装默认每日并开启自动更新；旧的明确关闭保留。检查官方 `main` 的语义版本，而不是每次强拉所有提交。只有完整安装、支持的更新后端、可用网络/权限、有效更新授权和任务空档都具备时才更新；静态文件拷贝不能冒充自动更新接入。

**频率约束不是后台调度器。**相关任务触发由技能文档约定，脚本不会自行开系统服务、安装计划任务、创建cron或修改其他profile，也不会远程更新所有电脑。无人使用时不会自动启动；只有使用者另行明确接入已有调度机制，才会有独立于任务的调用，仍须协调安装占用和同一数据根。

## 验收分层

仓库测试验证真实临时 Git 仓库 fast-forward、本地修改保护、配置迁移、每日检查/更新节流、失败与中断健康、锁和备份，以及真实CLI进程的离线JSON/持久快照/可选门禁退出码。网络和更新后端替身只证明对应状态分支，不冒充公网或原生管理器可用。发布验收区分匿名公网下载/版本检查、原生 Hermes 安装以及产品集成，不将尝试安装写成安装成功。

当前 Hermes 安全扫描将脚本的子进程执行及环境传递标为 CAUTION，新社区源可能被阻止安装。这是实际集成门槛，不隐藏扫描项、不改写等价代码躲规则、不自行强制通过。需使用者按平台正式审批/信任流程处理；未获准前不写“原生安装已通过”。Windows/macOS、各款 CLI/桌面端的技能发现与调度仍需真实环境验证，不能从 Python 可跨平台推断产品集成已通过。
