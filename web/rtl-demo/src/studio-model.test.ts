import { it, expect } from "vitest";
import { studioModel } from "./studio-model";
const fixtures = import.meta.glob("../public/cases/*/manifest.json", {
  eager: true,
  import: "default",
});
const load = (id: string) =>
  fixtures["../public/cases/" + id + "/manifest.json"] as any;
it("projects real records without inventing eight executions", () => {
  const b = load("e203"),
    m = studioModel(b);
  expect(m.steps).toHaveLength(8);
  expect(m.trials).toHaveLength(9);
  expect(b.events).toHaveLength(13);
  expect(m.steps.find((s) => s.id === "diagnose")?.source).toBe(
    "report_summary",
  );
  expect(b.events.every((e: any) => e.observed_at === null)).toBe(true);
  expect(m.trials.filter((e) => e.validation_id)).toHaveLength(2);
});
it("does not fabricate missing AES repair or statistics", () => {
  const m = studioModel(load("aes_cipher_system_hard"));
  expect(m.steps.find((s) => s.id === "repair")?.events).toHaveLength(0);
  expect(m.trialCount).toBeNull();
});

it("does not reveal a future successful attempt while replaying failure", () => {
  const b = load("e203");
  const fail = b.events.find((e: any) => e.trial_no === 5);
  const m = studioModel(b, null, fail.sequence);
  expect(m.final).toBeUndefined();
  expect(m.steps.find((s) => s.id === "repair")?.result).toBe("fail");
  expect(m.trials.some((e) => e.trial_no === 9)).toBe(false);
});
