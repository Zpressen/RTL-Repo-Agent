import type { Bundle, Context, Run, Version, Validation } from "./state";
export function resolveEvidence(
  b: Bundle,
  ctx: Context,
  runs: Run[] = [],
): Context {
  if (ctx.case_id !== b.case_id) throw new Error("证据属于其他案例。");
  if (runs.some((r) => r.case_id && r.case_id !== ctx.case_id))
    throw new Error("运行属于其他案例。");
  const versions = [...b.versions, ...runs.flatMap((r) => r.versions)],
    vals = [...b.validations, ...runs.flatMap((r) => r.validations)];
  const c = { ...ctx };
  if (c.validation_id) {
    const v = vals.find((x) => x.validation_id === c.validation_id);
    if (!v) throw new Error("所选验证不存在。");
    if (
      (c.version_id && c.version_id !== v.version_id) ||
      (c.run_id && c.run_id !== v.run_id)
    )
      throw new Error("报告与版本或运行不一致。");
    Object.assign(c, { version_id: v.version_id, run_id: v.run_id });
  }
  if (c.version_id) {
    const v = versions.find((x) => x.version_id === c.version_id);
    if (!v || (c.run_id && v.run_id !== c.run_id))
      throw new Error("所选版本与运行不一致。");
    c.run_id = v.run_id;
    if (c.module_id && !v.modules.some((m) => m.module_id === c.module_id))
      throw new Error("该版本没有所选模块或文件。");
  }
  if (
    c.run_id &&
    c.run_id !== b.source_run_id &&
    !runs.some((r) => r.run_id === c.run_id)
  )
    throw new Error("所选运行不可用。");
  return c;
}
export const changedFiles = (a: Version, b: Version) =>
  [...new Set([...a.file_manifest, ...b.file_manifest].map((x) => x.path))]
    .sort()
    .filter(
      (p) =>
        a.file_manifest.find((x) => x.path === p)?.sha256 !==
        b.file_manifest.find((x) => x.path === p)?.sha256,
    );
const units: Record<string, bigint> = {
  s: 1000000000000000n,
  ms: 1000000000000n,
  us: 1000000000n,
  ns: 1000000n,
  ps: 1000n,
  fs: 1n,
};
export function convertTicks(
  t: bigint,
  a: { value: number; unit: string },
  b: { value: number; unit: string },
) {
  if (!units[a.unit] || !units[b.unit])
    throw new Error("波形时间单位无法换算。");
  const x = t * BigInt(a.value) * units[a.unit],
    y = BigInt(b.value) * units[b.unit];
  if (x % y) throw new Error("波形时间无法精确对齐。");
  return x / y;
}
export function assertWave(
  v: Validation,
  w: { validation_id: string; version_id: string; waveform_sha256: string },
) {
  if (
    v.validation_id !== w.validation_id ||
    v.version_id !== w.version_id ||
    v.waveform_sha256 !== w.waveform_sha256
  )
    throw new Error("波形与所选验证绑定不一致。");
}
