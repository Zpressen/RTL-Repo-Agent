import {
  state,
  historicalRun,
  selectedAttempt,
  type HistoricalAttempt,
  type Validation,
} from "./state";
import { el, button, note, modal, errorText } from "./dom";
import { content } from "./api";
import { verification } from "./verification";

export function historyDiagnosis(
  inspect: (attempt: HistoricalAttempt) => void,
  repair: (attempt: HistoricalAttempt) => void,
  select: (validation: Validation) => void,
  onContext: () => void,
) {
  const run = historicalRun(),
    a = selectedAttempt();
  const root = el("section", "repair-view history-diagnosis");
  root.append(el("div", "eyebrow", "根因定位 · 修复前的判断"));
  if (!run || !a) {
    const recorded =
      run?.attempts.filter(
        (a) => a.diagnosis?.status === "recorded_hypothesis",
      ) || [];
    root.append(
      el("h2", "", "Agent 如何判断代码错在哪里"),
      note(
        recorded.length
          ? `已保存 ${recorded.filter((a) => a.diagnosis?.recorded_at === "before_edit").length} 条修改前判断、${recorded.filter((a) => a.diagnosis?.recorded_at === "validation_request").length} 条提交验证时的理由，${run!.attempts.length - recorded.length} 次未保存独立判断。点击右侧记录查看来源与旧代码。`
          : "当前记录未保存可绑定的修复前判断；不使用代码改动或修复结果代替根因。",
      ),
    );
    for (const attempt of recorded.slice(0, 3)) {
      root.append(
        button(
          `修复前 · 候选 ${attempt.trial_no}：${attempt.diagnosis!.summary}`,
          () => inspect(attempt),
          "diagnosis-choice card",
        ),
      );
    }
    return root;
  }
  root.dataset.trial = String(a.trial_no);
  const diagnosis = a.diagnosis;
  const baseline = run.versions.find(
    (v) => v.version_id === a.baseline_version_id,
  )!;
  const before = run.validations.find(
    (v) => v.validation_id === a.before_validation_id,
  )!;
  root.append(el("h2", "", `修复前 · 候选 ${a.trial_no}`));
  const binding = note(
    "定位对象：修改前 RTL · " + baseline.tree_sha256.slice(0, 12),
  );
  binding.classList.add("diagnosis-binding");
  binding.title = baseline.version_id;
  root.append(binding);
  const judgment = el("article", "card diagnosis-judgment");
  judgment.append(
    el(
      "h3",
      "",
      diagnosis?.status === "recorded_hypothesis"
        ? diagnosis.recorded_at === "validation_request"
          ? "提交候选验证时的诊断理由"
          : "Agent 当时的根因假设"
        : "本次根因判断未记录",
    ),
    note(diagnosis?.summary || "未保存本次修改前的独立根因判断。"),
  );
  if (diagnosis?.status === "recorded_hypothesis")
    judgment.append(
      note(
        "中文摘要依据归档记录整理；这是当时的判断，后续接受或回退请查看自动修复。",
      ),
    );
  if (diagnosis?.recorded_at === "validation_request")
    judgment.append(
      note("未保存独立的修改前判断消息；这里仅展示提交候选验证时记录的理由。"),
    );
  root.append(judgment);
  if (diagnosis?.statements.length) {
    const originals = el("details", "card diagnosis-original");
    originals.append(el("summary", "", "查看原始 Agent 记录与来源"));
    for (const source of diagnosis.statements) {
      const title =
        source.kind === "patch_hypothesis"
          ? "执行修改时提交的 hypothesis"
          : source.kind === "validation_reason"
            ? "提交候选验证时的 reason（非独立修改前消息）"
            : source.timing === "before_code_edit"
              ? "已记录代码修改前的公开消息"
              : "候选验证前的公开消息";
      const row = el("article", "diagnosis-statement");
      row.append(
        el("strong", "", title),
        note(source.text),
        el(
          "small",
          "mono muted",
          `来源 SHA-256 ${source.sha256.slice(0, 16)} · 记录行 ${source.line}`,
        ),
      );
      originals.append(row);
    }
    root.append(originals);
  }
  if (diagnosis?.locations.length) {
    const card = el("article", "card diagnosis-location");
    card.append(el("h3", "", "涉及的修改前代码"));
    const chooser = el("select");
    chooser.setAttribute("aria-label", "根因涉及代码位置");
    for (const [i, location] of diagnosis.locations.entries()) {
      const option = el(
        "option",
        "",
        `${location.file} · L${location.start_line}–${location.end_line}`,
      );
      option.value = String(i);
      chooser.append(option);
    }
    const origin = note(""),
      code = el("pre", "diagnosis-source");
    let token = 0;
    async function show() {
      const seq = ++token,
        loc = diagnosis!.locations[Number(chooser.value)];
      origin.textContent =
        loc.source === "agent_target"
          ? "原始 Agent 指定的修改范围；下方为修改前版本的代码节选。"
          : "按该候选的变更范围关联旧代码；原消息未给出精确根因行号。";
      try {
        const module = baseline.modules.find((m) => m.file === loc.file)!;
        const text = await content(module.artifact_id!);
        if (seq !== token) return;
        const lines = text.split("\n"),
          start = Math.max(0, loc.start_line - 3),
          end = Math.min(lines.length, start + 26, loc.end_line + 2);
        code.textContent = lines
          .slice(start, end)
          .map((line, i) => String(start + i + 1).padStart(4) + "  " + line)
          .join("\n");
        if (end < loc.end_line)
          code.textContent += `\n… 范围较长，此处仅展示开头；完整范围至 L${loc.end_line}。`;
      } catch (e) {
        if (seq === token) code.textContent = errorText(e);
      }
    }
    chooser.onchange = () => void show();
    card.append(
      chooser,
      origin,
      code,
      button(
        "查看该基线完整 RTL",
        async () => {
          const loc = diagnosis.locations[Number(chooser.value)];
          try {
            modal(
              loc.file + " · 修改前完整 RTL",
              await content(
                baseline.modules.find((m) => m.file === loc.file)!.artifact_id!,
              ),
            );
          } catch (e) {
            modal("加载失败", errorText(e));
          }
        },
        "text-button",
      ),
    );
    root.append(card);
    void show();
  }
  const evidence = el("details", "card diagnosis-evidence");
  evidence.append(el("summary", "", "查看修改前的验证依据"));
  evidence.ontoggle = () => {
    if (!evidence.open || evidence.querySelector(".verification")) return;
    if (!before.simulation_completed)
      evidence.append(
        note(
          "该修改基线没有单独完成仿真。未把更早版本的失败时刻或波形作为这个版本的结果。",
        ),
      );
    evidence.append(verification(select, onContext, { validation: before }));
  };
  root.append(
    evidence,
    button("查看该次自动修复 ↗", () => repair(a), "primary"),
  );
  return root;
}
