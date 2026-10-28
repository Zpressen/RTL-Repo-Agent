import { el, button, note } from "./dom";
import { studioModel } from "./studio-model";
import {
  state,
  historicalRun,
  historicalEvents,
  type ReplayEvent,
} from "./state";
export function timeline(onStep: (id: string, e?: ReplayEvent) => void) {
  const root = el("aside", "timeline");
  root.setAttribute("aria-label", "运行步骤");
  const title = el("div", "eyebrow", "RUN TIMELINE · 点击查看每一步");
  root.append(title);
  const list = el("div", "timeline-list");
  root.append(list);
  function render() {
    list.replaceChildren();
    const limited = state.mode === "historical" && state.replayIndex >= 0;
    const sequence = limited
      ? historicalEvents()[state.replayIndex]?.sequence
      : undefined;
    const full = studioModel(
      state.bundle!,
      state.mode === "live"
        ? state.liveRun || {
            run_id: state.context.run_id || "",
            versions: [],
            validations: [],
            modules: [],
          }
        : historicalRun(),
    );
    const m = studioModel(
      state.bundle!,
      state.mode === "live"
        ? state.liveRun || {
            run_id: state.context.run_id || "",
            versions: [],
            validations: [],
            modules: [],
          }
        : historicalRun(),
      sequence,
    );
    for (const [i, s] of m.steps.entries()) {
      const row = el("div", "timeline-row");
      const b = button(
        "",
        () => onStep(s.id, full.steps[i].events.at(-1)),
        "timeline-step",
      );
      b.dataset.step = s.id;
      b.classList.toggle("active", state.step === s.id);
      b.setAttribute("aria-current", state.step === s.id ? "step" : "false");
      const outcome = s.result;
      const dot = el(
        "span",
        "step-dot " +
          (outcome === "pass" ? "pass" : outcome === "fail" ? "fail" : ""),
        outcome === "pass" ? "✓" : outcome === "fail" ? "!" : String(i + 1),
      );
      b.dataset.result = outcome;
      const text = el("span", "step-copy");
      const waiting =
        limited &&
        s.source === "unrecorded" &&
        full.steps[i].source !== "unrecorded";
      const summary = waiting
        ? state.step === s.id && !full.steps[i].events.length
          ? full.steps[i].summary
          : "尚未回放 · 可点击浏览归档"
        : s.summary;
      text.append(
        el("strong", "", s.name),
        el("small", outcome === "fail" ? "failed-step" : "", summary),
      );
      b.append(dot, text);
      row.append(b);
      const records =
        s.id === "repair" && historicalRun() ? m.trials : s.events;
      if (records.length > 1) {
        const d = el("details", "step-attempts");
        d.append(el("summary", "", records.length + " 条记录"));
        for (const e of records)
          d.append(button(e.text, () => onStep(s.id, e), "text-button"));
        row.append(d);
      }
      list.append(row);
    }
    list.append(note("历史按展示节奏回放；未记录原始耗时。"));
  }
  render();
  return { element: root, render };
}
