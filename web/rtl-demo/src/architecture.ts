import { state, type Module } from "./state";
import { el, button, note } from "./dom";
const roles: Record<string, string> = {
  aes_sbox: "正向 S-box",
  aes_inv_sbox: "逆向 S-box",
  aes_rcon: "轮常量",
  aes_key_expand: "密钥扩展",
  aes_key_expand_128: "128 位密钥扩展",
  aes_cipher_top: "加密顶层控制",
  aes_inv_cipher_top: "解密顶层控制",
  sdc_controller: "SDC 顶层控制",
  sdc_serial_engine: "串行收发引擎",
  sdc_stream_buffers: "数据流缓冲",
  sdc_system_control: "系统控制",
  sdc_transfer_engine: "传输控制",
  amo_sequence: "原子操作序列",
  branch_jump: "分支与跳转",
  csr: "CSR 控制",
  memory_transaction: "访存事务",
  muldiv: "乘除法",
  nice_forwarding: "NICE 扩展转发",
  regular_integer: "整数运算",
  shared_arithmetic_datapath: "共享算术数据通路",
  alu_system: "顶层调度与结果整合",
};
export const label = (id: string) => roles[id.replace("e203_exu_", "")] || id;
export function architecture(open: (m: Module) => void, openSpec: () => void) {
  const root = el("section", "architecture");
  const intro = el("div", "section-heading");
  intro.append(
    el("div", "", "从规格到可验证的多模块设计"),
    button("查看原始规格 ↗", openSpec, "text-button"),
  );
  root.append(intro, note(state.bundle!.title + " · 原始规划中的模块关系"));
  const details = el("details", "spec-summary");
  details.append(
    el("summary", "", "系统规格摘要"),
    note(state.bundle!.summary),
  );
  root.append(details);
  const modules =
    state.mode === "live"
      ? state.liveRun?.modules || []
      : state.bundle!.modules;
  if (!modules.length) {
    root.append(note("本次实时运行尚未产生模块规划。"));
    return root;
  }
  const children = new Set(modules.flatMap((m) => m.children || []));
  const top = modules.find((m) => !children.has(m.module_id));
  const nested = modules.some((m) =>
    (m.parents || []).some((p) => p !== top?.module_id),
  );
  const tree = el("div", nested ? "module-tree nested" : "module-tree");
  if (top) {
    const b = button("", () => open(top), "module-top");
    b.append(
      el("span", "eyebrow", "TOP MODULE"),
      el("strong", "mono", top.module_id),
      el("span", "muted", label(top.module_id)),
    );
    tree.append(b);
  }
  const grid = el("div", "module-grid");
  for (const m of modules.filter((m) => m !== top)) {
    const b = button("", () => open(m), "module-card");
    b.append(
      el("span", "module-icon", "◇"),
      el("strong", "", label(m.module_id)),
      el("span", "mono", m.module_id.replace("e203_exu_", "")),
    );
    if (nested)
      b.append(
        el(
          "span",
          "muted",
          "调用方：" + (m.parents || []).map(label).join(" / "),
        ),
      );
    if (state.mode === "live")
      b.append(
        el(
          "span",
          "muted",
          {
            completed: "生成完成",
            planned: "已规划",
            failed: "生成失败",
            in_progress: "生成中",
          }[m.status || ""] ||
            m.status ||
            "状态未记录",
        ),
      );
    b.title = m.role || m.module_id;
    grid.append(b);
  }
  tree.append(grid);
  root.append(tree);
  const flow = el("div", "design-flow");
  ["系统规格", "模块与接口", "RTL 实现", "仿真与修复", "独立复验"].forEach(
    (s, i) => {
      flow.append(el("span", "", s));
      if (i < 4) flow.append(el("span", "muted", "→"));
    },
  );
  root.append(
    flow,
    note(
      "点击模块查看对应 RTL。历史阶段的原始时间未记录，回放按展示节奏压缩。",
    ),
  );
  return root;
}
