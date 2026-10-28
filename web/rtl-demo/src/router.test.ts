import { describe, it, expect } from "vitest";
import { parseRoute, publicLink } from "./router";
describe("studio navigation", () => {
  it("normalizes legacy pages without discarding valid evidence", () => {
    const r = parseRoute(
      new URL(
        "https://demo.test/?case=e203&version_id=v&story_id=old#/experience",
      ),
    );
    expect(r.view).toBe("workspace");
    expect(r.context.version_id).toBe("v");
    expect(r.context.story_id).toBeUndefined();
  });
  it("supports five panels and verification alias", () => {
    for (const p of ["spec", "architecture", "code", "verify", "repair"])
      expect(parseRoute(new URL("https://x/?panel=" + p)).panel).toBe(p);
    expect(parseRoute(new URL("https://x/?panel=verification")).panel).toBe(
      "verify",
    );
  });
  it("retains invalid explicit evidence intent", () =>
    expect(
      parseRoute(new URL("https://x/?version_id=%2Fprivate")).explicitEvidence,
    ).toBe(true));
  it("only shares public fields", () => {
    const url = publicLink(
      {
        case_id: "e203",
        validation_id: "v",
        session_id: "private",
        text: "secret",
      } as never,
      "workspace",
      "verify",
    );
    expect(url).not.toContain("private");
    expect(url).not.toContain("secret");
  });
});
