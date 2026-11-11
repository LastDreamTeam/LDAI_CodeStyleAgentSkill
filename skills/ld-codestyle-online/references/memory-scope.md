# 共享 Markdown 的跨项目范围与本机排除

本页定义共享 Markdown 在不同引擎和语言项目中的适用范围，以及本机项目根黑名单协议。它不授予提交、发布、资产改写或任意文件维护权限，也不把项目共享知识变成某个 Bot 的私人记忆。当前主人明确指令优先；具体目录读写仍遵守[目录共享上下文](directory-context.md)与所属 README 声明。

## 所有项目默认启用，重型引擎必须执行

安装本技能后，**共享 Markdown 机制默认适用于所有项目**：重型引擎工程必须执行，一般工程也默认执行，不因非 Unity、没有面向对象接口或属于脚本项目就跳过。Unity、Unreal Engine、Cocos、Godot、自研/工业引擎、Web/H5/Vue、Node.js/TypeScript、PHP、Python 等都沿实际模块边界适配。

只有**主人明确要求排除具体项目**时，才把该项目的真实根目录加入本机环境变量黑名单。不能由 Agent 因嫌麻烦、尚无目录、工具失败或对“轻型工程”的猜测自行排除；坏黑名单也不等于获准停用或默认启用。`--owner-requested` 是调用方对真实要求的声明，工具不认证发言者或生成新授权。

此范围只调整共享 Markdown 的默认适用性，不强迫非 Unity 项目建立 C# Base/配对接口、继承结构、命名空间、Inspector、Prefab 或 Unity 资产。不适配的源码架构规则仍按语言及当前授权判断。**提交身份、公私有可见性、贡献保护与隐私规则独立于记忆黑名单**；排除共享记忆不能豁免它们，见[提交规范](commit.md)。

## 模块目录怎样适配

先读项目现有入口、模块说明和真实依赖，再选最接近职责边界的 README。README 保留业务说明和唯一索引；共享正文集中到它声明的区域 `Agentic/USER.md`、`MEMORY.md`、`DEBUG.md`。SQLite 精选历史仅在该区域已声明采用时按[历史规范](memory-history.md)使用，跨项目默认 Markdown 不自动部署数据库。物理目录不改变逻辑范围，不能把它们只当 Agentic 代码自己的资料。

下表为路径结构示意，必须落到项目真实目录，不要求为了匹配例子移动代码：

| 项目类型 | 区域 README 示例 | 共享正文示例与范围 |
|---|---|---|
| Unity | `Assets/<Area>/README.md`，或实际职责在 Scripts 时用 `Assets/<Area>/Scripts/README.md` | 同责任区 `Agentic/`；声明真实 Base/接口、实现和相关资产范围，不自动改场景、Prefab 或人工资料。 |
| Unreal Engine | `Source/<Module>/README.md`；一方插件按其真实模块入口 | 同模块 `Agentic/`；说明 C++、蓝图/内容和模块依赖的真实映射，不因目录名接管第三方插件。 |
| Cocos | `assets/scripts/<Module>/README.md`，或现有资源/脚本模块入口 | 所属区域 `Agentic/`；按实际组件与资源引用声明，不照搬 Unity 层次。 |
| Godot | `scripts/<Module>/README.md`，或实际场景功能目录的 README | 同职责区 `Agentic/`；覆盖真实 GDScript/C#、节点和资源联系，不强造 OOP 包装层。 |
| 自研/工业引擎 | `modules/<Subsystem>/README.md`，或现有子系统入口 | 同子系统 `Agentic/`；记录实际部署、设备、数据及安全边界，不把记忆步骤视作设备操作授权。 |
| Web / H5 / Vue | `src/features/<Feature>/README.md`，或现有页面/服务模块入口 | 同区域 `Agentic/`；明确页面、状态、接口、服务等实际范围，不按前后端标签复制两套正文。 |
| Node.js / TypeScript | `packages/<Package>/README.md` 或实际 `src/<Module>/README.md` | 包或模块的 `Agentic/`；以真实包边界及依赖为准，不要求每个文件建立目录。 |
| PHP | `src/<Module>/README.md` 或既有 `app/<Area>/README.md` | 对应 `Agentic/`；适配实际 MVC、服务或过程式组织，不把规范当重构授权。 |
| Python | `src/<package>/README.md`、`<package>/README.md` 或脚本集合入口 | 对应 `Agentic/`；按包、脚本组或实际子系统维护，可保留函数式/过程式实现。 |

