import type { Context } from "./state";
export type { Panel } from "./state";
import type { Panel } from "./state";
// Legacy view types remain for old records; new navigation is always workspace.
export type View = "workspace" | "optimization" | "experience";
export const views: View[] = ["workspace"];
export const panels: Panel[] = [
  "spec",
  "architecture",
  "code",
  "verify",
  "repair",
];
export const panelNames: Record<Panel, string> = {
  spec: "规格",
  architecture: "架构",
  code: "RTL 代码",
  verify: "仿真与波形",
  repair: "定位与修复",
};
const keys = ["validation_id", "version_id", "run_id", "module_id"] as const;
export const normalizePanel = (p?: string | null): Panel | undefined =>
  p === "verification"
    ? "verify"
    : panels.includes(p as Panel)
      ? (p as Panel)
      : undefined;
export function parseRoute(url: URL) {
  const raw = url.hash.replace(/^#\/?/, "");
  const ctx: Partial<Context> = {};
  for (const k of keys) {
    const v = url.searchParams.get(k);
    if (v && /^[A-Za-z0-9_.-]{1,240}$/.test(v)) ctx[k] = v;
  }
  const step = url.searchParams.get("step");
  const before = url.searchParams.get("before_validation_id");
  return {
    view: "workspace" as View,
    context: ctx,
    explicitEvidence: keys.some((k) => url.searchParams.has(k)),
    panel: normalizePanel(url.searchParams.get("panel")),
    step:
      step &&
      [
        "spec",
        "architecture",
        "rtl",
        "syntax",
        "verify",
        "diagnose",
        "repair",
        "complete",
      ].includes(step)
        ? step
        : undefined,
    before:
      before && /^[A-Za-z0-9_.-]{1,240}$/.test(before) ? before : undefined,
    legacy: raw === "optimization" || raw === "experience",
    invalid:
      !!raw && !["workspace", "optimization", "experience"].includes(raw),
  };
}
export function publicLink(
  ctx: Context,
  _view: View = "workspace",
  panel?: Panel,
) {
  const q = new URLSearchParams({ case: ctx.case_id });
  for (const k of keys) if (ctx[k]) q.set(k, ctx[k]!);
  if (panel) q.set("panel", panel);
  return "/?" + q + "#/workspace";
}
