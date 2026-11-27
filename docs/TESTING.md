# 测试与验证范围

2026-11-27，macOS arm64、Python 3.9.6。v1.2.0 运行 **153 项测试，全部通过**，无失败、错误或跳过（此前 117 项、本地路径迁移 12 项、超长扫描 8 项、本次恢复 14 项及 1.1 前驱迁移 2 项）。测试仅操作临时项目和临时配置目录，使用标准库、本地进程和合成 Agent 输入；不发送真实模型请求。

机器可读记录见 [verification.json](verification.json)。含个人绝对路径的本机安装记录、备份、原生探测输出和项目记忆未公开。

本次 8 项回归覆盖大于 1 MiB 的工具结果与可见消息、分段写入、8 MiB 解析上限之外的有界排空、额度提醒、来源归属不明时不导入讨论、游标锚点改写拒绝，以及旧错误恢复时保留核对位置和模型失败标记。另用已有原生会话的隔离私有状态回放，在 31 轮内穿过 4 条大于 1 MiB 的记录并读到文件末尾，未产生缺口；真实项目记忆及真实私有监测状态在沙盒回放前后哈希一致。正式安装维护升级后，也已从原游标补读同一会话，积压与来源读取错误清除，未确认候选讨论或清除失败标记。以上不代表过去未发出的额度提醒已补发。

覆盖新旧项目、重复初始化、文档冲突、符号链接与硬链接、路径穿越、并发写锁、原子创建、外部改动保留、进程中断恢复、回滚、敏感模式过滤、Git 暂存/未暂存/未跟踪保护、恢复、接力笔记、协议导出、归档/检索、修复、局部维护升级和安全卸载。临时 Git 提交只用于构造历史夹具。

此前本机正式安装有 31 项冒烟核验通过，正式安装未实际卸载；这不代表原生 Agent 生命周期验收完成。2026-11-26 本机 Codex 已信任四事件并观察到启动注入、压缩前检查点、压缩后注入和结束检查点；这项本机会话证据独立于临时夹具测试，不代表其他版本或机器已验证；Antigravity/Copilot 的真实会话触发与跨服务自动接力未验收。原 Handoff 校验器已接受导出的协议 v1 结果，没有启动控制器。

POSIX 锁仅约束合作写者，不能消除外部编辑器最终检查与替换/删除之间的极小竞态；敏感过滤是启发式；未知旧格式和缺少本机所有权凭据的可移植记忆有明确限制。详见 [操作说明](OPERATIONS.md)。