README 可以与被说明的区域同级。例如 `Features/README.md` 明确负责 `Realtime/`，则可索引 `Realtime/Agentic/USER.md` 等文件；这些文件应写明返回 `../../README.md`、真实 scope 和排除项。不能凭 `Agentic/` 的物理位置扩大到兄弟区域，也不能因它与 README 不在同一目录而漏掉上层联动约束。

四类文件分工保持一致：README 是业务地图和索引；USER 保存有来源的主人持久意图；MEMORY 保存可回核的共有事实与机制经验；DEBUG 保存缺陷、防复发和真实用户操作/测试流程。每份文件的头部都须自足说明用途、持久共享属性、scope、README 入口及维护边界，不要求陌生 Agent 先装技能才能理解。

## 按当前写任务逐区补齐

- 开始任务先核项目根、排除状态、现有 README 与适用共享条目。项目根来自已核项目/仓库边界，不把当前工作子目录随手当新项目以绕开主人排除。
- 首次触及某责任区的**已授权写任务**，沿真实结构补齐必要共享入口及本次有价值的记忆，修正与该区有关的路径和头部说明；保留既有人类资料、有效历史、来源和保护标记。不因机制默认启用就全仓扫荡或一次建满所有空目录。
- 只记录真实增量：用户意图保留原意与条件，经验说明证据及未验边界，修复流程来自实际核验；没有相应事实就不虚构 USER/MEMORY/DEBUG 内容。既有共享文件的独立说明和历史保全仍按目录规范维护。
- **只读任务只读取，不创建记忆文件、目录或数据库**。安装技能及执行范围查询也不会自动创建业务项目资料；工具不会注入所有宿主、监控所有项目或遍历全盘。
- 黑名单只控制本机这个项目的默认共享记忆采用；已有资料不因此被删除或改作他用。未来明确恢复时先读回既有记录，核当前代码再继续。

## 本机黑名单协议

环境变量名为 **`LD_CODESTYLE_MEMORY_BLACKLIST`**，内容是 JSON 绝对项目根字符串列表；未设置表示 `[]`，默认启用。变量不得包含相对路径、换行路径、非字符串项、对象或其它损坏值。变量存在但为空字符串也属于坏值，工具拒绝处理，不自动清空或回退默认。

根目录按本机路径规则解析实际链接、点路径和大小写，并以**规范化后的完整根相等**判断，不使用字符串前缀或祖先包含关系。排除 `Project` 不会自动排除相邻的 `ProjectElse`，也不会自动排除独立声明为另一个项目的 `Project/IndependentProject`。但普通模块仍属于其真实项目根，不能把模块目录当独立项目来规避排除。

查询/修改命令的目标根必须是当前存在的绝对目录。列表中已移动或暂时离线的合法绝对根仍保留，修改一个项目不会顺手清掉其他项目；现存文件不能作为项目根。列表不执行环境表达式、波浪号或 shell 展开。跨机/跨账号时路径和环境独立，不把机器私有根列表提交到公开仓库、复制到别人的配置或当作全组织策略。

Windows 读取顺序：当前用户 `HKCU\Environment` 中的**该变量**存在时优先读取；只有该变量不存在才读当前进程继承值；两处都不存在才默认 `[]`。持久 `[]` 同样优先，避免宿主仍继承旧排除列表时把已恢复项目再次禁用。读取权限失败、坏 JSON 或坏类型都返回错误，不退回旧进程值。读取仅访问这一个注册表键值，不扫描其他环境变量。

## CLI 与生效判定

[项目范围工具](../scripts/project_memory.py) 使用 Python 3.10+ 标准库；下列命令从完整技能目录执行。示意路径要替换为本机已核绝对项目根，不要求顺序全跑，更不是对当前真实项目的排除授权：

