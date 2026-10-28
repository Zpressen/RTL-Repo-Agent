import { el, note, button } from "./dom";

// Presentation of a proposed mechanism, independent of measured run results.
export const evolutionSteps = [
  {
    title: "观测",
    english: "OBSERVE",
    hint: "看见执行过程",
    headline: "先看见，Agent 是如何完成任务的。",
    description:
      "让执行轨迹、工具反馈和验证结果成为反馈来源，理解任务在哪里推进、在哪里受阻。",
    example:
      "一次模块集成出现接口不匹配。我们希望 Agent 能保留问题发生的上下文，而不只看到最后的报错。",
    tags: ["任务轨迹", "工具反馈", "仿真结果"],
  },
  {
    title: "评估",
    english: "EVALUATE",
    hint: "理解成败原因",
    headline: "从“做完了吗”，走向“方法合适吗”。",
    description:
      "围绕设计目标审视结果，也回看规划、工具选择与修复路径，识别值得保留的做法和需要调整的环节。",
    example:
      "面对接口问题，可以回看：模块拆分是否合理？契约是否清楚？问题是否本可以在集成前发现？",
    tags: ["结果质量", "过程复盘", "策略判断"],
  },
  {
    title: "记忆",
    english: "REMEMBER",
    hint: "把反馈变成经验",
    headline: "留下解决问题的方法，带上适用边界。",
    description:
      "把一次任务中的有效做法、失败原因与使用条件沉淀为可复用经验，让下一次任务有机会从已有认知出发。",
    example:
      "将这次问题提炼为一条带条件的经验：多模块协作时，先确认接口契约，再推进并行实现。",
    tags: ["设计经验", "失败边界", "适用条件"],
  },
  {
    title: "改进",
    english: "ADAPT",
    hint: "调整下一次决策",
    headline: "经验的价值，体现在下一次行动里。",
    description:
      "在新任务中选择相关经验，辅助调整任务规划、工具使用与检查顺序；随着新反馈，修订或淘汰旧方法。",
    example:
      "下一次遇到类似系统，Agent 可以优先检查模块接口，并把集成检查提前到规划阶段。",
    tags: ["规划调整", "工具选择", "经验修订"],
  },
  {
    title: "再验证",
    english: "VERIFY",
    hint: "让新方法接受检验",
    headline: "改进是否有效，再交给任务检验。",
    description:
      "把新的做法带回实际任务，重新观测与评估。有效的经验继续积累，新的失败也成为下一轮改进的起点。",
    example:
      "再检查新任务的接口一致性与功能仿真，并比较前后的过程：这条经验是否适用，是否还需要补充边界？",
    tags: ["任务反馈", "效果评估", "下一轮迭代"],
  },
];
let selectedStep = 0;

export function evolutionNarrative() {
  const root = el("section", "evolution-narrative");
  const heading = el("div", "evolution-heading");
  heading.append(
    el("h2", "", "让任务的终点，成为进化的起点。"),
    el("span", "concept-badge", "机制构想"),
  );
  root.append(
    heading,
    note("点击一个环节，看看一次任务的反馈如何进入下一轮决策。"),
  );

  const cycle = el("div", "evolution-cycle");
  cycle.setAttribute("role", "group");
  cycle.setAttribute("aria-label", "自进化反馈循环");
  const detail = el("div", "evolution-detail");
  detail.setAttribute("aria-live", "polite");
  const controls: HTMLButtonElement[] = [];
  function renderStep() {
    const step = evolutionSteps[selectedStep];
    controls.forEach((control, i) => {
      control.classList.toggle("active", i === selectedStep);
      control.setAttribute("aria-pressed", String(i === selectedStep));
    });
    const copy = el("div", "evolution-step-copy");
    copy.append(
      el("span", "eyebrow", step.english),
      el("h3", "", step.headline),
      note(step.description),
    );
    const tags = el("div", "evolution-tags");
    for (const tag of step.tags) tags.append(el("span", "", tag));
    copy.append(tags);
    const scenario = el("div", "evolution-example");
    scenario.append(
      el("span", "eyebrow", "场景推演 · 模块集成"),
      el("p", "", step.example),
    );
    detail.replaceChildren(copy, scenario);
  }
  evolutionSteps.forEach((step, i) => {
    const control = button(
      "",
      () => {
        selectedStep = i;
        renderStep();
      },
      "evolution-node",
    );
    control.setAttribute("aria-label", step.title);
    control.append(
      el("span", "evolution-number", String(i + 1).padStart(2, "0")),
      el("strong", "", step.title),
      el("span", "evolution-hint", step.hint),
    );
    controls.push(control);
    cycle.append(control);
  });
  root.append(
    cycle,
    el("div", "evolution-return", "↶  新的反馈，回到下一轮观测与决策"),
    detail,
  );
  renderStep();

  const memory = el("section", "evolution-memory");
  memory.append(el("h2", "", "记住的不只是答案，还有方法。"));
  const cards = el("div", "evolution-memory-grid");
  for (const [title, text] of [
    ["设计经验", "哪些拆分方式、接口约定和实现路径值得在类似任务中参考。"],
    ["失败边界", "哪些尝试走过弯路，经验在什么条件下适用，又在哪里需要谨慎。"],
    ["任务策略", "如何安排规划、工具调用与验证，让经验影响下一次行动。"],
  ]) {
    const card = el("article", "evolution-memory-card");
    card.append(el("h3", "", title), note(text));
    cards.append(card);
  }
  memory.append(cards);
  root.append(memory);

  const levels = el("section", "evolution-levels");
  levels.append(el("h2", "", "设计在迭代，解决问题的方法也在迭代。"));
  const pair = el("div", "evolution-level-grid");
  for (const [label, title, text] of [
    [
      "RI · 改进设计",
      "让这一版设计更好",
      "围绕当前规格，反复提出候选、验证与评估，逐步优化设计结果。",
    ],
    [
      "RSI · 改进方法",
      "让下一次决策更有经验",
      "用任务反馈更新记忆与策略，让 Agent 逐步形成可以积累、复用和修订的工程方法。",
    ],
  ]) {
    const card = el("article", "evolution-level");
    card.append(el("span", "eyebrow", label), el("h3", "", title), note(text));
    pair.append(card);
  }
  levels.append(pair);
  root.append(levels);
  root.append(
    el(
      "p",
      "evolution-vision",
      "我们的愿景：让每一次芯片设计，都成为下一次设计的经验。",
    ),
    el(
      "p",
      "concept-footnote",
      "本页展示自进化机制与演进方向，场景为说明性推演；实际能力与效果以工程验证为准。",
    ),
  );
  return root;
}
