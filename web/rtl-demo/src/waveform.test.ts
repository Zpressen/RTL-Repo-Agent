import { describe, it, expect } from "vitest";
import { valueAt, displayValue, fitWindow, zoomWindow } from "./waveform";
describe("真实波形显示语义", () => {
  it("使用 carry-in 并保留 x/z", () => {
    const s = {
      id: "dut",
      full_path: "tb.dut",
      width: 4,
      initial_value: "xxxx",
      changes: [
        ["10", "0011"],
        ["20", "zzzz"],
      ] as [string, string][],
    };
    expect(valueAt(s, 5n)).toBe("xxxx");
    expect(valueAt(s, 19n)).toBe("0011");
    expect(valueAt(s, 20n)).toBe("zzzz");
    expect(displayValue("0011", 4)).toBe("0x3");
    expect(displayValue("zzzz", 4)).toBe("zzzz");
  });
  it("保持巨大 tick 精度并限制范围", () => {
    const lo = 99999999999999999999n;
    expect(fitWindow(lo - 3n, lo + 7n, lo, lo + 100n)).toEqual([lo, lo + 10n]);
    expect(zoomWindow(lo, lo + 100n, lo + 50n, 1n, 2n, lo, lo + 100n)).toEqual([
      lo + 25n,
      lo + 75n,
    ]);
  });
  it("范围不可比时回到当前记录全程", () =>
    expect(fitWindow(1000n, 1200n, 0n, 100n)).toEqual([0n, 100n]));
});
