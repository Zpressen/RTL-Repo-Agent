import { it, expect } from "vitest";
import { state } from "./state";
import { selectedPackage } from "./evidence-download";
const fixtures = import.meta.glob("../public/cases/*/manifest.json", {
  eager: true,
  import: "default",
});
it("rejects a descriptor mapped to the wrong validation or case", () => {
  const old = {
    bundle: state.bundle,
    context: state.context,
    comparing: state.comparing,
  };
  try {
    const b = structuredClone(
      fixtures["../public/cases/e203/manifest.json"],
    ) as any;
    state.bundle = b;
    state.context = {
      case_id: "e203",
      validation_id: b.comparison_pair.after_validation_id,
    };
    state.comparing = false;
    const d = b.evidence_packages.single[b.comparison_pair.after_validation_id];
    d.validation_id = "wrong";
    expect(() => selectedPackage()).toThrow();
    d.validation_id = b.comparison_pair.after_validation_id;
    d.url = d.url.replace("/e203/", "/sdc_controller_system/");
    expect(() => selectedPackage()).toThrow();
  } finally {
    Object.assign(state, old);
  }
});
