import type { Validation } from "./state";

export function validationSummary(v: Validation) {
  if (v.kind === "edit_only") return "修改已保留 · 未单独验证";
  if (!v.simulation_completed) return "语法检查失败 · 未完成仿真";
  if (v.total_samples != null)
    return `${v.mismatched_samples} / ${v.total_samples} 不匹配采样`;
  if (v.signal_mismatches?.length)
    return v.signal_mismatches
      .map((s) => `${s.signal}：${s.count} 次差异`)
      .join(" · ");
  return v.verdict === "pass"
    ? "验证通过 · 未记录总采样数"
    : "报告未记录采样统计";
}
