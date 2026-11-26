# Chorotheia v1.1.0

Memory beyond context. 本地优先、跨 Agent 的项目记忆与阶段接力工具。

这是 Python 3.9+ 程序，运行仅使用标准库、Markdown、JSON 和 Git。没有数据库、常驻服务、在线存储、自动提交、推送或发布。商标尚未查重，本版本仅作本地使用。

## 开始使用

安装位置为 `~/.chorotheia/`。为保留原有 shell 配置，没有修改启动文件。可以一直使用完整命令，或在当前终端执行以下命令启用短命令：

```sh
export PATH="$HOME/.chorotheia/bin:$PATH"
chorotheia --version
chorotheia doctor
```

在你授权的项目中使用（先将示例路径替换为真实项目目录）：

```sh
chorotheia init --project /absolute/project --dry-run
chorotheia init --project /absolute/project
chorotheia restore --project /absolute/project --text --budget 2400
chorotheia checkpoint --project /absolute/project \
  --summary '已完成的具体工作与当前状态' \
  --next '下一步可执行动作' \
  --decision '决策及理由' \
  --test '实际执行的检查与结果；未执行则写明原因'
chorotheia handoff --project /absolute/project --to antigravity \
  --summary '交接状态' --next '接手后的第一步'
chorotheia recall '检索词' --project /absolute/project
chorotheia status --project /absolute/project
chorotheia audit --project /absolute/project
```

`--next`、`--decision`、`--error`、`--test` 可重复。不要把凭据放入参数、记忆或共享文档。过滤器只提供有限的模式匹配，不能保证识别所有敏感信息。

## 自动初始化与冲突

`init --mode auto` 自动识别新旧项目；仅有 Git 元数据的空仓库按新项目处理。`retrofit` 或 `init --mode retrofit` 对旧项目增量补充。`new` 拒绝已有业务文件的目录。`init --mode audit` 只审计，`init --mode repair` 对已初始化项目执行保守修复。所有命令的选项放在子命令后。

默认项目结构：

```text
AGENTS.md                     # 仅不存在时创建
HANDOFF.md                    # 仅不存在时创建
.agent/
  manifest.json
  CONTEXT.md                  # 已确认、推断、未知及来源
  STATE.md
  DECISIONS.md
  ERRORS.md
  CHECKPOINT.json
  history/
  archive/
  local/.gitignore
  adapters/capabilities.json
```

既有 README、AGENTS、HANDOFF、代码、依赖文件和 Git 配置都保持原样。AGENTS/HANDOFF 冲突时另建记忆空间内的补充文件，由 `status` 返回真实路径。已有外部 `.agent/` 时使用 `.agent/chorotheia/`；`.agent` 是文件或符号链接时使用 `.chorotheia-agent/`。所有可用空间均冲突就拒绝，不覆盖。

项目目录只保存可共享记忆；备份、完整性基线、所有权凭据、事务日志均在 `~/.chorotheia/` 内，权限为 0700/0600。`.agent/local/` 默认只有忽略规则，没有私有会话信息。工具不修改项目 `.gitignore`，也不会把新文件自动加入 Git。

## 恢复与分层读取

先运行 `restore --text`，只加载 L0 约束和 L1 检查点、状态、上下文；L2 决策、错误、历史通过 `recall` 或直接阅读来源按需加载。初始建议目标为 1500–3000 tokens，默认使用 2400 UTF-8 字节的保守上限，不安装特定模型的分词器，不声称准确 token 数。JSON 诊断字段不包含在正文上限内。

当前维护实现按字段分配预算：目标、阶段、下一步、阻塞项优先，随后是完成情况、进展、最新决策和测试，背景按需读取。先给每个字段一次加载机会，再补充列表余项；不再重复加载 CHECKPOINT 与 STATE 的摘要。条目完整保留；过长的目标/进展可只加载完整句子，超长命令和测试条目整条省略。正文列出省略项，JSON 的 `loaded_fields`、`omitted` 提供准确字段和来源；需要时读取源文件。极小预算可能只容纳安全提示、来源和省略提示，过长来源路径无法容纳时明确报错，不输出半个 JSON。

## 进度核对与阶段遗漏提示

检查点可增加 `--goal`、重复 `--done`、`--phase`、`--phase-state open|complete`。未传目标和阶段时继承已有值；完成情况、下一步、决策、错误和测试记录由本次参数提供。阶段应在开始实质工作前开启，并在实际收尾后完成：

