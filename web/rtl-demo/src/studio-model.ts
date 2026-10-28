import type { Bundle, Panel, ReplayEvent, Run, Validation } from "./state";
export const stepDefs: { id: string; name: string; panel: Panel }[] = [
  { id: "spec", name: "规格解析", panel: "spec" },
  { id: "architecture", name: "架构规划", panel: "architecture" },
  { id: "rtl", name: "RTL 生成", panel: "code" },
  { id: "syntax", name: "语法检查", panel: "code" },
  { id: "verify", name: "仿真验证", panel: "verify" },
  { id: "diagnose", name: "根因定位", panel: "repair" },
  { id: "repair", name: "自动修复", panel: "repair" },
  { id: "complete", name: "最终复验", panel: "verify" },
];
export function stepForPanel(
  panel: Panel,
  step?: string,
  validationKind?: string,
) {
  if (stepDefs.some((s) => s.id === step && s.panel === panel)) return step!;
  return panel === "verify"
    ? validationKind === "final_system"
      ? "complete"
      : "verify"
    : panel === "code"
      ? "rtl"
      : panel;
}
export function eventStep(e: ReplayEvent) {
  return e.text.includes("语法检查未通过") ? "syntax" : e.stage;
}
export function studioModel(
  b: Bundle,
  run?: Run | null,
  throughSequence?: number,
) {
  const allEvents = run ? run.events || [] : b.events;
  const events =
    throughSequence === undefined
      ? allEvents
      : allEvents.filter((e) => e.sequence <= throughSequence);
  const seenIds = new Set(events.map((e) => e.validation_id));
  const allVals = run ? run.validations : b.validations;
  const vals =
    throughSequence === undefined
      ? allVals
      : allVals.filter((v) => seenIds.has(v.validation_id));
  const trials = events.filter((e) => e.trial_no != null);
  const steps = stepDefs.map((d) => {
    const diagnoses =
      run?.origin === "historical"
        ? (run.attempts || []).filter(
            (a) =>
              a.diagnosis?.status === "recorded_hypothesis" &&
              (throughSequence === undefined ||
                events.some((e) => e.trial_no === a.trial_no)),
          )
        : [];
    const preEdit = diagnoses.filter(
      (a) => a.diagnosis?.recorded_at === "before_edit",
    ).length;
    const es = events.filter((e) => eventStep(e) === d.id);
    const failure = vals.find(
      (v) => v.verdict === "fail" && v.first_failure_ticks,
    );
    const sim = vals.filter(
      (v) => v.simulation_completed && v.kind !== "final_system",
    );
    const source =
      d.id === "diagnose" && diagnoses.length
        ? "recorded_diagnosis"
        : es.length
          ? "original_event"
          : (d.id === "diagnose" && failure) ||
              (d.id === "verify" && sim.length)
            ? "report_summary"
            : "unrecorded";
    const refs = es.flatMap((e) => (e.validation_id ? [e.validation_id] : []));
    const results = vals.filter((v) => refs.includes(v.validation_id));
    return {
      ...d,
      events: es,
      source,
      summary:
        (d.id === "diagnose" && diagnoses.length
          ? `已保存 ${preEdit} 条修改前判断` +
            (diagnoses.length > preEdit
              ? `，${diagnoses.length - preEdit} 条提交验证理由`
              : "")
          : "") ||
        es.at(-1)?.text ||
        (d.id === "verify" && sim.length
          ? "已有 " + sim.length + " 条详细仿真记录 · 依据报告整理"
          : source === "report_summary"
            ? "已有失败报告，未保存独立根因判断"
            : "未单独记录"),
      result:
        d.id === "diagnose" && diagnoses.length
          ? "recorded"
          : results.length
            ? results.at(-1)!.verdict
            : d.id === "verify" && sim.length
              ? sim.at(-1)!.verdict
              : es.at(-1)?.text.includes("语法检查未通过")
                ? "fail"
                : es.length
                  ? "recorded"
                  : "unknown",
      validation_id:
        es.at(-1)?.validation_id ||
        (d.id === "verify" && sim.length
          ? sim.at(-1)?.validation_id
          : source === "report_summary"
            ? failure?.validation_id
            : undefined),
    };
  });
  return {
    steps,
    trials,
    trialCount: run ? (run.attempts?.length ?? null) : b.trial_count,
    moduleCount: run ? (run.modules?.length ?? 0) : b.modules.length,
    final: [...vals]
      .reverse()
      .find((v: Validation) => v.kind === "final_system"),
  };
}
