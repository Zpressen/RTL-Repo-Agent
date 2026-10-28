# Public Evidence Package Contract

日期：2026-10-20。覆盖 FR-022/023，关联版本、验证、波形及静态降级要求。此格式不是维护者 private seed，不扩大材料公开范围。

## 1. HTTP 接口

`GET /api/cases/{case_id}/evidence.zip?validation_id={after_or_single}&before_validation_id={optional_before}`

- case_id 限四个注册案例；validation_id 必选；before 可选且必须不同，最多两条验证。
- 本版只允许当前公开历史 bundle 中的详细验证及其公开闭包。同案例但不属于该公开包的私有实时记录也不能直接导出。
- 逐条核对 validation→version→run→case，公开成员资格和 artifact.exposure；不能因为持有 owner cookie 就把 private 变成公开下载。
- 接口沿用现有生产 gateway 边界。公开历史包不要求创建访客 session；解析案例以路径为准，header/query 不一致拒绝。
- GET 无模型、任务或数据库写入；ZIP 临时文件是派生产物，不更改运行记录。

成功：200 application/zip；Content-Disposition: attachment，安全文件名（已知 case 和清单 hash）；Cache-Control: no-store（API），X-Content-Type-Options: nosniff。支持分块文件响应，不在 JSON content 接口传 base64。

前端下载使用独立 Blob/文件导航处理，不使用现有强制 JSON 的 api.request 解码器；先核对状态与 content-type，错误为既有 JSON error envelope，不能把错误页保存成 ZIP。

## 2. 选择和强校验

1. 只取当前案例已发布 bundle，确认最多两条验证在其 validations 内，comparison 必须同 case；允许清楚指定的同案例 before/after，不隐式换成默认配对。
2. validation.version_id/run_id 必须与版本及运行一致，run.origin=historical；required RTL/report/spec/planner 缺失终止。
3. 对每个存储引用使用 Store.get 的公开读取和 Artifacts.file/version_path 的 path/hash 校验；source_snapshot 与 artifact RTL 字节必须匹配完整 file_manifest。
4. 固定白名单：spec、planning、rtl、report、waveform、waveform_tile。排除 raw vcd、contracts、audit、会话、提示、配置、参考 RTL 和任意目录遍历。
5. 波形归属通过 Validation.waveform_artifact_id / waveform_index_artifact_id 引用，以及 index/tile JSON 内 validation_id、version_id、waveform_sha256 联合校验；Artifact 记录本身没有这些归属字段，不要求为此迁移 artifact schema。index→tiles 闭包必须完整且所有 tile 可公开；存在却损坏/不匹配应报错，真正未记录才列 missing。
6. 显示材料中出现凭据或服务器绝对路径等不应公开内容时拒绝导出，不能修改 RTL 字节后继续声称 tree hash 相同。报告使用既有脱敏 display 字节；不重新读取私有原始 stdout。

## 3. ZIP 内容

```text
manifest.json
README.txt
spec/specification.md
planning/repo_skeleton.json
versions/<version_id>/rtl/<原相对文件名>
validations/<validation_id>/report.txt
validations/<validation_id>/waveform/index.json
validations/<validation_id>/waveform/tiles/<tile>.json   # 有分片才存在
```

共享版本可只保存一次，validation 通过清单关联；前后版同名文件不得覆盖。wave index 的 tile URL 改为包内相对路径，移除内部 storage_key/私有 artifact 引用；普通非 tiled 波形 index 直接保存公开信号数据。

README 中文说明单次/比较选择、历史材料性质、受测范围、解压后入口与波形 JSON 结构，以及“公开关键波形派生自真实 VCD；未提供完整私有原始 VCD或仿真环境”。不提供无实际执行依据的复现命令。

## 4. manifest.json（rtl-demo-evidence-v1）

| 字段 | 内容 |
| --- | --- |
| schema_version | rtl-demo-evidence-v1 |
| case_id / bundle_id / source_fingerprint | 当前公开历史包身份 |
| selection | kind=single/comparison、validation_id、before_validation_id? |
| validations[] | validation_id、run_id、version_id、kind、verdict、simulation_completed、已记录采样统计、first_failure_ticks、report artifact/hash、源 VCD hash、comparison policy、波形信号范围 |
| versions[] | version_id、run_id、tree_sha256、完整 file_manifest |
| files[] | archive_path、role、validation_ids[]、version_id?、artifact_id?、source_artifact_sha256?、source_sha256?、archive_sha256、size_bytes |
| missing[] | validation_id?、role、reason（确实未记录的可选材料） |
| exclusions[] | raw_vcd_not_public、private_runtime_not_exported 等明确范围说明 |

