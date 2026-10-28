import { it, expect } from "vitest";
import { unifiedDiff } from "./history-diff";
it("shows separated edits without marking unchanged middle lines as replacements", () => {
  const lines = Array.from({ length: 24 }, (_, i) => "line " + i),
    changed = [...lines];
  changed[2] = "first fix";
  changed[20] = "second fix";
  const d = unifiedDiff(lines.join("\n"), changed.join("\n"), "dut.v");
  expect(d).toContain("-line 2\n+first fix");
  expect(d).toContain("-line 20\n+second fix");
  expect(d).not.toContain("-line 12");
  expect(d.match(/@@ -/g)).toHaveLength(2);
});
it("includes added and removed files", () => {
  expect(unifiedDiff("", "module dut;\nendmodule\n", "dut.v")).toContain(
    "+module dut;",
  );
  expect(unifiedDiff("module dut;\n", "", "dut.v")).toContain("-module dut;");
});
