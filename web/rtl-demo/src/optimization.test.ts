import { it, expect } from "vitest";
import { optimizationCopy } from "./optimization";
it("has an explicit waiting state, no invented measurement", () => {
  expect(optimizationCopy.status).toBe("PPA 数据待接入");
  expect(optimizationCopy.steps).toEqual([
    "提出设计候选",
    "功能验证",
    "同条件测量",
    "保留或放弃",
  ]);
  expect(JSON.stringify(optimizationCopy)).not.toContain("%");
});
