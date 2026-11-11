# LDAI_CodeStyleAgentSkill

> **自用项目** · 本仓库主要供维护者自用。


**`ld-codestyle-online` —— LD 人类与 Agent 协作编程技能的 GitHub 持续更新版。**

LD = **LastDream · 最后的梦**。官网：[lastdream.net](https://lastdream.net)；B站：**最后的梦制作组**。

## 为什么做这个技能

我们希望探索一种更适合未来人类与 **Agent / SuperAI** 配合开发的方式：人类仍然可以通过熟悉的 **Markdown、自然语言、接口与必要的代码**，具体地表达自己的欲望、创意、设计与边界；Agent 则承担更多细节实现、验证和日常维护。

这不是让人类彻底无视代码，也不是把设计权交给黑箱。人类把重心更多放在“想要什么、为何需要、最终体验应该怎样”，同时保留理解、查看、调整和约束实现的入口。我们希望成果既能运行，也能被人读懂、接管和继续演进。

本技能将这种分工落实为可执行的工程约定：小而清楚的控制接口、可替换实现、就近的 Markdown 模块说明、可追溯注释归属，以及按仓库可见性区分的提交记录（私有保留强制准确身份，公开默认只保留 Bot 昵称或 Agent 模型名；两者保留问题和解决方式）。**这些约定服务于协作，不以制造更多抽象层、文档或审批为目的。**

## 当前阶段与适用范围

目前仍处于**持续迭代、研究与工程实践阶段**。规则的默认适用范围与实机验证范围分别说明，不将“已规定适用”当成“所有引擎均已验证”。本技能约束开发规范、习惯与风格，不能替代测试、审查和必要的人类判断。

**从0.5.0起按三层应用，不能再用“非Unity项目”整体跳过技能：**

- **提交身份覆盖一切仓库**，与引擎、开发语言、项目规模和共享记忆开关无关。私有强制准确Bot/Agent身份；public默认简化且主人可以定制。
- **共享Markdown记忆默认覆盖一切项目**。Unity、UE/Unreal、Cocos、Godot等重型游戏开发/生产工业引擎项目，只要当前宿主存在本技能就强制应用。Web/H5、Vue、Node.js、PHP、TypeScript、Python及无底层引擎项目也默认开启，采用明确排除的黑名单，不能因轻量或非Unity自行跳过。主人明确要求不使用共享记忆时，才在本机环境变量中按真实项目根记录排除；详见下方跨项目规则。
- **其余源码风格与Unity/OOP规则独立判断**。已经采用LD开发约定的Unity项目应用相应治理；其他项目对源码架构、命名、注释、格式等按明确采用授权及适配范围执行。默认记忆与提交身份不等于自动采用所有源码规则，不要求制造Base接口、Unity目录、Inspector或无意义OOP层，也不自动启用所有区域的SQLite历史流程。
- 第三方插件、生成文件、序列化资产和现有公共契约有独立边界。技能不是改写它们的授权，也不能覆盖当前任务范围。插件优先项目侧扩展；确有必要的侵入改写须最小化、就地标记，并在插件目录外的必读入口登记清单，升级后按清单补回，见[插件纯净与必要改写](skills/ld-codestyle-online/references/contract.md#插件纯净与必要改写)。
- 本次新写和改动的代码按工程格式配置与周边风格整理，保持原编码与换行，不全文件重排未改动代码；整体格式化单独提交，见[代码格式整理](skills/ld-codestyle-online/references/contract.md#代码格式整理)。
- 原 `ld-codestyle-v6` 是首版的规范来源；在线版拥有自己的版本号。**同一任务只使用一份确定版本，不叠加旧版与在线版。**

## 跨项目共享Markdown记忆与项目黑名单

一方业务模块或责任区使用所属 `README.md` 声明范围、入口与同级关系，把 `MEMORY.md`、`USER.md`、`DEBUG.md` 等共享正文集中在相应 `Agentic/`。**物理放在Agentic，不意味着逻辑只管Agentic**；作用范围始终与README所声明区域同级。Unity的路径关系是参考，实际目录按当前引擎/语言映射，已有README职责与人工资料保持，不能硬套 `Assets/Core`。

| 项目类型 | 可采用的责任区示例（须以真实目录核实） |
|---|---|
| Unity | `Assets/<模块>/README.md` 与同区域 `Agentic/` |
| UE/Unreal、同类工业引擎 | 一方 `Source/<模块>/README.md` 与 `Agentic/`；资产区由其真实上层README单独声明 |
| Cocos、Godot | 一方功能/脚本目录的README与Agentic，遵循实际资源导入及元数据规则 |
| Web/H5、Vue、Node.js、TypeScript、PHP、Python | `src/<模块>`、实际包/服务/功能目录的README与Agentic，不依赖底层引擎或OOP |
| 小型脚本、无模块项目 | 项目根README与Agentic；以后有真实模块再分区，不先造空层 |

父README可以与受控模块目录同级、将正文放在模块的Agentic中，但必须写真实往返入口和排除项。读写仍限于当前任务触及的区域：只读任务按需读取，授权写任务才建立/更新有真实增量的文件；不全仓铺空模板，不接管第三方、生成目录或宿主私人记忆。文件头部、日期、用户原意、DEBUG回归和迁移保护仍遵循原共同记忆规范。详见[跨项目映射与排除协议](skills/ld-codestyle-online/references/memory-scope.md)。

黑名单只影响共享记忆的自动维护，**不关闭提交身份、秘密检查或版本健康规则**。环境变量 `LD_CODESTYLE_MEMORY_BLACKLIST` 保存当前计算机/用户的JSON绝对项目根列表，默认不存在或空列表即启用；解析并规范化真实根后完全匹配，不按字符串前缀误伤兄弟或独立子项目。无效配置报错，不能把坏值当成“未排除”。排除后保留既有资料，不能据此删除记忆或忽视已有人工约定。

从完整技能目录执行以下命令，只有主人明确要求排除/恢复的实际项目才运行修改命令：

```sh
python -B scripts/project_memory.py show --project-root "<真实项目根绝对路径>"
# 默认仅返回建议环境值，persisted=false；不能据此宣称已经设置
python -B scripts/project_memory.py exclude --project-root "<真实项目根绝对路径>" --owner-requested
# Windows当前用户环境持久化；不写项目文件、不修改其他环境变量
python -B scripts/project_memory.py exclude --project-root "<真实项目根绝对路径>" --owner-requested --persist-user
python -B scripts/project_memory.py include --project-root "<真实项目根绝对路径>" --owner-requested --persist-user
```

Windows读取当前用户持久环境值优先，避免运行中宿主继承旧环境导致恢复失效；其他系统由Agent沿已核实的宿主环境设置入口保存返回值，重新查询验证后才报告已生效。不自动改shell启动文件或全机设置，不把本机项目路径提交到仓库；仅运行建议命令不会修改父进程环境。

## 区域历史与有限记忆

三份Markdown只承载当前关键摘要；`Agentic/history.sqlite3`精选保留本责任区用户原话、已验证bug修复和踩坑经验的完整记录。按需查历史，不全库注入、不无限分卷。USER/MEMORY/DEBUG默认上限分别为 **4000/6000/6000 Unicode字符**（含头部/索引），是可调整的实现默认值，不是token或用户指定值；80%提示整理。先归档读验、保全旧修订再压缩，范围与隐私边界见[完整规范](skills/ld-codestyle-online/references/memory-history.md)。

下列命令从完整技能目录执行，需Python3.10+。将示例路径与值替换为真实授权区域；不是要求依次全跑，不创建真实项目示例数据：

```sh
python -B scripts/memory_history.py --area "<实际区域>/Agentic" init --readme "../README.md" --scope "<区域ID>" --description "<负责路径与排除项>" --visibility private
python -B scripts/memory_history.py --area "<实际区域>/Agentic" add --record "<已核精选记录.json>" --reviewed
python -B scripts/memory_history.py --area "<实际区域>/Agentic" search "<关键词>" --limit 10 --offset 0
# 类型与来源日期可组合筛选；此为合成日期示例，范围含首尾日，不按UTC换算
python -B scripts/memory_history.py --area "<实际区域>/Agentic" search --kind debug --from-date 2026-01-01 --to-date 2026-01-31 --limit 10
python -B scripts/memory_history.py --area "<实际区域>/Agentic" get "<记录ID>"
python -B scripts/memory_history.py --area "<实际区域>/Agentic" status
python -B scripts/memory_history.py --area "<实际区域>/Agentic" verify
# 只有明确要求调额才执行；不为绕过本次超额自行抬高
python -B scripts/memory_history.py --area "<实际区域>/Agentic" limits --user 4000 --memory 6000 --debug 6000
# status提供原文SHA；逐项核原意后提交候选，record-id可重复参数列多个真实来源
python -B scripts/memory_history.py --area "<实际区域>/Agentic" replace --file USER.md --candidate "<候选摘要.md>" --expected-sha256 "<原文SHA256>" --record-id "<来源ID>" --reviewed
python -B scripts/memory_history.py --area "<实际区域>/Agentic" snapshot "<replace返回的snapshot_id>"
# 显式核分享范围和脱敏后跨机交换，输出必须不存在；不直接合并SQLite二进制
python -B scripts/memory_history.py --area "<实际区域>/Agentic" export --output "<新交换包.json>" --reviewed
python -B scripts/memory_history.py --area "<实际区域>/Agentic" import --input "<已核交换包.json>" --reviewed
```

记录格式见[合成用户示例](skills/ld-codestyle-online/templates/history-user.example.json)和[合成Debug示例](skills/ld-codestyle-online/templates/history-debug.example.json)。`--reviewed`不是自动语义/隐私证明；不得照抄示例当真实原话或成功证据。缺库、损坏、超额、旧文漂移或锁冲突停止该项、不截尾。工具不会抓聊天、自动压缩、装后台任务或拦截其他编辑器；交付仍须核真实文件和语义。正式采用时为库及sidecar配置精确忽略/共享策略，勿把私密数据随Git公开。

日期/类型为独立SQL列并带索引；未知日期保留原值并投影为NULL。新库schema 2，旧库不自动原地改写，schema 1交换包可保全原文导入新库；准确格式、日期边界和迁移步骤见[日期与类型](skills/ld-codestyle-online/references/memory-history.md#日期与类型独立sql列和筛选)。

## 强制源码注释：平时写好，旧账另做打扫

- 平时，新写和改动的函数必须带有效头部文档，包括 private、构造函数、生命周期、测试和内部辅助；C# 等支持 XML 的位置用 XML，其他语言用有效原生文档。
- 核心原理实现位置必须有 `//` 或该语言等价行注释，说明原因、规则、约束和关键顺序；头部说明与实现旁解释不能互相替代，也不能用 README 代写。
- 旧代码缺注释、旧脚本没按新规另做不定期打扫，不摊到每个任务；可以分几次，做不完记一句“还差哪些”。未改动旧函数的注释缺口不阻断本次提交，保护人工、第三方和生成代码，不接管无关工程。
- 提交前核本次新写和改动的函数，缺失、空壳或失实的说明先补好，不能把本次缺项当成旧账；委派和主Agent复核同样执行，不冒称已有自动源码分析器。

完整定义、语言差异、旧项目范围与验收见[强制注释与专门打扫](skills/ld-codestyle-online/references/comments.md)。

## 安装

### 一句话交给你的 Agent

复制这句话给你正在使用的 Agent，普通获取、接入和验证由它完成：

```text
请阅读以下安装说明，为你当前的 Agent 环境安装 ld-codestyle-online，并验证主动检查更新可用：https://github.com/LastDreamTeam/LDAI_CodeStyleAgentSkill/blob/main/skills/install.md
```

**[打开 Agent 安装说明](skills/install.md)** · [纯文本入口](https://raw.githubusercontent.com/LastDreamTeam/LDAI_CodeStyleAgentSkill/main/skills/install.md)

仓库已从 `LastDreamTeam/LDCodeStyleAgentSkill` 更名；技能名仍为 `ld-codestyle-online`。新安装使用新地址，旧安装的原地升级与偏好保留见[更名迁移](skills/ld-codestyle-online/references/maintenance.md#仓库更名兼容)。不要求换安装目录，也不另装一个同名技能。

文档要求 Agent 识别当前宿主和作用域，获取官方最新版、安装完整技能、验证宿主发现及主动检查；不会替同一电脑上的其他 Agent 一起安装。Hermes 使用原生管理器；允许本地技能的其他宿主可用独立 Git 克隆＋本地目录/链接接入。只扔一份 `SKILL.md` 不算完整安装，也不会因此获得可用更新后端。

“一句话安装”是交互目标，不是绕过权限或兼容一切的承诺。需要有文件、终端和网络能力，且宿主允许该接入方式；审批/激活等确需人工的步骤由 Agent 明确报告。当前部分 Hermes 版本会以 CAUTION 拦截维护脚本，必须按平台正式审批，不能改走手工安装规避。各款 CLI/桌面端及 Windows/macOS 仍须各自实机验收。

## 更新与本地配置

**在线技能默认自动更新，强制检查仅在相关任务触发，每天最多一次：**

- 实际使用本技能、或执行依赖本技能的长任务时运行 `sync --idle`；长任务跨日时在下一个安全阶段再检查。**无关任务不触发**，技能没有独立运行能力，不会在闲置时自行检查。
- 版本清单联网检查以滚动24小时节流，失败也记录尝试时间；同日读缓存，不反复联网或打断。`check`只检查，`--force`也不突破每日检查上限。安装更新后端的fetch/下载属于应用新版，具有独立的每日重试限制。
- 新安装默认 `auto_update=true`；有新版、来源可靠且确认无任务占用时直接更新，无须逐次询问。运行中任务保留已读版本，阶段边界确认空档后再更新并重读，无法确认空闲则只查版本、延后更新。
- 主人明确关闭自动更新时立即保留该选择并**标脏**；**版本落后也独立标脏**。不健康不代表技能无法使用，依赖方可据自身业务要求阻止相关推送。网络错误、未检查和过期证据也不能当成健康。

检查脚本不调用模型 API。“最新版”指官方 `main` 通道发布的技能版本，不表示每次使用强拉每一笔提交。完整安装、支持的更新后端、可用网络/权限和安全空档仍是前提；不覆盖本地改动、不绕原生审批、不安装后台任务、cron或服务。无关终端不会被远程更新。

`health`无网络读取版本与健康状态，返回机器可读JSON并维护当前实例的 `health.json`。依赖方应调用CLI重新评估时间与实际磁盘版本，而不是永久缓存一个健康布尔值；可选择 `health --require-healthy --min-version 0.5.0` 或精确版本要求。健康输出是保险信号，不是加密认证，也没有替其他技能/插件自动安装推送门禁，字段与退出码见[维护与健康接口](skills/ld-codestyle-online/references/maintenance.md)。

旧配置的人类名、交互偏好和路径保留。已保存的 `auto_update=false` 无法可靠区分旧默认与主人明确拒绝，因此保留并标脏；恢复自动更新按下面参数命令显式开启，不能静默洗掉脏标记。旧 `interval_days` 值保留作兼容信息，0.5.0 的实际联网检查周期固定为1天。

本地数据包括人类注释标记（默认 `LD`）、混合 Commit 的人类显示名（默认 `主人`）、兼容周期值、自动更新开关（新安装默认开启）、尝试/成功时间及健康状态。数据位置选择顺序：

1. 调用方明确提供 `--data-root`（终端为技能分配的数据根目录）；
2. 可选的 `LD_CODESTYLE_DATA_ROOT` 环境变量；
3. 能确认所属 Hermes 安装时，使用该 profile 的 `skill-data`；
4. 其他情况退回技能自身的 `.ld-codestyle-data` 子目录。

前三种共享根下仍按**技能真实安装路径的标识**分隔，各终端、各克隆、各版本安装副本不会共用一个配置文件。原地升级保留同一实例的偏好；数据格式有独立 schema 版本。环境变量是覆盖入口，不是要求设置的全机公共状态。

更新保留这些偏好，不批量替换源码注释，不更改人格、记忆、凭据或业务项目。原有 `LD:` 和既有人工注释继续保护，原版权来源不得因配置改名而抹去。检查/更新运行方式见[维护说明](skills/ld-codestyle-online/references/maintenance.md)；**可修改参数的操作命令统一只放在下面这一节**。

## 参数设置

默认值无需填写；首次使用或以后都可以用自然语言让 Agent 修改。仅作用于当前技能安装实例，不顺带修改其他 Agent、人格称呼、Git 用户名或旧提交。

| 参数 | 默认值 | 作用 / 可对 Agent 说的话 |
|---|---|---|
| `human_name` | `LD` | 代码中的人类注释标识；“把这个技能的 LD 注释标识改为某某”。 |
| `human_commit_name` | `主人` | 混合 Commit 首行的人类显示名；“把这个技能提交里的主人改为褪色的梦”。不连带改动 `LD:`。 |
| `interval_days` | `1` | 兼容保存旧值；在线有效检查周期固定为1天，不能借旧值取消每日维护。 |
| `auto_update` | `true` | 默认自动更新；主人可要求关闭，关闭立即标脏，恢复后仍需核最新版本。 |
| `interaction.enabled` | `true` | 是否启用必要的交互询问；关闭不绕宿主审批，也不等于获准无人值守。 |
| `interaction.answer_wait_minutes` | `15` | 展示确认后等回答多久，1–1440整数分钟；“把这个终端的询问等待改为10分钟”。 |
| `interaction.idle_after_minutes` | `0` | 可选的输入空闲阈值，0关闭、1–1440分钟；只供有合法终端信号的宿主降打扰，**本机HTML辅助不监控键鼠**。 |

Agent 先运行 `show` 确认当前实例和原值，再仅修改用户明确要求的字段，随后回读。若只说“改人类名”且语境无法区分注释标识与提交显示名，只需简短确认指哪一个；日常称呼、示例和引述不是配置修改授权。不改源码注释、命名空间、品牌/版权来源，不搜索替换历史提交，也不修改全局 Git author/email。

以下命令从完整技能目录通过终端工具运行（使用实际可用的 Python 3.10+）；**按要求选用，不是让 Agent 按顺序全部执行**：

```sh
# 查看当前安装配置；修改后也用此命令回读
python -B scripts/maintain.py show

# 仅修改混合 Commit 中的人类显示名，LD 注释标识不变
python -B scripts/maintain.py config --human-commit-name "褪色的梦"

# 仅修改代码中的人类标识，不追改旧注释，也不改 Commit 显示名
python -B scripts/maintain.py config --human-name "你的标识"

# 兼容字段只接受每日值；旧值保留供追溯，实际维护始终每日节流
python -B scripts/maintain.py config --interval-days 1

# 新安装默认开启；主人明确要求关闭或恢复时才修改当前实例
python -B scripts/maintain.py config --auto-update on
python -B scripts/maintain.py config --auto-update off

# 必要询问开关与两个独立时长；仅按用户明确要求修改
python -B scripts/maintain.py config --interaction on
python -B scripts/maintain.py config --answer-wait-minutes 10
python -B scripts/maintain.py config --idle-after-minutes 15
```

人类注释标识接受1–40个字母/汉字/数字/下划线/短横线，不含冒号；提交显示名接受1–40个可见字符，不含换行、首尾空白及首行结构分隔符（`# | + : ： 【 】 [ ]`）。无效值拒绝写入，不截断或静默“修正”用户原值。旧配置缺少显示名时补为“主人”，其他偏好保持不变。

若宿主给此安装指定了数据根，每次调用都须在子命令前带同一 `--data-root`，例如 `python -B scripts/maintain.py --data-root "<实际数据根>" show`；环境变量仅是可选路径覆盖，不建议设置全机公共偏好。

`show`另显示实际`config_path`与解析后的`interaction`。旧配置没有新对象时沿默认且保留原值；显式修改才写入交互偏好，不重置其他设置。非法类型/越界时拒绝写入。每个安装实例可按终端调整，不改操作系统PATH；原地更新保留偏好。单次问题的等待覆盖不改长期值。

## 默认推送范围与最终求助

**默认只同步其他设备或干净检出能够完整复现本次更新所需的内容**，包括真实源码/资源/配置依赖、正式构建和测试脚本、必要文档；默认排除不必要的一次性调试脚本、实验副本、缓存、日志、转储、截图及中间产物。按用途和依赖判断，不按文件名或扩展名一刀切。仅有辅助价值而希望保留的材料，先说明理由并给方案询问；主人已经明确纳入则直接遵守，正常正式依赖无需再批。

Unity自动重新序列化中没有必要业务语义的差异不混入推送；实际场景/预制件/资源变化、导入和项目设置、版本迁移及 `.meta` / GUID 依赖必须完整。排除上传不等于删除本地文件，不擅自清除人工、来源不明或其他任务资料。提交前审查tracked/untracked/staged与diff；推送前审查全部待推送提交、中间版本和元数据，工作树干净不能证明历史干净。用干净检出验证相关正式流程，不以原现场通过冒称跨设备通过。完整示例与检查清单见[默认推送边界](skills/ld-codestyle-online/references/commit.md#默认提交与推送边界完整复现更新)。

**求助是尽力核查后的最后一步**：先查实际依赖、历史与业务要求，评估并在安全授权范围实测；仍不能自主作出安全可靠决定，尤其会较大改变业务行为时，给出已试证据、剩余未知、至少两种可行推荐方案（含取舍、条件、验证/回档和首选理由）以及用户自由说明入口。不能只问“推不推”，也不把“继续/取消”当两种解决办法。

支持异步/后台询问时，在当前宿主发问并继续独立且已授权的工作，待决内容与相关推送暂缓；只有阻塞式能力时如实处理。不支持可用询问功能则暂停当前任务，在同一会话带方案文字询问。超时或无可并行工作时报告待决并暂停相应推进，沉默不等于授权，不无限等候或虚构异步能力。细则见[推送前求助](skills/ld-codestyle-online/references/interaction.md#推送前无法安全决策时的求助)。

## 询问交互与未回答续行

**没回答不是停止整项任务的理由。**在原授权内评估能否安全自行决定：低风险、可可靠回档、方向清楚则自主推进并留依据；无法回档、业务方向涉及面较多而无法安全裁决或需新增批准的，只暂缓那一项，继续不依赖它的其他任务内容，有可用询问能力时尽量途中带方案发问，收尾汇总仍待裁决项，不为等收尾推迟求助。既不替用户自动选推荐，也不因未答抹掉原授权；明确取消/拒绝/稍后不按沉默处理。

LD语境区分**工具类Agent**（Codex、Cursor、IDE AI插件、DeepSeekHarness等当前终端的工具单元）与**Bot**（具人格配置、私有长期记忆/技能资料、聊天与A2A+Gateway协作、自身可操作环境的AI队友）。这是职责约定，不是行业标准、产品是否支持多OS的判断或权限等级。

- 工具类：当前授权宿主原生询问优先，缺失才用本机HTML辅助或同终端文字；不越平台到其他电脑弹窗，不默认转QQ/微信。
- Bot：在任务相关聊天渠道用原生卡片/文字询问，不在云服务器或用户其他电脑弹窗。
- 提供方案/差别、推荐理由、自定义回答与取消/稍后；只问实质待决项，不抢焦点或重复刷问。明确无人值守直接按安全续行规则处理。
- 等待默认15分钟可调，展示/未答/空闲分开。无人回答时收尾并列已自主决定的依据及回档办法、仍待裁决项；不把未决说成完成。

完整角色定义、语义原文、配置范围、问询示例、本机辅助用法及限制见[交互询问与安全续行](skills/ld-codestyle-online/references/interaction.md)。附带标准库HTML辅助，**不是所有宿主原生弹窗已适配**；不安装后台服务，不自动监控键鼠、不跨终端转发，返回答案也不签发执行批准。发布不会自动更新任何终端；继续使用已有安装的更新策略。

### 所有 AI 提交的准确身份

commit 前核实际目标，push 前复核托管平台可见性，包括fork/PR与全部推送目标；`internal`不是public，未知不能猜。身份部分在明确可辨时尽量简短，**不用 `+` 连接框架与昵称/模型**。以下规则同时适用于提交消息及新原创提交的 Git author/committer 显示名：

| 执行者 | 私有仓库（强制） | public仓库（默认，可按主人要求调整） |
|---|---|---|
| Bot：已有独立姓名、记忆与资料的实例 | 框架/容器名-昵称；不需要模型 | 昵称 |
| Agent：Codex、Claude Code、Cursor、DSH、Copilot等普通会话工具 | 框架/容器名 完整具体模型 实际推理强度 | 具体模型名，不含推理强度 |

Grok Bot、GPT Dot、Hermes Bot、DSH Bot是框架/容器示例，不证明任一会话已有独立人格。不能临时起昵称冒充Bot；Agent不能只写`GPT`、`Sol`、`auto`等泛称。模型和档位从本次有效配置/回执核实；没有推理控制时据实声明`none`，不知道不等于没有。旧Codex品牌别名可映射短名，准确模型ID不随意截断。PC改为有明确需要时显式补充，默认不查询主机名。

公开默认首行 `##模型：<昵称或具体模型名> | <摘要>`；主人可改公开显示名或明确要求省略整个身份段。新生成器 public 调用需要昵称/模型，显式省略选项只用于已获得此要求的情形。私有仍强制完整分类身份，不能用公开覆盖选项绕过。问题和解决两节保留空行，工具入口及例子见[提交规范](skills/ld-codestyle-online/references/commit.md)。

自有且获准使用的真实邮箱优先用于提交，例如Bot已配有的邮箱；没有则用获准仓库邮箱或平台noreply，**不照抄示例地址、不虚构邮箱、不把认证账户误当实际作者**。只设置当前进程或获准仓库局部字段，核`git var`有效值并回读实际commit，代提交保留原作者，不改全局配置、账号绑定或历史。生成器本身不执行Git。

公开前仍须检查文件、元数据、PR与全部待推送历史中的个人/企业隐私及秘密；简化署名不是秘密扫描。公开默认不附内部框架、推理强度、PC或人类混合显示名，不转填到其他正文。删当前文件或加.gitignore不能清除历史秘密，发现则暂停受影响推送；真实凭据泄漏由有权方撤销/轮换，合法版权/许可来源保留。

### 人类与 AI 混合贡献

核 staged diff 中的 `LD:` / 自定义人类标记及明确关联代码，私有混合首行用 `##主人 + 模型：<已核AI身份> | <摘要>`；`主人`取独立的`human_commit_name`，可改为“褪色的梦”等，不加`【】`。混合前缀的`+`保留贡献语义，不是身份连接符。公开仍默认简化AI署名，正文区分人类既有贡献与本次实现。

历史无关标记不能让所有提交都挂人类名，不能借混合署名扩大保护代码修改权限，也不能把人类旧约定说成本次亲写。标题概括具体结果，问题节交代症状，解决节填写实际改动、验证和未验边界，不能把计划写成成果。

## 目录级共享记忆

在一方模块的 Base 与配对接口所在控制区域，以 **README 声明范围、Agentic 存放记忆**。这样接手者能找到本区域的需求、经验和实际使用/测试方式，避免跨目录知识污染与重复解释：

```text
<区域根>/
  README.md                 区域声明、边界、入口索引
  Agentic/
    MEMORY.md               共有事实与经验
    USER.md                 用户意图与要求
    DEBUG.md                用户操作与正确测试流程
```

- **`README.md`** 留在原区域根，维持原本业务说明、职责与权威索引，不因记忆搬迁被替代或清空；新增MEMORY/USER/DEBUG等记忆索引。头部必须简述机制、同级逻辑scope及不可擅删/他用，让未安装本技能的Agent也能在本文件内读懂，而不是只给技能链接。
- **`Agentic/MEMORY.md`**：模块逻辑、业务意图、已验证修复经验和坑点的可核参考；区分观察与推论，不是某个Agent的私有记忆。工作会话发现或用户反馈复发缺陷、尤其Git曾修过时，应核历史并在有效修复验证后更新正确关联层级的同类条目，说明发现、修复过程、证据和防复发边界；缺陷正文已在DEBUG时不另复制，MEMORY仅提炼独立机制经验。阶段性/番茄切片成功修复也可记录并注明剩余未完成范围；半途猜测、无价值废弃/放弃方案留原任务，不灌进共享记忆。见[修复经验闭环](skills/ld-codestyle-online/references/directory-context.md#复发缺陷的修复经验闭环)。
- **`Agentic/USER.md`**：本区域持久要求、动态业务需求、用户痛点及单列的未来设想；准确保留用户原意，不把一次性任务升格为永久要求。
- **`Agentic/DEBUG.md`**：保存缺陷与防复发记录，并从会话与开发中的用户描述/纠正持续维护正确操作和测试流程，包含关联文件/数据、触发条件、有效修复要点、前提、步骤、预期、实际结果、版本/环境、恢复与未验范围。缺陷可在此维护完整唯一正文，独立机制经验再提炼到 MEMORY 并互链，不强迫抄两份。
- **每份文件独立可读**：不能只在 README 写一次。README/MEMORY/USER/DEBUG及同类文件各自在头部留简短、自足的用途与维护提示，说明持久共享属性、真实作用域/README入口、可做与不可擅做的事。即使直接打开单个文件、没安装技能或不在舰队/指挥系统，也不应误当临时文件、宿主私有记忆或任意日志；头部不充当System Prompt或新增授权。旧共享文件的缺口归打扫时补齐，保留有效正文和来源，不能只改新模板。详见[独立文件头部要求](skills/ld-codestyle-online/references/directory-context.md#每份文件头部独立可读的基础说明)。
- **物理存放不改变逻辑范围**：记忆跟随所属 README 的逻辑层级与声明范围，不只管 Agentic、不扩大权限。上图是常见布局；README 也可以与所说明的模块目录同级、索引该模块 Agentic 内的记忆，双方须写准确的入口/返回路径及排除项，不能机械回填 `../README.md`。
- **平时顺手放好**：所有 Markdown 记忆都放在它所属目录的 README/Agentic，别随手堆项目根目录或别人模块；平时，一条坑记在出事那块目录自己的 README/Agentic 里。**致命级例外优先**：死机、崩溃、掉数据、工程/存档损坏，要往外挪到「凡是动这块东西的人都得先看」的那一份文件（含它的索引）；XR 就是 XR 那套文件里最外面的那一份，不是项目根，也不是只留在出事那个子目录。条目标注「死机级」，带触发条件和一手证据（版本/提交）。README 是本区域唯一索引，没有新信息就不记。
- **按需读取但不漏读**：从共同入口和上层适用约定到目标模块，再沿直接依赖补查，不全仓注入。验收时只修改任一关联方，都应能从正常入口发现对应约束；无关模块不应被迫读全文。非致命级示例中 ViewModel/Mgr 联动记在 `./Agentic/DEBUG.md`，FunA 内 ViewModel/Prefab 联动记在 `./Core/FunA/Agentic/DEBUG.md`；若是致命级，后者移到维护 FunA 人人必读的外层入口并标「死机级」，不是固定放项目根，见[完整路径示例与规则](skills/ld-codestyle-online/references/directory-context.md#记在哪里)。
- **README 真正替代旧 Agentic.md 模块索引**：在授权区域保全有效正文、来源、相对链接和 Unity meta 后收敛，只保留一套有效入口/正文；短期兼容只能指路并列退役条件。仅新增 README、旧文件仍双写，不算迁移完成；`Agentic/` 目录及宿主 `AGENTS.md` 不在替代范围。见[迁移步骤与完成条件](skills/ld-codestyle-online/references/agentic.md)。
- 整理权限：普通Agent在九成以上把握时做无损整合；已采用精选历史流程的三份有限摘要，可由授权区域维护者先归档读验、保全旧修订再内容压缩。README/人类资料及未采用区域仍由专门获授权的审计/辅助模型处理，不扩权或丢失关键原意。

本组记录均以**参考为主而非绝对**。首次新增的解释、经验与意图摘要默认暂定，依证据自然使用“可能”“预计”“估计”“当前理解”等措辞；已发生的实测结果和真实路径仍准确陈述。`USER.md` 尽可能保留整理后的用户原话意图、条件和例外，区别摘录与摘要，不改写原话来制造不确定性。

条目经相关推送后超过 **7天**并复核，可进入持续观察；超过 **15天（半个月）**，经过**多次相关推送**和不同时间的验证且无未解决反例，才可在**再次涉及**时考虑修正为限定范围的基本稳定知识。默认将多次解释为至少3次独立相关推送（含首次），明确的项目/用户口径优先。时间与次数不自动证明正确，也不授权为了凑数推送或定时改记忆；证据不足保持暂定，反例和实质变化须降级回核。当前明确用户指令不等待观察期，不被历史摘要覆盖。完整证据口径与示例见[共享上下文成熟度](skills/ld-codestyle-online/references/directory-context.md#参考措辞与知识成熟度)。

**推送后、PR/分支合并后**，对准确的目标版本按 DEBUG 的相关用户流程实际尝试；不能只读流程或用编译、接口成功替代业务验证。未合并、未部署、缺设备/权限等明确记未验及下一责任，不自动授权部署或危险操作。失败保留证据，不降低预期来洗绿；完整规则见[DEBUG回归](skills/ld-codestyle-online/references/directory-context.md#推送后与合并后的回归)。

**所有记忆类文件尽量带日期**，新增、修改、删除条目都在文内简记真实日期、条目标识、动作/原因和操作身份（私有按Bot/Agent身份要求；公开默认昵称或模型名、不含推理强度，主人可调整）；删除仍留简短摘要或替代索引。文件更新时间、用户提出日期、推送日期、实际验证日期分开，未知历史不补造。

**打扫另做，不是每次任务都做**：找出没按要求放的旧东西，保留有效内容、来源、链接和meta，搬回所属 README/Agentic；旧 Agentic.md 的有价值正文由 README 承接。搬时留一行“从哪搬到哪、谁搬的”（公开目标按隐私规则记录）；旧代码缺注释、旧脚本没按新规也归这次打扫。可以分几次，做不完记一句“还差哪些”，下次接着清。历史人类 Readme、人工改动与宿主私有记忆不擅动，不复制两份正文；见[完整规则与模板](skills/ld-codestyle-online/references/directory-context.md)。

安装/更新技能不自动开扫；只读不搬。平时读取相关 README 及仍有效的旧入口，不因尚未打扫就忽略已有要求，也不把打扫摊到每次开发。

本节原提案记录：2026-10-15（Asia/Shanghai）；按 [Issue #2](https://github.com/LastDreamTeam/LDAI_CodeStyleAgentSkill/issues/2) 新增作用域/布局、DEBUG与日期身份约定，并据用户补充明确既有文件必须迁移、README原职责保留及每份文件独立可读的头部说明，不仅README；继承 #1 的成熟度规则，随0.3.0统一发布。
`##模型：列克星敦 + openai/gpt-6-astra | 补充目录共享记忆与用户流程回归`

2026-10-16统一审查补充：在已授权写维护触及的责任区域主动迁移旧记忆，并同时检查README入口和脚本附近旧位置。Codex + GPT-6；原提案与审查归属保留。

## 本仓库的共享上下文入口

本仓库本身是无底层引擎的Python项目，采用上述默认Markdown共享记忆。**本README是唯一入口，作用域为本仓库的一方规范、工具与测试**，逻辑范围与根目录同级；正文物理位于Agentic，不将使用者业务仓库或宿主私人资料纳入范围。

- [Agentic/USER.md](Agentic/USER.md)：有来源的人类持久要求，保留条件和修正。
- [Agentic/MEMORY.md](Agentic/MEMORY.md)：当前机制与可复核经验，首次长期结论暂定。
- [Agentic/DEBUG.md](Agentic/DEBUG.md)：真实回归入口、已核环境问题、证据和未验范围。

这些是持久项目资料，未安装技能的接手者也应先读对应头部；只维护获授权的真实增量，不擅删、改作临时文件或扩展权限。当前未采用SQLite历史；README的说明、安装及版本职责保留，不退化为仅链接列表。

## 版本与贡献

技能名固定为 `ld-codestyle-online`，当前版本 **0.5.1**（默认推送内容边界、尽力核查后的两方案求助与独立工作续行；保留0.5.0身份、跨项目记忆及健康机制），见 [Release 包](https://github.com/LastDreamTeam/LDAI_CodeStyleAgentSkill/releases/tag/v0.5.1) 与 [CHANGELOG.md](CHANGELOG.md)。此前tag与附件保持不变，不改技能名来分发。配置schema仍为1，原地保留偏好；新安装自动更新默认开启，已有关闭值保留并标脏，运行中任务不静默切规则。

Release ZIP用于允许文件包安装的宿主，不绕过原生管理器审批，也不具有Git fast-forward更新能力；现有Git/Hermes安装仍走原管理方式，不用ZIP覆盖。升级前内容可从 [legacy备份分支](https://github.com/LastDreamTeam/LDAI_CodeStyleAgentSkill/tree/legacy/main-20261016-6aa86d5) 核对。

欢迎以 Issue 或 PR 分享实践、问题和改进。贡献者应说明适用工程、真实收益、兼容风险与验证；不以单个工程的临时做法直接替代通用规则。贡献流程与三段式提交要求见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可与来源

现阶段以内部实践为主、规范仍在演进，因此选择**保留来源、共享改进的较强互惠许可**，而不是 MIT 式宽松许可。我们允许商用，也希望公开分享后的改进继续对社区可用。这是选择许可的动机说明，**不是附加的“禁止商用”或“仅研究可用”条款**。

- 技能正文、Markdown 规范和其他文档：**CC BY-SA 4.0**。
- Python 工具、测试和实际代码文件：**AGPL-3.0-only**。
- 具体分区、标准全文和第三方声明见 [LICENSE](LICENSE) 与 [NOTICE.md](NOTICE.md)。这是分区授权，不是任意选择其中一份许可。

对外分享改编正文，需要署名、标明修改并按相同或兼容许可分享；代码的分发和修改版网络交互遵循 AGPL 对应源码义务。**不把一切私人修改都说成必须立即发布到全网，也不强制回传 PR。**只借鉴设计思想、遵守风格或使用技能协助开发，不因此自动要求独立产品整体开源；直接复制受保护代码/表达及衍生、组合情形另按适用许可判断。

保留 LD 原作来源不等于把他人的新增版权归 LD 所有。品牌不代表对衍生版本的官方背书，许可也不冒充注册法人或商标授权。
