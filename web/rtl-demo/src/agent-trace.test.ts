import { it, expect } from "vitest";
import { traceModel, observedRun, selectedTrace } from "./agent-trace";
import { stepForPanel } from "./studio-model";
import { historyJourney } from "./state";
const fixtures = import.meta.glob("../public/cases/*/manifest.json", {
  eager: true,
  import: "default",
});
const load = () => fixtures["../public/cases/e203/manifest.json"] as any;
it("combines the recorded sources into 39 display candidates without changing their baseline identities", () => {
  const b = load(),
    r = historyJourney(b)!;
  expect(r.attempts).toHaveLength(39);
  expect(r.attempts.map((a) => a.trial_no)).toEqual(
    Array.from({ length: 39 }, (_, i) => i + 1),
  );
  expect(r.attempts[38].baseline_version_id).toBe(
    b.debug_history.runs[1].attempts[8].baseline_version_id,
  );
  expect(r.final_validation_id).toBe(
    b.debug_history.runs[1].final_validation_id,
  );
  const m = traceModel(b, r);
  expect(m.flatMap((s) => s.attempts)).toHaveLength(39);
  expect(
    m.flatMap((s) => s.attempts).find((a) => a.event.trial_no === 39)?.debug
      ?.expected_effect,
  ).toContain("Separate initial overlap");
});
it("includes every debug attempt with bound goals and decisions", () => {
  const m = traceModel(load());
  expect(m).toHaveLength(8);
  expect(m.flatMap((s) => s.attempts)).toHaveLength(9);
  const trial5 = m
    .flatMap((s) => s.attempts)
    .find((a) => a.event.trial_no === 5)!;
  expect(trial5.debug?.signals).toContain("wbck_o_wdat");
  expect(trial5.debug?.decision).toBe("accept");
});
it("limits debugging details to reached events during replay", () => {
  const b = load();
  const m = traceModel(
    b,
    null,
    b.events.find((e: any) => e.trial_no === 5).sequence,
  );
  expect(
    m.flatMap((s) => s.attempts).some((a) => a.debug?.trial_no === 9),
  ).toBe(false);
  expect(m.find((s) => s.id === "complete")?.source).toBe("unrecorded");
});
it("never borrows historical debugging for live or mismatched archives", () => {
  const b = structuredClone(load());
  b.debug_trace.source_fingerprint = "wrong";
  expect(
    traceModel(b)
      .flatMap((s) => s.attempts)
      .every((a) => !a.debug),
  ).toBe(true);
  const live: any = {
    run_id: "live",
    events: b.events,
    validations: [],
    versions: [],
  };
  expect(
    traceModel(load(), live)
      .flatMap((s) => s.attempts)
      .every((a) => !a.debug),
  ).toBe(true);
});
it("projects observed live stages only for the selected run", () => {
  const run = observedRun({ run_id: "mine", versions: [], validations: [] }, [
    { id: "2", runId: "other", stage: "complete", tag: "live", text: "PASS" },
    {
      id: "1",
      runId: "mine",
      stage: "repair",
      trialNo: 1,
      tag: "live",
      text: "候选检查中",
    },
  ]);
  expect(run.events).toHaveLength(1);
  const m = traceModel(load(), run);
  expect(m.find((s) => s.id === "repair")?.summary).toBe("候选检查中");
  expect(m.find((s) => s.id === "complete")?.source).toBe("unrecorded");
  expect(m.flatMap((s) => s.attempts).every((a) => !a.debug)).toBe(true);
});
it("selects only the requested phase, including phases sharing one panel", () => {
  const steps = traceModel(load());
  for (const step of steps)
    expect(selectedTrace(steps, step.id, step.panel)?.id).toBe(step.id);
  expect(selectedTrace(steps, "complete", "spec")?.id).toBe("spec");
  expect(selectedTrace(steps, "syntax", "repair")?.id).toBe("repair");
  expect(stepForPanel("repair", "complete")).toBe("repair");
  expect(stepForPanel("repair", "diagnose")).toBe("diagnose");
  expect(stepForPanel("verify", "repair", "final_system")).toBe("complete");
});

it("counts pre-fix hypotheses independently of candidate outcomes and replay goals", () => {
  const b = load(),
    r = historyJourney(b)!;
  const full = traceModel(b, r).find((s) => s.id === "diagnose")!;
  expect(full.name).toBe("根因定位");
  expect(full.summary).toContain("25 条修改前判断");
  expect(full.summary).toContain("6 条提交验证理由");
  expect(r.attempts[38].diagnosis?.status).toBe("unrecorded");
  const beginning = traceModel(b, r, 4).find((s) => s.id === "diagnose")!;
  expect(beginning.source).not.toBe("recorded_diagnosis");
});
