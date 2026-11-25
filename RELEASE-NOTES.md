# Chorotheia v1.0.0

**Memory beyond context.**

Universal Agent Context & Memory System · One memory. Any agent.

让记忆超越上下文的边界。

## 首个正式版本

- Local-first、Agent-agnostic 的 Python 3.9+ CLI，运行只使用标准库、Markdown、JSON 与只读 Git；没有数据库、守护进程或默认云端记忆服务。
- 新旧项目 auto/new/retrofit 初始化，现有文档与代码保留，冲突隔离与幂等补充。
- 持久化记忆、不可变检查点、L0/L1 恢复、来源检索、逻辑归档及跨 Agent 交接笔记。
- Core、Bootstrap、Memory、Checkpoint、Restore、Handoff、Guard、Compact、Recall、Hooks、Adapters、Doctor 十二个正式功能模块。
- 独占创建、原子写入、fsync、合作文件锁、SHA-256 完整性验证、私有凭据、事务回滚、保守修复、维护升级与安全卸载。
- Codex、Antigravity、Copilot 的能力明确接入，以及原 Universal Handoff 协议 v1 导出兼容。
- 正式字标、品牌定义、安装说明、操作文档、逐项验证记录、确定性源码归档与 SHA-256 校验文件。

## 安装

下载 `chorotheia-1.0.0-source.zip` 或 `.tar.gz`，依据 `SHA256SUMS.txt` 校验，解压后运行：

```sh
python3 -B install.py --dry-run
python3 -B install.py
~/.chorotheia/bin/chorotheia doctor
```

安装目录为 `~/.chorotheia/`。仅 Skill 压缩包包含指引，完整功能仍需安装 CLI。已有配置冲突会保留并报告，不自动覆盖或批准原生 Hook 信任。

## 验证范围与已知限制

本机 62 项测试已通过，其中 58 项核心隔离验收及 4 项归档与标签保护测试，并由仓库发布流程在 macOS/Linux 重新执行。逐项结果见仓库文档和对应 Actions 运行记录，不将未执行的检查列为通过。

原生 Hooks 自动触发尚未端到端验收；Codex 需要原生信任审阅，Antigravity 压缩专用事件未确认，Copilot 旧 Local harness/远程环境不作兼容承诺。真实跨服务自动接力尚未联调。Hook 只能保存已记录状态，不能读取隐藏思考或未保存内容。

敏感过滤为启发式；外部编辑器不受合作锁约束，最终检查与替换/删除之间仍有极小竞态。恢复不恢复业务源码，compact 不删除历史原件。未知旧格式及缺少本机私有凭据的跨机器导入有明确限制。

商标查重尚未完成；品牌采用既定名称，不宣称注册商标。未另行新增开源许可，未发布到 PyPI/npm。详细范围见 README 和操作文档。
