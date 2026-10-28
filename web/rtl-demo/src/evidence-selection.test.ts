import { it, expect } from "vitest";
import {
  resolveEvidence,
  changedFiles,
  convertTicks,
} from "./evidence-selection";
const b: any = {
  case_id: "e203",
  source_run_id: "run",
  versions: [
    { version_id: "v", run_id: "run", modules: [], file_manifest: [] },
  ],
  validations: [{ validation_id: "ok", version_id: "v", run_id: "run" }],
};
it("rejects mismatched explicit evidence rather than falling back", () => {
  expect(() =>
    resolveEvidence(b, { case_id: "e203", validation_id: "bad" }),
  ).toThrow();
  expect(() =>
    resolveEvidence(b, { case_id: "sdc_controller_system" }),
  ).toThrow();
  expect(() =>
    resolveEvidence(b, {
      case_id: "e203",
      validation_id: "ok",
      version_id: "other",
    }),
  ).toThrow();
  expect(
    resolveEvidence(b, { case_id: "e203", validation_id: "ok" }).version_id,
  ).toBe("v");
});
it("lists added deleted and changed files including defines", () =>
  expect(
    changedFiles(
      {
        file_manifest: [
          { path: "defs.v", sha256: "a" },
          { path: "old.v", sha256: "x" },
        ],
      } as any,
      {
        file_manifest: [
          { path: "defs.v", sha256: "b" },
          { path: "new.v", sha256: "y" },
        ],
      } as any,
    ),
  ).toEqual(["defs.v", "new.v", "old.v"]));
it("converts physical time exactly", () => {
  expect(
    convertTicks(2n, { value: 1, unit: "ns" }, { value: 1, unit: "ps" }),
  ).toBe(2000n);
  expect(() =>
    convertTicks(1n, { value: 1, unit: "ps" }, { value: 1, unit: "ns" }),
  ).toThrow();
});
