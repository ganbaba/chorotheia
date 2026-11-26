# 测试与验证范围

2026-11-26，macOS arm64、Python 3.9.6。对包含字段优先恢复与进度复核提示的维护实现运行 **117 项测试，全部通过**，无失败、错误或跳过（原 112 项及本次版本迁移、回滚权限和观察锁竞争 5 项）。测试仅操作临时项目和临时配置目录，使用标准库、本地进程和合成 Agent 输入；不发送真实模型请求。

机器可读记录见 [verification.json](verification.json)。含个人绝对路径的本机安装记录、备份、原生探测输出和项目记忆未公开。

覆盖新旧项目、重复初始化、文档冲突、符号链接与硬链接、路径穿越、并发写锁、原子创建、外部改动保留、进程中断恢复、回滚、敏感模式过滤、Git 暂存/未暂存/未跟踪保护、恢复、接力笔记、协议导出、归档/检索、修复、局部维护升级和安全卸载。临时 Git 提交只用于构造历史夹具。

此前本机正式安装有 31 项冒烟核验通过，正式安装未实际卸载；这不代表原生 Agent 生命周期验收完成。2026-11-26 本机 Codex 已信任四事件并观察到启动注入、压缩前检查点、压缩后注入和结束检查点；这项本机会话证据独立于临时夹具测试，不代表其他版本或机器已验证；Antigravity/Copilot 的真实会话触发与跨服务自动接力未验收。原 Handoff 校验器已接受导出的协议 v1 结果，没有启动控制器。

POSIX 锁仅约束合作写者，不能消除外部编辑器最终检查与替换/删除之间的极小竞态；敏感过滤是启发式；未知旧格式和缺少本机所有权凭据的可移植记忆有明确限制。详见 [操作说明](OPERATIONS.md)。

| # | 测试名称 | 结果 |
|---|---|---|
| 1 | test_actual_process_exit_recovery | passed |
| 2 | test_agent_file_conflict_uses_fallback | passed |
| 3 | test_all_conflict_paths_preserved | passed |
| 4 | test_ambiguous_crash_record_is_preserved | passed |
| 5 | test_atomic_publish_never_overwrites | passed |
| 6 | test_checkpoint_restore_preserves_task | passed |
| 7 | test_cli_end_to_end_commands | passed |
| 8 | test_compact_and_recall_retain_history | passed |
| 9 | test_compare_and_swap_rejects_stale_update | passed |
| 10 | test_crash_journal_blocks_then_recovers | passed |
| 11 | test_cross_process_exclusive_lock | passed |
| 12 | test_dry_run_missing_home_not_created | passed |
| 13 | test_dry_run_zero_project_and_home_writes | passed |
| 14 | test_exclusive_same_bytes_failure_never_deletes_existing | passed |
| 15 | test_explicit_new_refuses_nonempty | passed |
| 16 | test_foreign_agent_namespace | passed |
| 17 | test_full_project_uninstall_removes_only_owned | passed |
| 18 | test_git_dirty_staged_untracked_and_index_unchanged | passed |
| 19 | test_handoff_preserves_existing_controller_and_business | passed |
| 20 | test_history_evidence_separates_unknown | passed |
| 21 | test_hook_auto_init_can_be_disabled | passed |
| 22 | test_hook_git_auto_init | passed |
| 23 | test_hooks_non_git_uninitialized_noop | passed |
| 24 | test_init_external_change_triggers_integrity_rollback | passed |
| 25 | test_lock_symlink_refused | passed |
| 26 | test_manifest_path_escape_refused | passed |
| 27 | test_missing_checkpoint_recovered_from_verified_history | passed |
| 28 | test_modified_manifest_untrusted_ownership_refused | passed |
| 29 | test_modified_memory_blocked_then_explicitly_adopted | passed |
| 30 | test_native_hook_payload_adapters | passed |
| 31 | test_new_init_structure_and_integrity | passed |
| 32 | test_parent_symlink_injection_refused | passed |
| 33 | test_path_traversal_and_symlink_root_refused | passed |
| 34 | test_private_state_outside_repo | passed |
| 35 | test_project_uninstall_preserves_original_and_modified | passed |
| 36 | test_receipt_rolls_back_with_manifest | passed |
| 37 | test_repeated_init_exact_idempotence | passed |
| 38 | test_restore_budget_and_secret_redaction | passed |
| 39 | test_retrofit_preserves_existing_bytes_and_modes | passed |
| 40 | test_rollback_preserves_concurrent_external_edit | passed |
| 41 | test_schema_upgrade_backed_up_and_idempotent | passed |
| 42 | test_sensitive_patterns | passed |
| 43 | test_symlink_leaf_and_hardlink_refused | passed |
| 44 | test_symlink_namespace_does_not_escape | passed |
| 45 | test_transaction_failure_rolls_back_only_ours | passed |
| 46 | test_universal_handoff_protocol_export_exact_shape | passed |
| 47 | test_untrusted_unsupported_protocol_ids_refused | passed |
| 48 | test_existing_hook_configuration_is_not_overwritten | passed |
| 49 | test_global_previews_do_not_open_write_locks | passed |
| 50 | test_global_uninstall_dry_run_zero_change | passed |
| 51 | test_hook_configs_use_native_schemas_and_escaped_launcher | passed |
| 52 | test_install_backups_preserves_configs_launcher_and_sandbox_uninstall | passed |
| 53 | test_install_collision_refused | passed |
| 54 | test_install_dry_run_creates_nothing | passed |
| 55 | test_installer_failure_cleans_new_registrations_only | passed |
| 56 | test_invalid_maintenance_bundle_preserves_installation | passed |
| 57 | test_local_maintenance_upgrade_is_hashed_backed_up_and_idempotent | passed |
| 58 | test_maintenance_update_carries_license_and_preserves_user_edits | passed |
| 59 | test_private_home_permissions_enforced | passed |
| 60 | test_archives_are_deterministic_and_private_state_excluded | passed |
| 61 | test_existing_tag_cannot_be_retargeted | passed |
| 62 | test_manifest_traversal_and_symlink_are_refused | passed |
| 63 | test_source_and_standalone_skill_archives_carry_the_license | passed |
| 64 | test_tampered_source_is_refused | passed |

