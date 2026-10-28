import { el } from "./dom";
import { views, type View } from "./router";
export const viewNames: Record<View, string> = {
  workspace: "设计工作台",
  optimization: "持续优化 · RI",
  experience: "自进化 · RSI",
};
export function navigation(beforeLeave: () => void) {
  const nav = el("nav", "primary-nav");
  nav.setAttribute("aria-label", "主导航");
  for (const view of views) {
    const a = el("a", "primary-link", viewNames[view]);
    a.href = "#/" + view;
    a.dataset.view = view;
    a.onclick = beforeLeave;
    nav.append(a);
  }
  return {
    element: nav,
    update: (view: View) => {
      for (const a of nav.querySelectorAll("a")) {
        a.classList.toggle("active", a.dataset.view === view);
        if (a.dataset.view === view) a.setAttribute("aria-current", "page");
        else a.removeAttribute("aria-current");
      }
    },
  };
}
