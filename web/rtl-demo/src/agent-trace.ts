import { el, button, note } from "./dom";
import { studioModel } from "./studio-model";
import {
  state,
  type Bundle,
  type DebugTrial,
  type ReplayEvent,
  type Run,
  type Validation,
  type Panel,
  historicalRun,
  historicalEvents,
  type HistoricalAttempt,
  historyJourney,
} from "./state";

export function selectedTrace<T extends { id: string; panel: Panel }>(
  steps: T[],
  step: string,
  panel: Panel,
): T | undefined {
  return (
    steps.find((s) => s.id === step && s.panel === panel) ||
    steps.find(
      (s) =>
        s.id ===
        {
          spec: "spec",
          architecture: "architecture",
          code: "rtl",
          verify: "verify",
          repair: "repair",
        }[panel],
    )
  );
}

// Reuse only an explicitly bound historical supplement. Never use it for a live run.
export function traceModel(
  b: Bundle,
  run?: Run | null,
  throughSequence?: number,
) {
  const m = studioModel(b, run, throughSequence);
  const t = b.debug_trace;
  const bound =
    !run &&
    t?.schema_version === "rtl-agent-debug-trace-v1" &&
    t.case_id === b.case_id &&
    t.bundle_id === b.bundle_id &&
    t.source_run_id === b.source_run_id &&
    t.source_fingerprint === b.source_fingerprint;
  const recorded =
    run?.origin === "historical" &&
    b.debug_history?.source_fingerprint === b.source_fingerprint
      ? run.attempts?.length === historyJourney(b)?.attempts.length
        ? historyJourney(b)
        : b.debug_history.runs.find((r) => r.run_id === run.run_id)
      : undefined;
  return m.steps.map((s) => ({
    ...s,
    attempts: s.events
      .filter((e) => e.trial_no != null)
      .map((event) => ({
        event,
        debug:
          recorded?.attempts.find((a) => a.trial_no === event.trial_no)
            ?.debug ||
          (bound
            ? t.trials.find((x) => x.trial_no === event.trial_no)
            : undefined),
      })),
  }));
}