## 许可分发验证

在原有验收基础上，新增源码 ZIP、tar.gz 和独立 Skill ZIP 的 LICENSE 分发验证，以及维护升级携带许可证并保留用户编辑的验证。现有安装测试也核对新安装副本中的 LICENSE 与源文件一致。

另在临时隔离环境实际构建了 Python wheel：`License-Expression: MIT`、`License-File: LICENSE` 与嵌入的许可证正文均已核对。未修改全局 Python 环境，未发布到 PyPI。

## 归档验证

验证确定性归档、私有状态排除、源码篡改拒绝、路径穿越/符号链接拒绝和已有标签不被改写。远程平台测试结果以对应 Actions 运行记录为准。

## 字段恢复与阶段复核维护验证

新增 17 项隔离测试，包含长中文摘要下关键字段仍可加载、完整句子与不可拆命令、列表公平加载、256–2400 字节预算、初始化/旧记录保持未知、重复 Hook 保留核对基线、相同 M 状态下内容变化、未跟踪内容与暂存变化、HEAD 变化、纯讨论阶段收尾、敏感/不安全/超限输入降级、dry-run 零写入、CLI 参数与状态、Hook 保留新字段，以及损坏/外部编辑记忆拒绝信任。

| # | 测试名称 | 结果 |
|---|---|---|
| 65 | test_long_chinese_summary_cannot_hide_next_blocker_decision_or_test | passed |
| 66 | test_complete_sentences_and_atomic_command_entries | passed |
| 67 | test_first_items_reserved_before_extra_next_steps | passed |
| 68 | test_tiny_budgets_keep_safety_source_and_omission_notice | passed |
| 69 | test_legacy_and_initial_snapshots_never_become_reviewed | passed |
| 70 | test_memory_writes_do_not_invalidate_review | passed |
| 71 | test_same_dirty_status_content_changes_require_review | passed |
| 72 | test_untracked_content_and_staging_changes_detected | passed |
| 73 | test_head_movement_detected_even_when_tree_matches | passed |
| 74 | test_discussion_phase_requires_explicit_completion | passed |
| 75 | test_unsafe_or_sensitive_changed_content_is_unknown | passed |
| 76 | test_review_preview_does_not_change_stage_or_private_receipt | passed |
| 77 | test_cli_goal_phase_and_freshness | passed |
| 78 | test_snapshot_preserves_goal_completed_phase_and_test_reports | passed |
| 79 | test_corrupt_and_edited_checkpoints_cannot_claim_reviewed | passed |
| 80 | test_non_git_review_remains_explicit_but_coverage_unknown | passed |
| 81 | test_large_changes_and_external_symlinks_do_not_get_read | passed |

## 对话与额度观察维护验证