文件 SHA-256 对应 ZIP 解压后的实际字节。manifest 本身不在 files 中记录自身 hash，整体 ZIP hash 由静态索引或外部下载信息提供。固定排序/时间戳保证相同输入构建可重复；不以服务器当前路径/生成时间构造身份。

必须区分：Validation.waveform_sha256 为源原始 VCD hash；公开 waveform artifact 的 sha256 是派生 JSON；wave index 改写后 archive_sha256 是输出字节 hash，三者不相互替代。报告也可同时保留 source_sha256 与公开脱敏 artifact hash，但从不包含原始私有报告字节。

## 5. 资源预算和清理

默认：输入材料总量最多 64MiB（包含需重写的 JSON/README/清单预算）、最多 128 个 ZIP 条目、在线生成并发 1；压缩等级 1。输出也最多 64MiB；最终清单与 README 计入条目和输出限制。

生成前核对输入大小和清单上限；生成过程中逐文件读取、分块写入并再次核对 hash/输出预算。临时目录位于 data_root/export-tmp，权限 0700、文件 0600；在限额内构造清单所需 JSON，不将整个 ZIP 放内存。在线生成锁只覆盖构建，输出由 FileResponse 发送；限制同时存在的临时包总量 128MiB，避免慢下载绕过磁盘预算。

正常响应结束/异常/取消都要清理，断线处理不能只依赖可能不运行的成功回调；启动清理本进程不再使用的遗留文件。不能依赖 root、定时任务或新增后台服务才能清理。

## 6. 静态预生成与前端降级

export_static 复用同一 builder，预生成四案例所有已有公开详细验证的单次包与有效默认 comparison_pair 的比较包。目前为 E203 trial5/trial9/final 三个单次加 trial5→final 对比，其他案例各一个最终包，共七个。

只在导出副本 manifest 增加 evidence_packages：

```json
{
  "schema_version": "rtl-demo-evidence-index-v1",
  "single": {
    "<validation-id>": {
      "kind": "single",
      "validation_id": "<validation-id>",
      "url": "/cases/<case-id>/evidence/<zip-sha256>.zip",
      "sha256": "<zip-sha256>",
      "size_bytes": 1234
    }
  },
  "comparisons": []
}
```

比较 descriptor 增加 before_validation_id，validation_id 为 after。索引与 bundle_id/source_fingerprint 配套核对，前端优先选择精确匹配静态包；没有包才尝试在线 GET。不因为某 ZIP 下载失败就替换为另一验证；API 和静态都不可用时说明原因。

索引保存于版本化导出 manifest（以及顶层指针副本），ZIP 内容寻址，避免覆盖不同版本同名下载；不修改不可变存储 bundle 或 source_fingerprint。

## 7. 发布白名单

release.py 和 deployment.py 只允许 `cases/<registered_case>/evidence/<64位小写hex>.zip`。验证 zip 文件 hash 与导出索引一致，内部 manifest case/selection/来源也与案例包匹配。

内部校验：安全相对路径、无 symlink、无绝对路径/..、无重复条目、固定条目总数/解压字节上限；文件表 hash/大小对应实际解压条目，除 manifest 外所有条目均有清单；不允许嵌套压缩包或超范围后缀。白名单检验应流式核算，不解压到任意磁盘路径。

未知 case、无清单 ZIP、额外 ZIP 路径、private 文件及不匹配 hash 应拒绝发布。不泛开所有 .zip，也不为此允许原始 .vcd 或状态数据库进入静态包。

## 8. 错误

沿用 `{error:{code,message,...}}`，错误不包含内部路径或原始异常文本。

| HTTP | code | 含义 |
| --- | --- | --- |
| 401 | gateway_required | 未通过现有生产入口 |
| 403 | evidence_not_public | 私有记录或不可导出的材料 |
| 404 | not_found | 案例或记录不存在 |
| 409 | evidence_inconsistent | hash、绑定、材料闭包或安全内容冲突 |
| 413 | evidence_too_large | 输入、输出、条目或临时空间超限 |
| 422 | invalid_selection / case_mismatch | 参数无效、重复验证或跨案例组合 |
| 429 | export_busy | 生成资源忙；可带 Retry-After |

同来源的确实缺少可选波形允许成功并列 missing；缺失 RTL/报告不生成“完整证据包”。
