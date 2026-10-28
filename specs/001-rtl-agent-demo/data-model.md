# Data Model: RTL 演示工作台

## 存储边界

计算后台同机 SQLite 保存状态和索引，本地文件保存大产物。公网 Caddy 仅得到筛选后的不可变历史包。时间记录 UTC，界面按 Asia/Shanghai 展示；仿真时间使用整数 tick 和独立 timescale，不与真实时间混用。

## 实体

| 实体 | 核心字段 | 关系与约束 |
| --- | --- | --- |
| Case | case_id=e203, title, spec_artifact_id, planner_top, dut_alias, verifier_profile_id, default_bundle_id | 首版只有一个；外部根路径仅服务端 registry 保存 |
| Session | session_id, case_id, selected_run_id, selected_version_id, selected_validation_id, browsing_mode, last_event_id, created_at | 当前浏览选择与活动 operation 独立；使用不可预测标识与服务端会话 cookie |
| Message | message_id, session_id, sequence, role, content, context_ref, state, evidence_refs, operation_id, created_at | sequence 在会话内唯一；上下文引用记录创建时选中目标，不能随页面切换漂移 |
| Run | run_id, case_id, origin, source_run_id, input_version_id, spec_hash, config_fingerprint, stage, state, created_at, completed_at | origin=historical/live；实时 run 目录独立，配置指纹排除密钥原文 |
| Operation | operation_id, session_id, kind, target_version_id, run_id, idempotency_key, request_digest, state, result_verdict, error_code, worker_identity, started_at, finished_at | kind=generate_and_verify/verify/fix；全局最多一个 accepted/running；同一幂等键且相同payload返回原操作 |
| RTLVersion | version_id, run_id, parent_version_id, tree_sha256, file_manifest, disposition, created_at | 文件清单排序后含相对路径、长度与sha256；一旦被验证引用即不可变 |
| Validation | validation_id, run_id, version_id, kind, verifier_fingerprint, simulation_completed, verdict, total_samples, mismatched_samples, internal_mismatch_count, trial_no, report_artifact_id, waveform_artifact_id, first_failure_ticks | kind=syntax/candidate/final_system；指标可null，不能用0代缺失；PASS须关联对应系统报告 |
| Artifact | artifact_id, kind, sha256, size_bytes, relative_storage_key, owner_ref, exposure, source_binding | 路径只在服务端使用；exposure=private/display；浏览器只使用白名单artifact_id |
| RepairAttempt | attempt_id, run_id, trial_no, candidate_version_id, baseline_version_id, validation_id, decision | decision=pending/accepted/rolled_back；trial可只完成lint，不能因此绑定克隆VCD |
| Event | event_id, session_id, run_id, operation_id, type, payload, origin, observed_at | 单调递增持久ID；历史可无原始时间，回放延迟单独保存，不补造运行时间 |
| Bundle | bundle_id, case_id, schema_version, source_run_id, spec_fingerprint, verifier_fingerprint, validations, artifacts, events, manifest_sha256 | 导入完成后冻结；静态包与后台均使用同一 bundle_id，不能混版 |
| WaveformIndex | validation_id, waveform_sha256, timescale, first_tick, last_tick, allowed_signals, layout_fingerprint, comparison_policy, marker_status | 每个waveform hash缓存一次；layout必须匹配受信testbench与VCD宽度 |

`context_ref` 为 `{case_id, run_id, version_id, validation_id, module_id?, signal_id?, time_range?}`；消息和操作所用的上下文独立于随后变更的 Session 选择。

## 标识与完整性

- 所有实时ID不可预测；历史导入保留source candidate/revision/trial作为溯源字段，不把服务器路径当ID。
- `tree_sha256` 使用规范化的有序文件清单计算，文件内容按原始字节计算；include定义文件也是输入的一部分。
- 同一RTL版本允许多次验证，不允许用version_id代替validation_id。报告、VCD与配套测试配置属于验证记录，不仅仅属于run。
- 实时运行的 verifier_fingerprint 是固定测试环境文件清单摘要，覆盖脚本、testbench、golden、stimulus、头文件及模拟兼容改动。历史记录可能只有已保存的脚本/testbench绑定，此时记录 binding_level=recorded_candidate，缺失依赖指纹明确标为溯源限制；不能补填当前文件摘要冒充旧值。完整新运行使用 binding_level=full_input_manifest。
- 静态展示日志可以脱敏，但分别保存 source_sha256 与 display_sha256。后台保留原始证据，展示脱敏不得修改计数、判定和仿真时间。
- SQL唯一约束：Message(session_id,sequence)；Operation(session_id,idempotency_key)；RepairAttempt(run_id,trial_no)；仅accepted/running操作占用唯一全局槽。事务内同时检查请求digest和活动槽。
- 相同幂等键但payload不同返回冲突；用户想重新执行相同操作须使用新幂等键，刷新恢复不创建新键。
- SQLite只放计算机本地磁盘；完成状态、artifact绑定和相应Event写在同一事务中，文件先写临时文件并原子发布。

## 状态转换

### Operation

```text
accepted -> running -> completed
                    -> failed
                    -> timed_out
                    -> interrupted
```

completed 表示操作流程执行结束，result_verdict 可为 pass/fail/unverified/not_applicable。仿真跑完但不匹配属于 completed + fail；编译器或模型崩溃属于 failed；没有系统证据不能产生pass。accepted 仅表示登记并取得唯一槽，尚未领取的操作可首次启动；没有队列产品界面。

API服务重启不重放RTL操作。worker服务停止时清理其整个运行进程组；重新启动后先将旧running标为interrupted并核对终态文件，再接受新工作，不自动恢复模型会话或重新生成。仅当已有终态文件hash和输入绑定均正确，才可导入该次已完成结果。

### Run

```text
created -> planning -> generating -> verifying -> completed
                                           -> repairing -> verifying
任意执行阶段 -> failed / timed_out / interrupted
```

具体stage可以细分，但图上只呈现已有事件；未触发repair显示未触发。Run.state与最终验证verdict分开。

### RTLVersion / RepairAttempt

```text
candidate -> accepted
          -> rolled_back
```

回滚表示该候选未成为继续执行的基线，候选快照及失败报告仍保留；历史版本禁止原位修改。fix从选中失败版本派生新run，成功后也不覆盖历史bundle。

### Message

```text
received -> replying -> answered / clarification / failed / interrupted
```

每会话最多一个 replying 模型调用；新请求繁忙时返回明确状态。聊天进程崩溃或API重启后不自动重提写入意图，已登记operation不受重复消息影响。

## 采样与波形

`WaveWindow` 和 `SampleMarker` 格式见 [contracts/evidence.md](contracts/evidence.md)。marker只表达测试平台采样判定，不包含缺失的active区采样数据。

导入接受条件：对应trial确有simulation_completed；报告统计完整且无冲突；RTL/报告/VCD关联可确认；stats布局识别并且其最终clocks/errors与报告一致。若stats不支持，可保存可信报告与原始波形，但marker_status=unsupported；若识别成功却计数冲突则evidence_inconsistent，禁止展示为已核验的波形配对。

缺少RTL/报告/VCD核心关联或对应testbench识别依据的历史产物，只能作为标明限制的参考材料，不得用于可信对比。已确认核心候选绑定、但未保存全部外部依赖指纹的历史记录可用于带溯源范围说明的修复前后比较，不能声称已经完整复现原环境。现场操作必须重新核验当前完整测试环境，并复制完整可编译RTL版本。首个E203演示包必须通过这些导入门槛。