本次恢复回归覆盖下一轮提示注入、同一失败去重、压缩与启动重载、只读有界计划、失败与讨论独立确认、过期令牌、排除工具记录后的稳定令牌、恢复确认事务回滚、自动快照不可确认恢复、编辑过的检查点保留、监测关闭时降级和低预算优先加载。v1.1.0 全局及项目迁移分别验证旧程序、私有观察和检查点保留。Skill 通过官方 quick_validate；验证依赖仅在临时目录安装，不属于 CLI 运行依赖。

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
| 48 | test_version_1_0_project_upgrade_preserves_checkpoint | passed |
| 49 | test_version_1_1_project_upgrade_preserves_checkpoint | passed |
| 50 | test_existing_hook_configuration_is_not_overwritten | passed |
| 51 | test_global_previews_do_not_open_write_locks | passed |
| 52 | test_global_uninstall_dry_run_zero_change | passed |
| 53 | test_hook_configs_use_native_schemas_and_escaped_launcher | passed |
| 54 | test_install_backups_preserves_configs_launcher_and_sandbox_uninstall | passed |
| 55 | test_install_collision_refused | passed |
| 56 | test_install_dry_run_creates_nothing | passed |
| 57 | test_installer_failure_cleans_new_registrations_only | passed |
| 58 | test_invalid_maintenance_bundle_preserves_installation | passed |
| 59 | test_local_maintenance_upgrade_is_hashed_backed_up_and_idempotent | passed |
| 60 | test_maintenance_update_carries_license_and_preserves_user_edits | passed |
| 61 | test_private_home_permissions_enforced | passed |
| 62 | test_version_1_0_global_upgrade_switches_launcher_and_preserves_state | passed |
| 63 | test_version_1_1_global_upgrade_retains_old_release_and_monitor | passed |
| 64 | test_version_upgrade_refuses_modified_launcher | passed |
| 65 | test_version_upgrade_rollback_restores_executable_permissions | passed |
| 66 | test_cli_goal_phase_and_freshness | passed |
| 67 | test_complete_sentences_and_atomic_command_entries | passed |
| 68 | test_corrupt_and_edited_checkpoints_cannot_claim_reviewed | passed |
| 69 | test_discussion_phase_requires_explicit_completion | passed |
| 70 | test_first_items_reserved_before_extra_next_steps | passed |
| 71 | test_head_movement_detected_even_when_tree_matches | passed |
| 72 | test_large_changes_and_external_symlinks_do_not_get_read | passed |
| 73 | test_legacy_and_initial_snapshots_never_become_reviewed | passed |
| 74 | test_long_chinese_summary_cannot_hide_next_blocker_decision_or_test | passed |
| 75 | test_memory_writes_do_not_invalidate_review | passed |
| 76 | test_non_git_review_remains_explicit_but_coverage_unknown | passed |
| 77 | test_review_preview_does_not_change_stage_or_private_receipt | passed |
| 78 | test_same_dirty_status_content_changes_require_review | passed |
| 79 | test_snapshot_preserves_goal_completed_phase_and_test_reports | passed |
| 80 | test_tiny_budgets_keep_safety_source_and_omission_notice | passed |
| 81 | test_unsafe_or_sensitive_changed_content_is_unknown | passed |
| 82 | test_untracked_content_and_staging_changes_detected | passed |
| 83 | test_acknowledgement_rolls_back_if_checkpoint_transaction_fails | passed |
| 84 | test_busy_observation_hook_does_not_block_tools_or_write_state | passed |
| 85 | test_checkpoint_without_review_keeps_discussion_pending | passed |
| 86 | test_cli_configuration_and_preview_zero_writes | passed |
| 87 | test_disabled_monitor_does_not_open_untrusted_transcript | passed |
| 88 | test_duplicate_events_do_not_duplicate_messages | passed |
| 89 | test_exact_review_token_clears_only_acknowledged_discussion | passed |
| 90 | test_exhausted_quota_before_request_snapshots_known_notes | passed |
| 91 | test_explicit_quota_refresh_does_not_start_a_model | passed |
| 92 | test_failed_request_still_snapshots_when_transcript_is_unsafe | passed |
| 93 | test_failure_acknowledgement_requires_explicit_token | passed |
| 94 | test_failure_snapshot_preserves_notes_and_marks_unsummarized_without_model | passed |
| 95 | test_fixed_scan_resumes_old_error_without_resetting_review_or_failure | passed |
| 96 | test_hook_additional_context_is_advisory_and_not_a_block | passed |
| 97 | test_large_partial_record_waits_for_newline_without_duplicate_discussion | passed |
| 98 | test_large_tool_output_does_not_hide_quota_hook_reminders | passed |
| 99 | test_large_visible_message_retains_offsets_and_needs_explicit_review | passed |
| 100 | test_maintenance_adds_events_without_touching_existing_definitions_or_trust | passed |
| 101 | test_maintenance_preserves_modified_native_hooks | passed |
| 102 | test_malformed_long_record_does_not_hide_later_quota_or_import_unknown_context | passed |
| 103 | test_malformed_source_remains_pending_and_cannot_be_acknowledged | passed |
| 104 | test_native_rpc_sends_only_initialize_and_rate_limit_read | passed |
| 105 | test_native_rpc_timeout_is_bounded_and_process_is_reaped | passed |
| 106 | test_other_project_context_is_not_imported | passed |
| 107 | test_over_cap_drain_still_refuses_cursor_anchor_rewrite | passed |
| 108 | test_over_cap_partial_record_keeps_drain_state_until_terminated | passed |
| 109 | test_over_cap_record_drains_with_explicit_gap_and_later_quota | passed |
| 110 | test_oversized_hook_event_is_diagnostic_not_blocking | passed |
| 111 | test_partial_record_is_not_consumed_until_newline | passed |
| 112 | test_path_identity_symlink_and_hardlink_refused | passed |
| 113 | test_private_candidates_never_enter_project_checkpoint | passed |
| 114 | test_prospective_binding_does_not_claim_old_history_reviewed | passed |
| 115 | test_quota_passive_observation_and_notice_deduplication | passed |
| 116 | test_stale_missing_reset_and_invalid_quota_are_unknown | passed |
| 117 | test_stale_private_state_write_preserves_external_change | passed |
| 118 | test_stale_review_token_cannot_acknowledge_new_messages | passed |
| 119 | test_thresholds_both_windows_and_multiple_buckets | passed |
| 120 | test_truncation_and_anchor_rewrite_preserve_cursor | passed |
| 121 | test_visible_only_candidates_have_source_offsets_and_redaction | passed |
| 122 | test_warning_and_pending_discussion_survive_restore_budget | passed |
| 123 | test_automatic_snapshot_cannot_acknowledge_recovery | passed |
| 124 | test_compaction_reloads_recovery_even_after_delivery | passed |
| 125 | test_edited_checkpoint_preserved_and_recovery_does_not_claim_completion | passed |
| 126 | test_monitor_disabled_does_not_start_recovery_or_any_model | passed |
| 127 | test_new_failure_after_recovery_delivers_a_new_plan | passed |
| 128 | test_next_prompt_delivers_plan_once_and_keeps_failure_pending | passed |
| 129 | test_normal_open_phase_and_discussion_do_not_trigger_full_recovery | passed |
| 130 | test_recover_cli_is_read_only_and_bounded | passed |
| 131 | test_recovery_marker_survives_small_restore_budget | passed |
| 132 | test_recovery_result_and_failure_ack_roll_back_together | passed |
| 133 | test_recovery_token_rejects_new_source_or_git_changes | passed |
| 134 | test_recovery_without_result_tests_or_current_token_refused | passed |
| 135 | test_tool_only_cursor_advances_do_not_invalidate_recovery_token | passed |
| 136 | test_verified_recovery_checkpoint_acknowledges_failure_only | passed |
| 137 | test_archives_are_deterministic_and_private_state_excluded | passed |
| 138 | test_existing_tag_cannot_be_retargeted | passed |
| 139 | test_manifest_traversal_and_symlink_are_refused | passed |
| 140 | test_source_and_standalone_skill_archives_carry_the_license | passed |
| 141 | test_tampered_source_is_refused | passed |
| 142 | test_altered_manifest_or_memory_cannot_be_adopted | passed |
| 143 | test_existing_previous_root_is_not_treated_as_move | passed |
| 144 | test_failure_rolls_back_both_bindings | passed |
| 145 | test_import_without_real_private_receipt_is_refused | passed |
| 146 | test_missing_or_uncommitted_journal_is_refused | passed |
| 147 | test_occupied_destination_receipt_is_preserved | passed |
| 148 | test_pending_old_transaction_prevents_relocation | passed |
| 149 | test_preview_has_zero_project_and_private_writes | passed |
| 150 | test_real_receipt_relocation_preserves_all_project_bytes | passed |
| 151 | test_second_move_uses_committed_relocation_provenance | passed |
| 152 | test_source_receipt_requires_exact_committed_bytes | passed |
| 153 | test_subsequent_checkpoint_does_not_break_repeat_relocation | passed |