export type LiveTrace = {
  id: string;
  text: string;
  tag: string;
  runId?: string;
  stage?: string;
  validationId?: string;
  trialNo?: number;
};
export function observedRun(run: Run, live: LiveTrace[]): Run {
  const observed = live
    .filter(
      (x) =>
        x.runId === run.run_id &&
        [
          "spec",
          "architecture",
          "rtl",
          "syntax",
          "verify",
          "diagnose",
          "repair",
          "complete",
        ].includes(x.stage || ""),
    )
    .slice()
    .reverse();
  const events = run.events || [];
  const start = Math.max(0, ...events.map((e) => e.sequence));
  return {
    ...run,
    events: [
      ...events,
      ...observed.map((x, i) => ({
        sequence: start + i + 1,
        stage: x.stage!,
        text: x.text,
        validation_id: x.validationId,
        trial_no: x.trialNo,
        observed_at: null,
        replay_delay_ms: 0,
        origin: "live" as const,
      })),
    ],
  };
}
export function agentTrace(
  onStep: (id: string, e?: ReplayEvent) => void,
  select: (v: Validation) => void,
  inspect?: (a: HistoricalAttempt) => void,
) {
  const root = el("section", "agent-trace");
  root.setAttribute("aria-label", "Agent Trace 调试流程");
  const heading = el("div", "trace-heading");
  heading.append(
    el("strong", "mono", "AGENT TRACE"),
    el("span", "", "逐步调试流程"),
  );
  const origin = el("p", "trace-origin");
  const list = el("div", "agent-trace-list");
  root.append(heading, origin, list);

  function detailRow(parent: HTMLElement, label: string, value: string) {
    const row = el("div", "trace-detail-row");
    row.append(el("strong", "", label), el("p", "", value));
    parent.append(row);
  }
  function debugDetails(box: HTMLElement, d: DebugTrial) {
    if (d.intent) detailRow(box, "修改原因 · Agent 记录", d.intent);
    if (d.expected_effect)
      detailRow(box, "① 修改目标 · 预期效果", d.expected_effect);
    if (d.files.length)
      detailRow(
        box,
        "② RTL 修改",
        d.files
          .map(
            (f) =>
              (({ added: "+ ", deleted: "− ", modified: "~ " })[f.change] ||
                "") + f.path,
          )
          .join("\n"),
      );
    detailRow(
      box,
      "③ 检查与仿真",
      (d.lint_pass === null
        ? "未单独检查"
        : d.lint_pass
          ? "语法检查通过"
          : "语法检查失败") +
        " → " +
        (d.simulation_completed
          ? "仿真完成 · " + d.verdict.toUpperCase()
          : "未完成仿真"),
    );
    if (d.signals.length)
      detailRow(
        box,
        "④ 差异回溯",
        d.signals.join("、") +
          (d.first_fail_time != null
            ? " · 首次失败 " + d.first_fail_time + " ticks"
            : "") +
          (d.alignment === "unresolved"
            ? "\n采样对齐尚未解决，未形成确定根因。"
            : ""),
      );
    if (d.mismatch_count != null)
      detailRow(
        box,
        "调试器内部计数",
        d.mismatch_count + "（可能含重复信号；采样结果以原始验证报告为准）",
      );
    detailRow(
      box,
      "⑤ 候选决策",
      d.decision === "accept"
        ? "接受此候选，更新基线"
        : d.decision === "rollback"
          ? "回退此候选，保留原基线"
          : "未记录独立决策",
    );
    if (d.lint_excerpt) {
      const logs = el("details", "trace-tool-log");
      logs.append(
        el("summary", "", "查看语法工具日志 · 脱敏节选"),
        el("pre", "", d.lint_excerpt),
      );
      box.append(logs);
    }
  }
  function openDetail(
    title: string,
    fill: (body: HTMLElement, close: () => void) => void,
  ) {
    const dialog = el("dialog", "artifact-dialog trace-dialog");
    dialog.setAttribute("aria-label", title);
    const head = el("div", "dialog-head");
    const close = () => dialog.close();
    head.append(el("strong", "", title), button("关闭详情", close));
    const body = el("div", "trace-dialog-body");
    fill(body, close);
    dialog.append(head, body);
    document.body.append(dialog);
    dialog.onclose = () => dialog.remove();
    dialog.showModal();
  }
  function render(live: LiveTrace[] = []) {
    const b = state.bundle!;
    const currentRun =
      state.mode === "live"
        ? state.liveRun || {
            run_id: state.context.run_id || "",
            versions: [],
            validations: [],
            events: [],
          }
        : historicalRun();
    const run =
      state.mode === "live" && currentRun
        ? observedRun(currentRun, live)
        : currentRun;
    const limited = state.mode === "historical" && state.replayIndex >= 0;
    const steps = traceModel(
      b,
      run,
      limited ? historicalEvents()[state.replayIndex]?.sequence : undefined,
    );
    const s = selectedTrace(steps, state.step, state.tab);
    root.dataset.step = s?.id || state.step;
    heading.lastElementChild!.textContent = s?.name || "当前阶段";
    origin.textContent =
      state.mode === "live"
        ? "实时执行 · 点击卡片查看详情"
        : "历史回放 · 点击卡片查看详情";
    list.replaceChildren();
    if (!s) return;
    const recorded = historicalRun();
    if (recorded && ["diagnose", "repair"].includes(s.id)) {
      s.attempts = recorded.attempts.flatMap((a) => {
        const event = run?.events?.find((e) => e.trial_no === a.trial_no);
        return event &&
          (!limited ||
            event.sequence <= historicalEvents()[state.replayIndex].sequence)
          ? [{ event, debug: a.debug }]
          : [];
      });
    }
    const source = s.attempts.some((a) => a.debug)
      ? "来源：原始验证日志；修改目标为当时预期，不等同确定根因。"
      : s.source === "original_event"
        ? "来源：运行事件 / 归档材料"
        : s.source === "report_summary"
          ? "来源：验证报告；没有独立的 Agent 定位结论。"
          : "没有独立记录";
    const v = (run?.validations || b.validations).find(
      (v) => v.validation_id === s.validation_id,
    );
    const stage = button(
      "",
      () =>
        recorded
          ? onStep(s.id, s.events.at(-1))
          : openDetail(s.name + " · 阶段记录", (body, close) => {
              body.append(note(s.summary));
              if (v) {
                detailRow(body, "验证记录", v.validation_id);
                detailRow(
                  body,
                  "检查结果",
                  v.verdict.toUpperCase() +
                    (v.total_samples != null
                      ? " · " +
                        (v.mismatched_samples ?? "—") +
                        " / " +
                        v.total_samples +
                        " 不匹配采样"
                      : ""),
                );
                if (v.first_failure_ticks)
                  detailRow(body, "首次差异", v.first_failure_ticks + " ticks");
              }
              if (s.source !== "unrecorded")
                body.append(
                  button(
                    "查看" + s.name + "证据 ↗",
                    () => {
                      close();
                      onStep(s.id, s.events.at(-1));
                    },
                    "trace-link",
                  ),
                );
              body.append(note(source));
            }),
      "trace-card current",
    );
    stage.dataset.step = s.id;
    stage.dataset.result = s.result;
    const tag = el(
      "span",
      "trace-card-tag mono",
      "STEP " + String(steps.indexOf(s) + 1).padStart(2, "0") + " · " + s.name,
    );
    stage.append(
      tag,
      el(
        "span",
        "trace-summary",
        s.attempts.length
          ? s.id === "diagnose"
            ? s.summary + "；点击查看判断与修改前代码。"
            : "已记录 " + s.attempts.length + " 条候选记录，点击查看阶段证据。"
          : s.summary,
      ),
      el("span", "trace-card-action", "查看详情 ↗"),
    );
    list.append(stage);
    for (const { event, debug } of [...s.attempts].reverse()) {
      const diagnosis =
        s.id === "diagnose"
          ? recorded?.attempts.find((a) => a.trial_no === event.trial_no)
              ?.diagnosis
          : undefined;
      const candidate = button(
        "",
        () => {
          const a = recorded?.attempts.find(
            (a) => a.trial_no === event.trial_no,
          );
          if (a && inspect) {
            inspect(a);
            return;
          }
          openDetail(event.text, (body, close) => {
            if (debug) debugDetails(body, debug);
            else
              body.append(note("仅保存此轮摘要；没有可公开的详细调试记录。"));
            const result = (run?.validations || b.validations).find(
              (v) => v.validation_id === event.validation_id,
            );
            if (result)
              body.append(
                button(
                  "查看候选 " + event.trial_no + " 报告与波形 ↗",
                  () => {
                    close();
                    select(result);
                  },
                  "trace-link",
                ),
              );
            body.append(note(source));
          });
        },
        "trace-attempt trace-summary-card",
      );
      candidate.dataset.trial = String(event.trial_no);
      candidate.classList.toggle(
        "selected",
        event.validation_id === state.context.validation_id,
      );
      candidate.setAttribute(
        "aria-pressed",
        String(event.validation_id === state.context.validation_id),
      );
      const summary =
        s.id === "diagnose"
          ? diagnosis?.summary || "未保存本次修改前的独立根因判断。"
          : debug
            ? (debug.files.length
                ? "变更 " + debug.files.length + " 个 RTL 文件；"
                : "") +
              (debug.lint_pass === null
                ? "未单独检查，"
                : debug.lint_pass
                  ? "语法检查通过，"
                  : "语法检查失败，") +
              (debug.simulation_completed
                ? "仿真" + (debug.verdict === "pass" ? "通过" : "存在差异")
                : "未完成仿真") +
              (debug.decision === "accept"
                ? debug.lint_pass === null
                  ? "，修改已保留。"
                  : "，候选已接受。"
                : debug.decision === "rollback"
                  ? "，已回退。"
                  : "。")
            : "仅保存验证摘要，点击查看可用记录。";
      candidate.append(
        el(
          "span",
          "trace-card-tag mono",
          (s.id === "diagnose" ? "修复前 · 候选 " : "候选 ") + event.trial_no,
        ),
        el("span", "trace-summary", summary),
        el(
          "span",
          "trace-card-action",
          s.id === "diagnose"
            ? "查看判断与修改前代码 ↗"
            : recorded
              ? "查看本次代码与波形 ↗"
              : "查看调试记录 ↗",
        ),
      );
      list.append(candidate);
    }
    for (const event of live.filter(
      (x) => x.runId === run?.run_id && x.stage === s.id,
    )) {
      const card = button(
        "",
        () =>
          openDetail("本阶段实时事件", (body) => {
            body.append(note(event.tag), note(event.text));
          }),
        "trace-summary-card",
      );
      card.append(
        el("span", "trace-card-tag", event.tag),
        el("span", "trace-summary", event.text),
      );
      list.append(card);
    }
  }
  return { element: root, render };
}