```sh
# 只查询：无网络请求，不写项目文件或环境
python -B scripts/project_memory.py show --project-root "<已存在的绝对项目根>"

# 主人明确要求排除/恢复时，默认仅返回环境变量建议
python -B scripts/project_memory.py exclude --project-root "<已存在的绝对项目根>" --owner-requested
python -B scripts/project_memory.py include --project-root "<已存在的绝对项目根>" --owner-requested

# Windows：主人要求在本机持久应用时，写当前用户的单个变量并回读
python -B scripts/project_memory.py exclude --project-root "<已存在的绝对项目根>" --owner-requested --persist-user
python -B scripts/project_memory.py include --project-root "<已存在的绝对项目根>" --owner-requested --persist-user
```

`show` 返回当前状态；`exclude/include` 没有 `--owner-requested` 会失败。默认修改不写 `os.environ`、注册表或 shell 配置，只返回 `status=environment_update_required`、建议 `value` 与 `persisted=false`。**建议不是已经生效**：调用方应通过已有且获授权的宿主/系统环境入口落地，再在实际使用该配置的环境运行 `show` 复核。

Windows 的 `--persist-user` 只设置 `HKCU\Environment` 的 `LD_CODESTYLE_MEMORY_BLACKLIST` 为字符串 JSON，保留其他变量和其他项目根；移除最后一项时写 `[]`，不删除该变量而让继承旧值重新生效。持久变更在当前用户目录的 `.ld-codestyle/project-memory-blacklist.lock` 下取得排他短锁，锁内重新读取、计算、写入并精确回读，成功后才报告 `persisted=true`。锁跨技能安装和项目共享，不能按项目各建一把锁；已有或残留锁直接拒绝，不自动等待、删锁或猜 PID 失效后抢占，需先核活动写者和现场。正常退出清理本次取得的锁，只读查询和默认建议不建立锁。

写前仍复查原值，检测到未使用此锁的外部修改时拒绝覆盖；该复查不是注册表原子 CAS，外部宿主/系统设置入口应协调单写者。写入已尝试后若关闭句柄或读验失败，返回 `persisted=null` 而不是假称未写入，应先查询现状再处理。测试注入临时锁和注册表替身，不操作真实用户持久环境。

其他系统保留已有宿主环境配置入口；即使指定 `--persist-user`，本工具仍只返回建议、`persisted=false` 和下一步，不自行修改 shell profile，不假称已跨重启持久化。宿主采用何种持久性以它的真实能力为准；落地后用 `show` 复核，不拿当前 shell 临时值冒充所有会话均已更新。

JSON 字段：

| 字段 | 含义 |
|---|---|
| `status` | `ok` 为查询成功；`environment_update_required` 为候选待落地；`updated` 为持久写入且读验成功；`error` 为失败。 |
| `project_root` | 本机实际规范化后的目标绝对根。 |
| `enabled` / `excluded_roots` | **当前已观察的实际状态**；建议尚未落地时仍保留旧状态。 |
| `desired_enabled` / `desired_excluded_roots` | 仅修改命令返回的主人要求候选，不等同于当前生效值。 |
| `variable` / `value` | 变量名和准确 JSON 环境值；修改命令的 `value` 是拟写值，查询则是当前值。 |
| `source` | `user_environment`、`process_environment` 或 `default`，表示当前实际读取来源。 |
| `persisted` | 本次调用是否完成持久写入并读验；查询也为 false，不能据此认为已有持久配置不存在。写入已尝试但无法核实结果时为 null。 |
| `next_step` | 尚待落地时说明通过宿主/系统配置入口应用并再次查询。 |

正常查询、建议和已验证写入退出码为 0；操作失败返回非零及不含坏值原文的 JSON 错误。`environment_update_required` 仍是待执行结果，依赖方不能只看退出码就声称已排除；写后验证失败时结果可能已改变，应先运行 `show` 检查，不盲目重复修改。

工具只提供范围查询与明确请求的本机变量更新，不替代主人意图核验、实际业务测试、共享文档的语义审查或[提交身份规则](commit.md)。
