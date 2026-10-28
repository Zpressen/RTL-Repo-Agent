import { expect, test } from "vitest";
import { validationSummary } from "./validation-summary";
import type { Validation } from "./state";

test("per-output errors stay separate from sample counts", () => {
  const v = {
    simulation_completed: true,
    verdict: "fail",
    total_samples: null,
    mismatched_samples: null,
    signal_mismatches: [
      { signal: "text_out", count: 287 },
      { signal: "done", count: 12 },
    ],
  } as Validation;
  expect(validationSummary(v)).toBe("text_out：287 次差异 · done：12 次差异");
  expect(
    validationSummary({ ...v, total_samples: 222, mismatched_samples: 2 }),
  ).toBe("2 / 222 不匹配采样");
  expect(validationSummary({ ...v, simulation_completed: false })).toContain(
    "未完成仿真",
  );
  expect(
    validationSummary({
      ...v,
      kind: "edit_only",
      simulation_completed: false,
      verdict: "unverified",
    }),
  ).toBe("修改已保留 · 未单独验证");
  expect(
    validationSummary({ ...v, verdict: "pass", signal_mismatches: [] }),
  ).toBe("验证通过 · 未记录总采样数");
});