```sh
chorotheia checkpoint --project /absolute/project \
  --goal '改进导出' --phase '中文文件名验证' \
  --summary '开始验证' --next '运行边界用例'
chorotheia checkpoint --project /absolute/project \
  --phase-state complete --summary '验证完成' \
  --done '处理中文文件名' --test '实际命令与结果' --next '等待下一项任务'
```

未完成的阶段不能直接换名，否则拒绝写入。阶段标记属于 Agent/操作者的显式记录，不自动判断测试是否充分。

`snapshot_at` 是最近保存副本的时间；`reviewed_at`、`reviewed_checkpoint_id` 是最近显式核对的时间与原始检查点 ID。`covered_git` 是核对时覆盖的基线，`observed_git` 是保存时的观察。Hooks 只更新快照与观察，不更新核对时间或基线；重复 Stop 不会将旧进度变成新进度。旧记录及初始化记录没有核对信息，保持未知，不猜测迁移；首次显式 checkpoint 即可补充新字段，schema 仍为 1。

`status` 和 `restore` 的 `freshness` 返回：

| 状态 | 含义 |
|---|---|
| `reviewed` | 已显式核对且当前 Git 证据与覆盖基线相同；不证明笔记内容正确 |
| `needs_review` | Git HEAD、暂存索引或已修改/未跟踪内容与基线不同，提示复核，不直接认定遗漏 |
| `phase_open` | 有明确开启但尚未收尾的阶段；即使没有代码变更也可提示 |
| `unknown` | 无明确核对信息、Git 不可用、检查点缺失/修改，或无法安全比较 |

多种情况并存时查看 `reasons`；Git 不同优先显示 needs_review，未收尾阶段仍保留在 phase/reasons。核对时允许确认文本不变而更新基线，不能仅因时间流逝而判断笔记过期。Git 指纹排除本工具管理的记忆，避免保存自身造成误报；比较实际修改内容，可以发现同一文件一直显示 M 但内容再次变化。指纹只保存哈希，不保存差异正文，不调用外部 diff/textconv。对敏感路径、符号链接、硬链接、子模块等无法安全读取的变化，以及单文件超过 4 MiB、变更路径超过 1000 或总读取超过 16 MiB 的情况，降级为未知，不绕过路径防护。该观察不是原子快照，外部进程仍可能并发修改。

提示不阻塞 Agent，也不会自动改写进度。未启用下述对话观察功能时，纯讨论/外部工具工作若未登记阶段，仍无法自动检测；结束 Hook 保存后可从 status 或下一次 restore 查看提示。Git 判断只涵盖 Git 可见且位于当前项目范围的文件，不涵盖被忽略文件或未保存编辑器内容。

## 对话观察与额度提醒

按项目显式启用，默认关闭，不引入守护进程或额外模型 API：

```sh
chorotheia monitor --project /absolute/project --enable --quota-warning 80 --quota-critical 95
chorotheia monitor --project /absolute/project --details
```

阈值单位为已使用百分比，要求 `0 < warning < critical <= 100`。配置、观察游标、候选片段和额度证据存于私有 `~/.chorotheia/projects/PROJECT_ID/monitor.json`；事务前像与其他备份同样留在全局私有目录。项目 CHECKPOINT 只保存待核对标记、数量、失败分类及不透明核对令牌，不复制候选原文或会话绝对路径。

Codex 原生 Hook 提供 session_id、transcript_path、cwd 时，观察器只接受当前 CODEX_HOME/sessions 下、文件名和首条元数据 ID 匹配的 rollout JSONL；拒绝路径穿越、符号链接、硬链接及其他用户的文件。首次绑定从当前文件末尾开始，**不声称此前历史已核对**；后续增量提取可见用户消息和最终回复，排除分析、摘要、commentary、开发者/系统消息及工具参数/结果。turn_context 切换到其他项目后的可见消息不会导入。

需要手动绑定或明确读取已有记录时：

```sh
chorotheia monitor --project /absolute/project --session-id NATIVE_SESSION_ID \
  --transcript /absolute/codex/sessions/.../rollout-...-NATIVE_SESSION_ID.jsonl
# 仅首次绑定时可加 --include-existing；每次最多扫描 1 MiB，存在 backlog 时重复运行。
```

