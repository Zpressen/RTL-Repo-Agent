import { el, note, button } from "./dom";
import { state } from "./state";
import { evolutionNarrative } from "./evolution";
import {
  stageLabels,
  readinessLabels,
  applicationFacts,
  resultForUse,
  type StoryView,
  type MemoryRevision,
  type MemoryUse,
} from "./stories";
export function experience(
  story: StoryView | null,
  select: (m: MemoryRevision, use?: MemoryUse) => void,
  open: (runId: string, validationId?: string, versionId?: string) => void,
) {
  const root = el("div", "story-page experience-page");
  root.append(
    el("div", "eyebrow", "SELF-EVOLVING AGENT · RSI"),
    el("h1", "", "不止完成任务，更让经验持续生长。"),
    note(
      "我们希望 Agent 能从执行中观测，从反馈中评估，把经验带入下一次决策，逐步改进解决问题的方法。",
    ),
  );
  root.append(evolutionNarrative());
  const e = story?.experience;
  const records = el("details", "evolution-records");
  records.append(el("summary", "", "查看工程经验记录"));
  const archive = el("div", "evolution-archive");
  records.append(archive);
  root.append(records);
  records.open = Boolean(state.context.memory_revision_id);
  archive.append(
    el(
      "span",
      "evidence-state",
      readinessLabels[e?.state || "empty"] || "证据待核查",
    ),
  );
  if (state.storyError) {
    const error = el("p", "context-error", "证据不可用：" + state.storyError);
    error.setAttribute("role", "alert");
    root.prepend(error);
  }
  if (!e?.memories.length) {
    archive.append(
      note(
        "工程经验记录将随实际任务接入。上方机制说明不代表已经完成真实跨任务复用或效果验证。",
      ),
    );
    return root;
  }
  const selected = e.memories.find(
    (m) => m.revision_id === state.context.memory_revision_id,
  );
  const list = el("div", "memory-list");
  for (const m of e.memories)
    list.append(
      button(
        m.title + " · " + m.revision_id.slice(-8),
        () => select(m),
        selected?.revision_id === m.revision_id
          ? "memory-choice active"
          : "memory-choice",
      ),
    );
  archive.append(list);
  if (!selected) {
    archive.append(note("选择一条经验，查看固定版本及实际使用依据。"));
    return root;
  }
  const card = el("article", "story-card");
  const status =
    {
      draft: "草稿",
      approved_active: "已审核",
      superseded: "已有修订",
      retired: "已淘汰",
    }[selected.state] || selected.state;
  card.append(
    el("h2", "", selected.title),
    el("span", "evidence-state", status + " · 历史归档"),
    el("p", "memory-lesson", selected.lesson),
    note(
      "来源后端：" +
        selected.backend +
        " · 验证层级：" +
        selected.validation_level,
    ),
    button(
      "查看来源运行 ↗",
      () =>
        open(
          selected.source_run_id,
          undefined,
          selected.source_version_id || undefined,
        ),
      "evidence-button",
    ),
  );
  for (const [title, items] of [
    ["适用条件", selected.applicability],
    ["适用限制", selected.limitations],
  ] as const) {
    card.append(el("h3", "", title));
    for (const text of items) card.append(note(text));
    if (!items.length) card.append(note("未记录"));
  }
  const uses = e.uses.filter((u) => u.revision_id === selected.revision_id);
  card.append(el("h3", "", "后续检索与使用记录"));
  if (!uses.length)
    card.append(note("未记录跨运行复用。已沉淀不代表已被采用。"));
  for (const use of uses) {
    const block = el("section", "use-chain");
    block.append(note("后续运行：" + use.run_id + " · " + use.backend));
    if (!applicationFacts(use.events).adopted)
      block.append(note("未记录实际采用；以下仅展示已发生阶段。"));
    for (const event of use.events) {
      const verdict = resultForUse(use, event, story?.runs || []);
      block.append(
        el(
          "p",
          "",
          (stageLabels[event.kind] || event.kind) +
            (event.kind === "validation_observed"
              ? " · " + verdict.toUpperCase()
              : "") +
            (event.reason ? " · " + event.reason : ""),
        ),
      );
      if (event.validation_id)
        block.append(
          button(
            "查看对应验证与波形 ↗",
            () => {
              select(selected, use);
              open(use.run_id, event.validation_id!);
            },
            "evidence-button",
          ),
        );
    }
    card.append(block);
  }
  card.append(el("h3", "", "修订与淘汰"));
  const changes = e.lifecycle_events.filter(
    (ev) =>
      ev.revision_id === selected.revision_id ||
      ev.replacement_revision_id === selected.revision_id,
  );
  if (!changes.length) card.append(note("未记录有据修订。"));
  for (const ev of changes) card.append(note(ev.kind + " · " + ev.reason));
  if (selected.parent_revision_id && !uses.length)
    card.append(note("新版尚未再次使用，效果待验证。"));
  card.append(
    el("h3", "", "记忆收益"),
    note(
      e.comparisons.length
        ? "仅按记录的条件和样本范围解释，不推广为普遍收益。"
        : "收益待验证 · 当前没有同条件启用/禁用记忆对照。",
    ),
  );
  for (const comp of e.comparisons) card.append(note(comp.message));
  archive.append(card);
  return root;
}
