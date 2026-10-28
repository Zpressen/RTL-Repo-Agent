import { state, type Validation, version } from "./state";
import { el, button, note, modal, errorText } from "./dom";
import { content } from "./api";
import { changedFiles } from "./evidence-selection";
import { simpleDiff, renderDiff } from "./code";
import { studioModel } from "./studio-model";
export function repair(select: (v: Validation) => void) {
  const b = state.bundle!,
    root = el("section", "repair-view");
  const before = b.validations.find(
      (v) => v.validation_id === b.comparison_pair.before_validation_id,
    ),
    after = b.validations.find(
      (v) => v.validation_id === b.comparison_pair.after_validation_id,
    );
  root.append(
    el("div", "eyebrow", "DIAGNOSIS & REPAIR"),
    el("h2", "", "从失败记录，到最终复验"),
  );
  if (!before) {
    root.append(note("未保存可配对的修复前记录，可在仿真与波形查看最终结果。"));
    if (after)
      root.append(button("查看最终复验", () => select(after), "primary"));
    return root;
  }
  const cards = el("div", "repair-cards");
  for (const [title, text] of [
    [
      "失败现象",
      `${before.mismatched_samples ?? "—"} / ${before.total_samples ?? "—"} 不匹配采样 · ${before.first_failure_ticks ?? "未记录"} ticks`,
    ],
    ["差异定位", "依据已有报告整理；未单独记录定位过程。"],
    ["根因结论", "未记录独立根因结论；可核查报告、代码变更和候选验证。"],
  ]) {
    const c = el("article", "card");
    c.append(el("div", "eyebrow", title), note(text));
    cards.append(c);
  }
  void content(before.report_artifact_id)
    .then((text) => {
      const names = [
        ...text.matchAll(/Output '([^']+)' has [1-9][0-9]* mismatches/g),
      ].map((m) => m[1]);
      if (names.length)
        cards.firstElementChild?.append(
          note("差异信号：" + [...new Set(names)].join("、")),
        );
    })
    .catch(() => {});
  root.append(
    cards,
    button(
      "查看失败报告 ↗",
      async () => {
        try {
          modal("失败报告", await content(before.report_artifact_id));
        } catch (e) {
          modal("加载失败", errorText(e));
        }
      },
      "text-button",
    ),
    button(
      "定位差异 · " + before.first_failure_ticks + " ps",
      () => select(before),
      "failure-jump",
    ),
  );
  const a = b.versions.find((v) => v.version_id === before.version_id),
    z = b.versions.find((v) => v.version_id === after?.version_id);
  if (a && z) {
    const box = el("article", "card patch-card");
    box.append(el("h3", "", "版本变更 · 对比片段"));
    const chooser = el("select");
    chooser.setAttribute("aria-label", "变更文件");
    for (const name of changedFiles(a, z)) {
      const o = el("option", "", name);
      o.value = name;
      chooser.append(o);
    }
    const pre = el("pre", "diff-source");
    let seq = 0;
    const show = async () => {
      const n = ++seq,
        p = chooser.value;
      try {
        const x = a.modules.find((m) => m.file === p),
          y = z.modules.find((m) => m.file === p);
        const [l, r] = await Promise.all([
          x ? content(x.artifact_id!) : Promise.resolve(""),
          y ? content(y.artifact_id!) : Promise.resolve(""),
        ]);
        if (n === seq) renderDiff(pre, simpleDiff(l, r));
      } catch (e) {
        if (n === seq) pre.textContent = errorText(e);
      }
    };
    chooser.onchange = () => void show();
    box.append(chooser, pre);
    root.append(box);
    if (chooser.options.length) void show();
    else pre.textContent = "没有代码差异。";
  }
  const list = el("details", "card");
  list.append(
    el("summary", "", "候选验证记录 · " + (b.trial_count ?? "未记录")),
  );
  for (const e of studioModel(b).trials) {
    const v = b.validations.find((v) => v.validation_id === e.validation_id);
    const row = button(
      e.text + (v ? " ↗" : " · 仅保存摘要"),
      () => v && select(v),
      "attempt-record",
    );
    row.disabled = !v;
    list.append(row);
  }
  root.append(list);
  if (after) {
    root.append(
      note(
        "最终系统复验：" +
          (after.verdict === "pass" ? "PASS" : "未通过") +
          " · " +
          after.mismatched_samples +
          " / " +
          after.total_samples,
      ),
    );
    root.append(
      button("查看修复后 · 最终复验", () => select(after), "primary"),
    );
  }
  return root;
}
export { changedFiles };
