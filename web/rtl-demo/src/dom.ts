export function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  cls = "",
  text?: string,
): HTMLElementTagNameMap[K] {
  const n = document.createElement(tag);
  n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}
export function button(
  text: string,
  action: () => void,
  cls = "",
): HTMLButtonElement {
  const b = el("button", cls, text);
  b.type = "button";
  b.onclick = action;
  return b;
}
export function note(text: string) {
  return el("p", "muted", text);
}
export function hash(text?: string) {
  return text?.slice(0, 12) || "未记录";
}
export const errorText = (e: unknown) =>
  e instanceof Error ? e.message : "操作暂不可用";
export function modal(title: string, text: string) {
  const d = el("dialog", "artifact-dialog");
  const h = el("div", "dialog-head");
  h.append(
    el("strong", "", title),
    button("关闭", () => d.close()),
  );
  const p = el("pre", "artifact-text", text);
  d.append(h, p);
  document.body.append(d);
  d.onclose = () => d.remove();
  d.showModal();
}