启发式识别目标/决策/完成/下一步/阻塞线索；只生成 `inferred; requires review` 候选。每个项目最多 8 个来源，每个来源最多保留 20 条、每条 300 UTF-8 字节的脱敏片段；数量和摘要哈希仍覆盖所有已观察消息。候选片段不完整时须核对来源，不能将普通问答或历史引用当成确认的任务变化。`monitor --details` 给出消息 ID、字节范围、来源、观察位置和 review_token。

观察位置前进不等于完成语义核对。Agent 核对后用以下命令确认；新可见消息会让旧令牌失效，核对与检查点在同一事务中写入，失败则回滚核对状态：

```sh
chorotheia checkpoint --project /absolute/project --summary '核对后的实际进度' \
  --decision '已确认的决定；或明确说明本次讨论没有任务变化' \
  --next '下一步' --test '实际验证或未运行原因' --review-discussion EXACT_REVIEW_TOKEN
```

多来源时重复传 `--review-discussion`。来源缺口、未读 backlog 不能被令牌跳过。来源替换、截断、游标附近改写或超大记录会拒绝推进；保持原始状态供人工检查，不猜测重新绑定。隐藏的未保存对话、启用前历史、缺失或改变格式的来源不在自动覆盖范围内。旧原生 JSONL 不是稳定公开接口，格式变化时应降级人工核对。

额度观察使用原生 token_count 事件中的额度窗口，或按需通过官方 App Server 读取：

```sh
chorotheia monitor --project /absolute/project --refresh-quota --codex-binary /absolute/native/codex
```

该刷新只启动短时 stdio 客户端，发送 initialize/initialized 和 account/rateLimits/read，不创建 thread、turn、模型请求或登录操作；由原生程序使用已有登录，响应仅保留窗口百分比、重置时间等额度字段。监控 Hook 不逐次启动 RPC，而是读取已有原生额度证据。比较所有计费 bucket 的 primary/secondary 窗口；超过 300 秒、已重置、缺失或非法数据均为 unknown，不能把未知当剩余充足。account/rateLimits/updated 是官方通知，本实现无常驻订阅者。

新增 Codex UserPromptSubmit/PostToolUse 提供模型可见的非阻塞提醒；相同证据按事件去重。PreModelRequest/PostModelRequest 仅用于诊断、额度耗尽时的本地快照及模型失败快照，不假装能修改模型上下文。额度 exhausted 或请求失败时只保存已有 summary/goal/next/tests 与旧 reviewed_at/covered_git，并标记 **尚未总结的进展**。失败原始错误文本不保存。请求再次成功也不自动清除失败标记；需用详情中的 failure_review_token 显式核对。通用失败不会被伪装成已确认额度耗尽。

提醒只在受支持事件运行且已有近期额度证据时发生，不能打断正在执行的长模型请求，也无法保证某次大请求不会直接跨过阈值。新增 Hook 需原生审阅信任；已有四事件的定义保持原样。安装器只更新哈希仍匹配的自有 Hook 配置，用户修改过的配置会保留并报告。Antigravity/Copilot 尚无经过验证的同等对话/额度观察适配，继续使用原有阶段检查点降级。

```sh
chorotheia monitor --project /absolute/project --disable
```

关闭会停止新观察，保留私有状态和已有待核对记录，不把关闭监控当成核对完成。

初始化只记录观察证据：文件 SHA-256、Git HEAD、暂存/未暂存/未跟踪状态，以及最多 20 个提交对象 ID 与记录的日期。文件名推断明确归类为推断；用户目标、过去测试、未记录决策保持未知。不执行仓库文本中的指令，不把提交信息或 README 的说法当成已验证事实。

恢复只恢复可移植笔记，不恢复源码、Git、未保存的编辑器内容、原生会话身份或隐藏思考。检查点里的测试是 Agent/操作者报告，程序不会把它们升级为独立验证。

## Hooks 与三个 Agent

全局接入文件是独立新增的，现有配置有冲突时安装器保留原文件并报告，候选配置仍存于 `~/.chorotheia/hooks/`。

