# Chorotheia v1.2.0

**Memory beyond context.** · One memory. Any agent.

新增异常中断后的恢复核对入口，并正式包含超长转录扫描及有证据的本机目录迁移修复。沿用 MIT、Python 3.9+ 标准库和本地优先设计，无数据库、守护进程或额外模型 API。

## 新增与修复

- Codex 已启用监测且存在未处理失败时，原会话下一轮“继续”即可获得恢复核对入口；不依赖重新触发 SessionStart。
- 新增只读 `recover` 命令，提供检查点、显式核对时间、Git 指纹及讨论状态，引导 Agent 核对保存的工具结果、运行中任务和实际测试。
- 首次给出恢复流程，后续只保留简短待处理提醒；启动或压缩后重新加载。普通 Git 改动和未结束阶段不会独自触发完整恢复。
- `checkpoint --recovery-result ... --review-recovery TOKEN --test ...` 在同一事务记录恢复结果并确认该次失败；证据变化会使令牌失效，失败回滚不丢失原记录。讨论仍需单独核对，不自动清除失败或宣称测试通过。
- 修复大于 1 MiB 的 JSONL 记录阻塞后续讨论及额度观察。完整解析上限为 8 MiB；更大记录有界排空并明确保留缺口，后续额度仍可读取。来源身份、路径、游标锚点及私有状态保护保留。
- 已有项目在本机更名/移动时，可用 `repair --rebind-from OLD_ROOT`，要求原私有凭据、提交事务和完整性证据，保留旧绑定的停用记录；不伪造导入记忆的所有权。不修改 Codex 聊天本身的工作目录。
- 支持从已知 v1.0.0 / v1.1.0 安全升级到 v1.2.0，保留旧程序、私有记忆、历史检查点及原生信任配置。

## 下载与升级

附件含源码 ZIP、源码 tar.gz、独立 Skill ZIP 和 SHA256SUMS.txt。校验 SHA-256 后解压；独立 Skill 仍需 CLI。

新安装运行 `python3 -B install.py --dry-run`，核对后运行 `python3 -B install.py`。

已有安装请在新源码目录运行新版本升级器：

```sh
python3 -B -m chorotheia upgrade --global-install --source "$PWD" --dry-run
python3 -B -m chorotheia upgrade --global-install --source "$PWD"
~/.chorotheia/bin/chorotheia --version
```

项目可先预览 `chorotheia upgrade --project /absolute/project --dry-run`。修改过的安装文件拒绝覆盖；修改过的注册 Skill/Hooks 保留并报告，不批准或绕过原生信任。

## 验证与限制

隔离测试覆盖恢复入口去重、压缩重载、只读计划、过期令牌、失败/讨论分别确认、事务回滚、版本迁移、超长记录和原有安全验收。逐项结果见 docs/verification.json；发布工作流在 Linux/macOS 验证并从同一提交生成确定性归档。

恢复入口是给 Agent 的核对流程，不能保证 Agent 执行正确，不能还原隐藏思路、未保存文件或原进程执行位置；不自动重试操作、终止进程或恢复业务源码。自动讨论/额度/恢复入口目前适配 Codex；其他 Agent 降级到手动检查点。监测默认关闭，受原生事件、信任、来源可用性及证据新鲜度限制，无法打断长模型请求或补发过去漏掉的提醒。

敏感过滤为启发式，合作锁不覆盖外部编辑器全部竞态，未知旧格式拒绝猜测迁移。既有版本标签与附件保持不变。商标查重尚未完成，未发布到 PyPI/npm。
