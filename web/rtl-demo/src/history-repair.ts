import {
  state,
  historicalRun,
  selectedAttempt,
  validation,
  type Validation,
} from "./state";
import { el, button, note, modal, errorText } from "./dom";
import { content } from "./api";
import { changedFiles } from "./evidence-selection";
import { renderDiff } from "./code";
import { verification } from "./verification";
import { unifiedDiff } from "./history-diff";
import { validationSummary } from "./validation-summary";

export function historyRepair(
  select: (v: Validation) => void,
  onContext: () => void,
) {
  const run = historicalRun()!,
    a = selectedAttempt();
  const root = el("section", "repair-view history-repair");
  root.append(
    el(
      "div",
      "eyebrow",
      run.label + " · 修复过程",
    ),
  );
  if (!a) {
    root.append(
      el(
        "h2",
        "",
        state.context.validation_id === run.initial_validation_id
          ? "初始失败定位"
          : "阶段验证记录",
      ),
      note("依据初始报告定位失败信号与采样时刻；没有独立确认的根因结论。"),
    );
    const v =
      validation() ||
      run.validations.find(
        (v) => v.validation_id === run.initial_validation_id,
      )!;
    root.append(verification(select, onContext, { validation: v }));
    return root;
  }
  const v = run.validations.find((v) => v.validation_id === a.validation_id)!,
    before = run.validations.find(
      (v) => v.validation_id === a.before_validation_id,
    )!,
    left = run.versions.find((v) => v.version_id === a.baseline_version_id)!,
    right = run.versions.find((v) => v.version_id === a.candidate_version_id)!;
  root.dataset.trial = String(a.trial_no);
  root.dataset.runId = run.run_id;
  root.append(
    el(
      "h2",
      "",
      "候选 " +
        a.trial_no +
        " · " +
        (a.decision === "accepted"
          ? v.kind === "edit_only"
            ? "已保留 · 未单独验证"
            : "已接受"
          : a.decision === "rolled_back"
            ? "已回退"
            : "被后续修订替代"),
    ),
  );
  const baseAttempt = run.attempts.find(
    (a) => a.candidate_version_id === left.version_id,
  );
  const binding = note(
    "修改基线：" +
      (baseAttempt
        ? "候选 " + baseAttempt.trial_no
        : left.version_id ===
            run.validations.find(
              (v) => v.validation_id === run.initial_validation_id,
            )?.version_id
          ? "初始 RTL"
          : "本次起始快照") +
      " → 本次候选：候选 " +
      a.trial_no,
  );
  binding.title = left.version_id + " → " + right.version_id;
  binding.classList.add("baseline-binding");
  root.append(binding);
  if (a.decision === "rolled_back")
    root.append(note("本次修改未成为后续接受基线；展示其实际试验结果。"));
  if (a.debug.expected_effect) {
    const target = el("details", "card");
    target.append(
      el("summary", "", "本次修改目标 · 原始 Agent 记录"),
      ...(a.debug.intent ? [note("当时诊断假设：" + a.debug.intent)] : []),
      note(a.debug.expected_effect),
    );
    root.append(target);
  }
  const summary = el("div", "repair-cards");
  for (const [title, value] of [
    ["修改前", validationSummary(before)],
    ["本次验证", validationSummary(v)],
    [
      "诊断记录",
      a.debug.alignment === "unresolved"
        ? "采样对齐未解决，未确认根因"
        : a.debug.signals.length
          ? a.debug.signals.join("、")
          : "未记录新的独立诊断",
    ],
  ]) {
    const card = el("article", "card");
    card.append(el("div", "eyebrow", title), note(value));
    summary.append(card);
  }
  root.append(summary);
  const patch = el("article", "card patch-card");
  patch.append(el("h3", "", "本次代码改动 · 相对已接受基线"));
  const files = el("select");
  files.setAttribute("aria-label", "变更文件");
  for (const name of changedFiles(left, right)) {
    const o = el("option", "", name);
    o.value = name;
    files.append(o);
  }
  const code = el("pre", "diff-source");
  let token = 0;
  async function show() {
    const seq = ++token,
      name = files.value;
    try {
      const l = left.modules.find((m) => m.file === name),
        r = right.modules.find((m) => m.file === name);
      const [x, y] = await Promise.all([
        l ? content(l.artifact_id!) : Promise.resolve(""),
        r ? content(r.artifact_id!) : Promise.resolve(""),
      ]);
      if (seq === token && code.isConnected)
        renderDiff(code, unifiedDiff(x, y, name));
    } catch (e) {
      if (seq === token) code.textContent = errorText(e);
    }
  }
  files.onchange = () => void show();
  const source = el("details", "patch-expander");
  source.open = true;
  source.append(el("summary", "", "展开代码 Diff"), code);
  patch.append(files, source);
  root.append(patch);
  if (files.options.length) void show();
  root.append(
    button(
      v.kind === "edit_only" ? "查看修改状态 ↗" : "查看语法工具日志 ↗",
      () =>
        modal(
          "候选 " +
            a.trial_no +
            (v.kind === "edit_only" ? " · 修改状态" : " · 语法工具日志"),
          a.debug.lint_excerpt ||
            (v.kind === "edit_only"
              ? "本次修改未单独执行语法或仿真检查；后续候选才运行验证。"
              : "未记录"),
        ),
      "text-button",
    ),
  );
  if (a.debug.signals.length)
    root.append(note("诊断涉及信号：" + a.debug.signals.join("、")));
  if (a.simulation_completed) {
    const focus = v.first_failure_ticks || before.first_failure_ticks;
    if (!state.viewport && focus) {
      const t = BigInt(focus);
      state.viewport = [t > 100n ? t - 100n : 0n, t + 150n];
      state.cursor = t;
    }
    const waves = el("article", "card history-wave-comparison");
    waves.append(el("h3", "", "修改前 / 本次候选 · 验证与波形记录"));
    const toolbar = el("div", "verification-toolbar"),
      view = el("div");
    const baseline = button("修改前波形", () => showWave(before, baseline));
    const candidate = button("本次候选波形", () => showWave(v, candidate));
    function showWave(target: Validation, active: HTMLButtonElement) {
      for (const b of [baseline, candidate])
        b.classList.toggle("active", b === active);
      view.dataset.validationId = target.validation_id;
      view.replaceChildren(
        verification(select, onContext, { validation: target }),
      );
    }
    toolbar.append(baseline, candidate);
    waves.append(toolbar, view);
    root.append(waves);
    showWave(v, candidate);
  } else {
    root.append(
      note(
        v.kind === "edit_only"
          ? "本次修改已保留，但没有单独运行检查；初始失败结果和探针不作为本版本结果展示。"
          : "本次只完成语法检查，目录中继承的历史报告与 VCD 未作为本次结果展示。",
      ),
    );
  }
  const final = run.validations.find(
    (v) => v.validation_id === run.final_validation_id,
  )!;
  root.append(button("查看最终复验", () => select(final), "text-button"));
  return root;
}
