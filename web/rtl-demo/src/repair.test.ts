import { it, expect } from "vitest";
import { changedFiles } from "./repair";
it("does not omit removed files from a repair", () => {
  const a: any = {
    file_manifest: [
      { path: "old.v", sha256: "a" },
      { path: "same.v", sha256: "x" },
    ],
  };
  const b: any = {
    file_manifest: [
      { path: "new.v", sha256: "b" },
      { path: "same.v", sha256: "x" },
    ],
  };
  expect(changedFiles(a, b)).toEqual(["new.v", "old.v"]);
});
