# Chorotheia v1.1.0

**Memory beyond context.** · One memory. Any agent.

本次发布将字段优先恢复、阶段进度复核、可见讨论观察及额度保护纳入正式版本，沿用 MIT 许可证、Python 3.9+ 标准库和本地优先设计。

## 新增与改进

- 优先恢复目标、阶段、下一步和阻塞项，去除重复摘要；按完整条目或句子加载，并提供省略字段的来源。
- 区分自动快照与显式核对，比较 Git 内容指纹；支持目标、完成事项和阶段开始/结束记录。
- 按项目启用 Codex 可见讨论观察，生成带来源的推断候选；精确核对令牌避免把“读过消息”误当成“已更新进度”。
- 可配置额度提醒，默认已用 80% 提醒、95% 紧急提醒；支持官方额度只读刷新。额度耗尽或模型失败时仅保存已有笔记，标记“尚未总结的进展”。
- 观察状态和候选片段留在本机私有目录；不调用额外模型 API，不默认启动守护进程。
- 超大工具事件流式丢弃；写锁忙时有限重试后给出诊断，避免观察 Hook 阻断正常工具调用。
- 受保护的 v1.0.0 → v1.1.0 迁移：保留旧程序，事务备份并切换启动器，失败回滚恢复可执行权限；启动器隔离加载安装目录，避免当前项目覆盖已安装代码。

## 下载与安装

附件包含源码 ZIP、源码 tar.gz、独立 Skill ZIP 和 SHA256SUMS.txt。先校验 SHA-256；独立 Skill 仍需要完整 CLI。

新安装：

```sh
python3 -B install.py --dry-run
python3 -B install.py
```

已有 v1.0.0 安装时，在新源码解压目录运行新版本升级器：

```sh
python3 -B -m chorotheia upgrade --global-install --source "$PWD" --dry-run
python3 -B -m chorotheia upgrade --global-install --source "$PWD"
~/.chorotheia/bin/chorotheia --version
```

安装文件被用户修改时拒绝覆盖；修改过的注册 Skill/Hooks 保留并报告。项目历史检查点不重写，私有记忆与备份保留。详见 docs/OPERATIONS.md。

## 验证与边界

本地隔离测试和 Linux/macOS 发布工作流验证源码及确定性归档，机器可读结果见 docs/verification.json。真实账户只进行只读额度查询；额度耗尽和模型失败使用合成夹具，不耗尽真实额度。

新增 UserPromptSubmit、PostToolUse、PreModelRequest、PostModelRequest 需要 Codex 原生信任审阅。模型请求钩子仅提供诊断，模型可见提醒通过支持的事件和恢复入口发送；无法打断长模型请求，也不能保证单次大请求不会跨过阈值。

对话观察默认关闭，首次绑定从当前末尾开始。候选为启发式推断，必须核对；过期、重置或不可用的额度证据为未知。自动讨论/额度适配目前仅验证 Codex，Antigravity/Copilot 继续使用阶段检查点降级。真实跨服务自动接力尚未联调。

恢复不恢复业务源码或未保存文件；敏感过滤为启发式；合作锁不能消除外部编辑器的全部竞态。未知旧格式拒绝猜测迁移。既有 v1.0.0 标签和附件保持不变。商标查重尚未完成，未发布到 PyPI/npm。