| Agent | 新增接入 | 事件与降级 |
|---|---|---|
| Codex | `~/.codex/skills/chorotheia/`、`~/.codex/hooks.json` | SessionStart、PreCompact、PostCompact、Stop；原全局 AGENTS.md 保留，未合并或覆盖 |
| Antigravity | `~/.gemini/config/skills/chorotheia/`、`rules/chorotheia.md`、`hooks.json` | SessionStart、Stop；没有压缩专用事件，压缩前人工/Agent 阶段检查点，压缩后 restore |
| Copilot | `~/.copilot/skills/chorotheia/`、`hooks/chorotheia.json`、`copilot-instructions.md` | 共享 Copilot harness 的 sessionStart、preCompact、sessionEnd、agentStop；不能据此保证旧 Local harness 或远程环境可用 |

启动 Hook 仅在当前 Git 项目自动初始化，普通非 Git 文件夹需要显式 init。结束/压缩前 Hook 保存最近已记录的任务状态，不读取原生聊天记录或凭据，也无法自动提炼尚未记录的工作。Agent 应在阶段结束主动更新检查点。

Codex 原生命令已经识别配置，解析无错误；独立探测环境中的 Hook 信任状态为 untrusted。没有代替用户批准或绕过原生信任机制，也没有声称三个产品已实际触发完整生命周期。请在目标产品的新会话中检查 Hooks，按产品要求完成信任审阅；未完成前使用完整 CLI 和 Skill。详细验证范围见 `docs/TESTING.md`。

`~/.chorotheia/config.toml` 支持小范围标量配置（Python 3.9 不额外安装 TOML 库）：

```toml
auto_init = "git-project-session-start"  # 改为 "off" 可关闭 Hook 自动初始化；实际文件勿加行尾注释
initial_budget = 2400
```

实际解析不支持行尾注释、多行 TOML 或复杂结构。其他字段是安装元数据。修改配置后，所有权检查会将其报告为用户修改；升级和卸载会保留它。

## 与已有 Universal Handoff 兼容

原 Skill 位于独立仓库 `ganbaba/skills` 的 `agent-handoff/skill/universal-handoff/SKILL.md`，其备份和入口记录在全局 `backups/existing-handoff/`、`adapters/handoff/`。未安装或启动其控制器，没有改动 state.json、grants、锁、运行凭据或工作区。

普通 `handoff --to ...` 只生成补充笔记，不启动其他 Agent。对于正在运行的 Universal Handoff 任务，应先按原 Skill 获取控制器 status，并仅在它授权的隔离工作区继续。只有在控制器已经提供对应值时，才可以使用：

```sh
chorotheia handoff --project /absolute/authorized-workspace \
  --summary '已观察的结果' --next '下一步' \
  --task-id CONTROLLER_TASK_ID --run-id CONTROLLER_RUN_ID \
  --base-revision CONTROLLER_REVISION --outcome continue
```

这个模式只向标准输出导出严格协议 v1 JSON，不写控制器文件、不创建 token，也不替用户验收。输出已通过原 Handoff 程序的 `result_validate`，但尚未在真实控制器运行中跨三个提供商自动接力。

## 审计、故障处理与卸载

```sh
chorotheia audit --project /absolute/project
chorotheia repair --project /absolute/project --dry-run
chorotheia repair --project /absolute/project
```

修复只重建缺失的可恢复记忆，不覆盖已修改文件；缺失检查点可从哈希验证通过的历史记录恢复。用户明确审阅过 STATE/CONTEXT/DECISIONS/ERRORS 的编辑后，才用 `repair --adopt` 更新所有权哈希。修改过的 manifest 不会被自动信任。移动或从别的机器导入的记忆可以读取，但缺少本机私有凭据时不允许修改；v1 尚无安全导入/重新绑定工作流。

中断的事务会阻止后续写入。先检查错误中提供的事务 ID，再预览并执行：

```sh
chorotheia repair --project /absolute/project --rollback TRANSACTION_ID --dry-run
chorotheia repair --project /absolute/project --rollback TRANSACTION_ID
```

回滚仅处理本事务已确认写入且内容仍匹配的文件；外部修改或崩溃后无法确定归属的文件会保留并报告。不要删除锁文件。POSIX 锁会随进程结束释放，锁文件本身会保留。

```sh
chorotheia compact --project /absolute/project --keep 5 --dry-run
chorotheia compact --project /absolute/project --keep 5
chorotheia upgrade --project /absolute/project
chorotheia upgrade --global-install --dry-run
chorotheia uninstall --project /absolute/project --dry-run
chorotheia uninstall --global-install --dry-run
```

