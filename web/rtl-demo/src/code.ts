import { state, version } from "./state";
import { content, request } from "./api";
import { el, button, note, hash, errorText } from "./dom";
import { changedFiles } from "./evidence-selection";
export function code(onSelect?: () => void) {
  const root = el("section", "code-panel"),
    v = version();
  if (!v) {
    root.append(note("本阶段尚未展示 RTL。"));
    return root;
  }
  const files = el("aside", "file-tree");
  files.append(
    el("div", "eyebrow", "RTL / " + v.file_manifest.length + " 个文件"),
  );
  const body = el("div", "code-body"),
    toolbar = el("div", "code-toolbar"),
    path = el("strong", "code-path mono"),
    meta = note(
      "版本 " + v.version_id + " · " + hash(v.tree_sha256) + " · 只读",
    );
  const pre = el("pre", "code-source");
  pre.tabIndex = 0;
  toolbar.append(
    path,
    button(
      "查看修复差异",
      async () => {
        try {
          if (state.mode === "live" && v.parent_version_id) {
            pre.textContent = (
              await request<{ content: string }>(
                "/versions/" +
                  v.version_id +
                  "/diff?base_version_id=" +
                  encodeURIComponent(v.parent_version_id),
              )
            ).content;
            return;
          }
          const before = state.bundle!.versions.find(
            (x) =>
              x.version_id ===
              state.bundle!.validations.find(
                (x) =>
                  x.validation_id ===
                  state.bundle!.comparison_pair.before_validation_id,
              )?.version_id,
          );
          const after = state.bundle!.versions.find(
            (x) =>
              x.version_id ===
              state.bundle!.validations.find(
                (x) =>
                  x.validation_id ===
                  state.bundle!.comparison_pair.after_validation_id,
              )?.version_id,
          );
          if (!before || !after) {
            pre.textContent = "未保存可配对的修复前 RTL。";
            return;
          }
          const p = path.textContent!;
          const a = before.modules.find((m) => m.file === p),
            b = after.modules.find((m) => m.file === p);
          renderDiff(
            pre,
            "对比片段 · " +
              p +
              "\n" +
              simpleDiff(
                a ? await content(a.artifact_id!) : "",
                b ? await content(b.artifact_id!) : "",
              ),
          );
        } catch (e) {
          pre.textContent = errorText(e);
        }
      },
      "text-button",
    ),
  );
  body.append(toolbar, meta, pre);
  root.append(files, body);
  let seq = 0;
  async function load(p: string) {
    const token = ++seq;
    path.textContent = p;
    pre.textContent = "加载 RTL…";
    const m = v!.modules.find((x) => x.file === p);
    state.context.module_id = m?.module_id;
    for (const x of files.querySelectorAll("button"))
      x.classList.toggle("active", x.dataset.file === p);
    try {
      const text = m?.artifact_id
        ? await content(m.artifact_id)
        : "文件映射缺失。";
      if (token === seq) pre.textContent = text;
    } catch (e) {
      if (token === seq) pre.textContent = errorText(e);
    }
  }
  for (const f of v.file_manifest) {
    const b = button(
      f.path,
      () => {
        void load(f.path);
        onSelect?.();
      },
      "file-item mono",
    );
    b.dataset.file = f.path;
    files.append(b);
  }
  const selected =
    v.modules.find((m) => m.module_id === state.context.module_id)?.file ||
    v.modules.find(
      (m) =>
        m.module_id ===
        state.bundle?.modules.find((m) => !m.parents?.length)?.module_id,
    )?.file ||
    v.file_manifest[0]?.path;
  if (selected) void load(selected);
  return root;
}
// Prefix/suffix aligned excerpt, explicitly labelled; full source remains available in module view.
export function simpleDiff(a: string, b: string) {
  const left = a.split("\n"),
    right = b.split("\n");
  let start = 0;
  while (
    start < left.length &&
    start < right.length &&
    left[start] === right[start]
  )
    start++;
  let end = 0;
  while (
    end < left.length - start &&
    end < right.length - start &&
    left[left.length - 1 - end] === right[right.length - 1 - end]
  )
    end++;
  if (start === left.length && start === right.length) return "代码相同。";
  return (
    "修复前 / 修复后 · 共同前后文已折叠\n\n" +
    left
      .slice(Math.max(0, start - 3), start)
      .map((x) => "  " + x)
      .join("\n") +
    "\n" +
    left
      .slice(start, left.length - end)
      .map((x) => "- " + x)
      .join("\n") +
    "\n" +
    right
      .slice(start, right.length - end)
      .map((x) => "+ " + x)
      .join("\n") +
    "\n" +
    right
      .slice(right.length - end, right.length - end + 3)
      .map((x) => "  " + x)
      .join("\n")
  );
}

export function renderDiff(target: HTMLElement, text: string) {
  target.replaceChildren(
    ...text
      .split("\n")
      .map((line) =>
        el(
          "span",
          "diff-line " +
            (line.startsWith("+")
              ? "diff-add"
              : line.startsWith("-")
                ? "diff-remove"
                : "diff-context"),
          line || " ",
        ),
      ),
  );
}
