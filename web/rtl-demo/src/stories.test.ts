import { it, expect } from "vitest";
import { applicationFacts, type UseEvent } from "./stories";
it("does not infer adoption, earlier retrieval, or verification from delivery/declaration", () => {
  const events = [
    { kind: "provided" },
    { kind: "application_declared" },
  ] as UseEvent[];
  expect(applicationFacts(events)).toEqual({
    retrieved: false,
    provided: true,
    declared: true,
    adopted: false,
    observed: false,
  });
  expect(applicationFacts([...events, ...events])).toEqual(
    applicationFacts(events),
  );
});
