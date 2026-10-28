import { state } from "./state";
import { content } from "./api";
import { el, button, note, modal, errorText } from "./dom";
export function specification() {
  const b = state.bundle!,
    root = el("section", "spec-view evidence-grid");
  const left = el("article", "card spec-original"),
    right = el("article", "card");
  left.append(
    el("div", "eyebrow", "SYSTEM SPECIFICATION"),
    el("h2", "", b.title + " · 设计规格"),
    note(b.summary),
  );
  const pre = el("pre", "spec-excerpt", "载入已归档规格…");
  left.append(pre);
  right.append(
    el("div", "eyebrow", "DESIGN CONSTRAINTS"),
    el("h3", "", "规格与规划摘要"),
  );
  const facts = el("div", "constraint-list");
  right.append(facts, note("依据公开规格与规划整理；未记录的约束不作推断。"));
  root.append(left, right);
  void Promise.all([
    content(b.spec_artifact_id),
    content(b.planner_artifact_id),
  ])
    .then(([spec, plan]) => {
      pre.textContent =
        spec.slice(0, 3500) + (spec.length > 3500 ? "\n… 查看完整规格" : "");
      left.append(
        button(
          "查看原始规格 ↗",
          () => modal(b.title + " · 系统规格", spec),
          "text-button",
        ),
      );
      let p: any = {};
      try {
        p = JSON.parse(plan);
      } catch {}
      for (const [k, v] of [
        ["设计范围", b.title],
        ["规划模块", String(b.modules.length)],
        [
          "顶层模块",
          p.top_module ||
            b.modules.find((m) => !m.parents?.length)?.module_id ||
            "未记录",
        ],
        [
          "时钟",
          p.global_invariants?.clocking_model?.primary_clock || "未记录",
        ],
        ["复位", p.global_invariants?.clocking_model?.reset_signal || "未记录"],
        ["频率 / PPA 目标", "未记录"],
      ]) {
        const row = el("div", "constraint");
        row.append(el("span", "muted", k), el("strong", "mono", v));
        facts.append(row);
      }
      right.append(
        button(
          "查看规划来源 ↗",
          () => modal("架构规划 · 原始记录", plan),
          "text-button",
        ),
      );
    })
    .catch((e) => (pre.textContent = errorText(e)));
  return root;
}
