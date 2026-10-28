import { el, note } from "./dom";
import type { StoryView } from "./stories";
export const optimizationCopy = {
  title: "每一轮设计，都有下一次改进的方向。",
  status: "PPA 数据待接入",
  steps: ["提出设计候选", "功能验证", "同条件测量", "保留或放弃"],
};
export function optimization(story: StoryView | null) {
  const root = el("div", "story-page optimization-page");
  root.append(
    el("div", "eyebrow", "RI · RECURRENT IMPROVEMENT"),
    el("h1", "", optimizationCopy.title),
    note(
      "RI 关注设计本身：我们希望 Agent 围绕功能与工程目标反复提出方案、评估结果，再把反馈带回下一轮设计。",
    ),
  );
  const card = el("section", "story-card pending-card");
  card.append(
    el("span", "evidence-state", optimizationCopy.status),
    el("h2", "", "先证明功能，再比较工程指标。"),
    note(
      "后续将接入真实的面积、时序与可用功耗数据。当前功能仿真结果不等同于 PPA 优化成绩。",
    ),
  );
  const flow = el("ol", "story-flow");
  for (const step of optimizationCopy.steps) flow.append(el("li", "", step));
  card.append(flow, note("流程说明 · 当前未执行 PPA 实验"));
  const missing = el("ul", "evidence-gaps");
  for (const text of story?.optimization.missing_evidence || [
    "同条件的基线与候选测量",
    "测量报告与 RTL、功能验证的绑定",
  ])
    missing.append(el("li", "", text));
  card.append(el("h3", "", "接入所需依据"), missing);
  root.append(card);
  return root;
}