新增 31 项隔离测试，验证可见消息筛选、私有片段及来源、重复扫描、前瞻绑定、显式令牌核对、过期令牌拒绝、核对事务失败回滚、模型失败/额度耗尽仅快照已有笔记、异常来源仍保存失败状态、阈值及多窗口、过期证据降级、非阻塞提醒去重、半条 JSONL、损坏/替换/不安全来源、跨项目隔离、预算内警告、CLI 预览与参数验证、自有 Hook 维护更新和原生 RPC 最小方法集/超时清理。

本机已通过官方 account/rateLimits/read 读取真实额度，未创建模型任务。阈值越界、额度耗尽和模型失败均用合成夹具测试，不耗尽真实账户额度。新增四个 Codex Hook 仍需原生信任审阅；不能将配置解析或合成输入测试视为已完成真实限额中断验收。

| # | 测试名称 | 结果 |
|---|---|---|
| 82 | test_disabled_monitor_does_not_open_untrusted_transcript | passed |
| 83 | test_prospective_binding_does_not_claim_old_history_reviewed | passed |
| 84 | test_visible_only_candidates_have_source_offsets_and_redaction | passed |
| 85 | test_duplicate_events_do_not_duplicate_messages | passed |
| 86 | test_checkpoint_without_review_keeps_discussion_pending | passed |
| 87 | test_exact_review_token_clears_only_acknowledged_discussion | passed |
| 88 | test_stale_review_token_cannot_acknowledge_new_messages | passed |
| 89 | test_failure_snapshot_preserves_notes_and_marks_unsummarized_without_model | passed |
| 90 | test_exhausted_quota_before_request_snapshots_known_notes | passed |
| 91 | test_failure_acknowledgement_requires_explicit_token | passed |
| 92 | test_failed_request_still_snapshots_when_transcript_is_unsafe | passed |
| 93 | test_thresholds_both_windows_and_multiple_buckets | passed |
| 94 | test_stale_missing_reset_and_invalid_quota_are_unknown | passed |
| 95 | test_quota_passive_observation_and_notice_deduplication | passed |
| 96 | test_hook_additional_context_is_advisory_and_not_a_block | passed |
| 97 | test_partial_record_is_not_consumed_until_newline | passed |
| 98 | test_truncation_and_anchor_rewrite_preserve_cursor | passed |
| 99 | test_path_identity_symlink_and_hardlink_refused | passed |
| 100 | test_malformed_source_remains_pending_and_cannot_be_acknowledged | passed |
| 101 | test_other_project_context_is_not_imported | passed |
| 102 | test_acknowledgement_rolls_back_if_checkpoint_transaction_fails | passed |
| 103 | test_private_candidates_never_enter_project_checkpoint | passed |
| 104 | test_explicit_quota_refresh_does_not_start_a_model | passed |
| 105 | test_warning_and_pending_discussion_survive_restore_budget | passed |
| 106 | test_cli_configuration_and_preview_zero_writes | passed |
| 107 | test_maintenance_adds_events_without_touching_existing_definitions_or_trust | passed |
| 108 | test_maintenance_preserves_modified_native_hooks | passed |
| 109 | test_native_rpc_sends_only_initialize_and_rate_limit_read | passed |
| 110 | test_native_rpc_timeout_is_bounded_and_process_is_reaped | passed |
| 111 | test_stale_private_state_write_preserves_external_change | passed |
| 112 | test_oversized_hook_event_is_diagnostic_not_blocking | passed |

## v1.1.0 版本迁移验证

验证已知 v1.0.0 安装及 schema 1 项目迁移，保留旧程序、私有笔记和历史检查点；覆盖预览零写入、启动器权限、失败回滚、用户修改拒绝覆盖和重复升级幂等性。观察 Hook 的写锁竞争采用有限重试及非阻塞诊断。

| # | 测试名称 | 结果 |
|---|---|---|
| 113 | test_version_1_0_project_upgrade_preserves_checkpoint | passed |
| 114 | test_version_1_0_global_upgrade_switches_launcher_and_preserves_state | passed |
| 115 | test_version_upgrade_rollback_restores_executable_permissions | passed |
| 116 | test_version_upgrade_refuses_modified_launcher | passed |
| 117 | test_busy_observation_hook_does_not_block_tools_or_write_state | passed |

本地另从生成的 v1.1.0 源码 ZIP 实际新安装，并从原 v1.0.0 标签源码创建沙盒安装后升级。已确认旧程序目录、历史检查点、未完成业务文件保留，项目版本迁移及重复升级通过；此验收未升级正式全局安装。
