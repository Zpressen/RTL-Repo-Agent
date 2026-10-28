import { it, expect } from "vitest";
import { resultForUse, type MemoryUse, type UseEvent } from "./stories";
import type { Run } from "./state";
it("does not borrow PASS from another run or candidate and preserves actual failure", () => {
  const use = { run_id: "run-b" } as MemoryUse;
  const event = {
    kind: "validation_observed",
    validation_id: "report-1",
    candidate_version_id: "version-b",
  } as UseEvent;
  const runs = [
    {
      run_id: "run-a",
      validations: [
        {
          validation_id: "report-1",
          run_id: "run-a",
          version_id: "version-a",
          verdict: "pass",
          simulation_completed: true,
        },
      ],
    },
  ] as Run[];
  expect(resultForUse(use, event, runs)).toBe("unverified");
  runs[0].run_id = "run-b";
  runs[0].validations[0].run_id = "run-b";
  expect(resultForUse(use, event, runs)).toBe("unverified");
  runs[0].validations[0].version_id = "version-b";
  runs[0].validations[0].verdict = "fail";
  expect(resultForUse(use, event, runs)).toBe("fail");
  expect(resultForUse(use, { kind: "applied" } as UseEvent, runs)).toBe(
    "unverified",
  );
});

import { storyScenario } from "../tests/fixtures/stories";
it("keeps synthetic PASS/FAIL, missing proof and revised-but-unused states distinct", () => {
  for (const kind of ["pass", "fail", "missing_reference"] as const) {
    const story = storyScenario(kind),
      use = story.experience.uses[0];
    expect(resultForUse(use, use.events[2], story.runs || [])).toBe(
      kind === "missing_reference" ? "unverified" : kind,
    );
  }
  const revised = storyScenario("revision");
  expect(revised.experience.memories[1].parent_revision_id).toBe(
    "synthetic-v1",
  );
  expect(revised.experience.uses).toEqual([]);
});