`compact` 是可检索的逻辑归档，保留不可变原件，不节省磁盘。项目 upgrade 支持兼容字段布局的 schema 0 → 1，并已用合成旧版夹具验证；没有旧 UACS/Letheia 发布格式可核验，未知格式拒绝迁移。全局 upgrade 默认检查当前版本；`--source /absolute/reviewed/source` 支持本地 v1.1.0 安装或维护包的哈希保护更新、语法检查、备份及幂等更新，不自动下载版本，不推测未来迁移。

卸载预览不会移除内容。实际卸载必须由你明确执行不带 `--dry-run` 的命令；只移除安装记录中内容仍匹配的自有文件，保留用户编辑、私有记忆和备份。不删除无关文件或递归清理目录。正式安装未执行卸载；卸载验收均在临时配置目录中完成。

## 安全边界

独占创建、同目录临时文件、fsync、原子发布/替换、描述符相对访问、拒绝路径穿越/符号链接/写目标硬链接、进程间排他锁、SHA-256 比较、私有所有权凭据、事务前像备份和创建前后完整性检查均有实现与测试。Git 操作只读取状态/历史，初始化完整扫描包括 Git 内部文件。Git 环境覆盖变量被清除，禁用可选写锁。

锁只约束合作的 Chorotheia 进程。外部编辑器不遵守它，POSIX 也没有通用的“比较内容后原子替换”原语；最终哈希检查与替换/删除之间仍有极小竞态窗口，不能宣称抵抗任意恶意同用户进程。初始化前后发现外部改动会回滚本次写入并保留外部改动。

初始化/审计完整哈希扫描在大型仓库可能较慢；单文件记忆读取一般上限 4 MiB，恢复素材上限 256 KB，检查点上限 128 KB，单归档上限 2 MiB。不提供自动后台轮询、语义向量检索、数据加密、任意旧版格式迁移或业务文件快照恢复。

## 模块与验证

Core/Checkpoint/Handoff/Compact/Recall/Restore/Repair/Upgrade 生命周期位于 `chorotheia/core.py`；Bootstrap 位于 `bootstrap.py`；Memory 与分层恢复位于 `memory.py`；Guard 位于 `guard.py`；Hooks/Adapters 位于 `adapters.py`；Doctor 位于 `doctor.py`；安装、维护与全局卸载位于 `installation.py`。这些是功能模块，不强制一模块一个文件。

从本源码目录运行：

```sh
python3 -B -m unittest discover -s tests -v
```

公开验证结果见 `docs/TESTING.md` 和 `docs/verification.json`。含本机路径的原始部署记录不随源码公开。测试只在临时项目及临时配置目录运行；Git 提交仅用于构造临时历史夹具，没有提交用户项目。

超过 128 KB 的原生事件输入只进行流式丢弃并输出诊断，不保留工具载荷、不阻断工具调用；随后受支持的事件可从对话游标继续观察。这类跳过不代表已读取或核对该次事件。

## 从 v1.0.0 升级到 v1.1.0

下载并校验新源码包，在解压后的源码目录执行新版本升级器（旧 CLI 不理解未来版本）：

```sh
python3 -B -m chorotheia upgrade --global-install --source "$PWD" --dry-run
python3 -B -m chorotheia upgrade --global-install --source "$PWD"
~/.chorotheia/bin/chorotheia --version
```

升级器只接受已知 1.0.0 前驱或相同版本，核验安装记录和全部自有文件哈希。保留旧 core/releases/1.0.0 目录，在同一事务内备份并切换启动器、VERSION 和配置版本元数据，保留其他设置、私有记忆和 Hook 信任记录。修改过的安装文件会使升级拒绝写入；修改过的注册 Skill/Hooks 保留并报告。项目 schema 仍为 1，旧笔记可直接读取；可显式执行 `chorotheia upgrade --project /absolute/project --dry-run` 后更新项目版本，不改写历史检查点。未知旧格式拒绝迁移。

启动器使用隔离 Python 环境并显式加载已安装的版本目录，忽略当前项目及 PYTHONPATH 对模块解析的覆盖；从源码目录升级时使用前述新版本模块命令。观察 Hook 遇到项目写锁竞争时有限重试后给出跳过诊断，不把观察失败变成业务工具失败。
