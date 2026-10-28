import { assertWave, convertTicks } from "./evidence-selection";
import {
  state,
  validation,
  version,
  historicalRun,
  historicalEvents,
  type Validation,
} from "./state";
import { content, wave } from "./api";
import { el, button, note, hash, modal, errorText } from "./dom";
import { waveform } from "./waveform";
import { probeSamples } from "./probe-samples";
export const verdictText = (v: string) =>
  ({ pass: "通过", fail: "未通过", unverified: "未验证" })[v] || v;
export function verification(
  select: (v: Validation) => void,
  onContext: () => void,
  options?: { validation: Validation },
) {
  const root = el("section", "verification");
  const b = state.bundle!;
  const bar = el("div", "verification-toolbar");
  const run = historicalRun();
  const choices =
    state.mode === "live"
      ? state.liveRun?.validations || []
      : run
        ? [
            run.validations.find(
              (v) => v.validation_id === run.initial_validation_id,
            )!,
            run.validations.find(
              (v) => v.validation_id === run.final_validation_id,
            )!,
          ]
        : [
            b.validations.find(
              (v) => v.validation_id === b.comparison_pair.before_validation_id,
            )!,
            b.validations.find(
              (v) => v.validation_id === b.comparison_pair.after_validation_id,
            )!,
          ].filter((v): v is Validation => !!v);
  for (const [i, v] of choices.entries()) {
    if (
      state.replayIndex >= 0 &&
      !historicalEvents()
        .slice(0, state.replayIndex + 1)
        .some((e) => e.validation_id === v.validation_id)
    )
      continue;
    bar.append(
      button(
        run
          ? v.kind === "initial_system"
            ? "初始仿真"
            : "最终复验"
          : state.mode === "live"
            ? v.kind === "final_system"
              ? "独立最终复验"
              : "候选 " + (i + 1)
            : v.validation_id === b.comparison_pair.before_validation_id
              ? "修复前 · trial 5"
              : b.comparison_pair.before_validation_id
                ? "修复后 · 最终复验"
                : "系统最终复验",
        () => select(v),
        state.context.validation_id === v.validation_id
          ? "segment active"
          : "segment",
      ),
    );
  }
  if (!options) root.append(bar);
  const v = options?.validation || validation();
  if (!v) {
    root.append(note("本阶段还没有验证结果。"));
    return root;
  }
  const final = run
    ? run.validations.find((x) => x.validation_id === run.final_validation_id)
    : b.validations.find(
        (x) => x.validation_id === b.comparison_pair.after_validation_id,
      );
  if (
    !options &&
    state.mode === "historical" &&
    v.verdict === "fail" &&
    final?.verdict === "pass"
  ) {
    const explanation = el(
      "div",
      "history-explanation",
      "这是修复前的历史失败记录，不是当前最终结果；本案例最终系统复验已通过。",
    );
    explanation.append(
      button("查看最终通过结果", () => select(final), "text-button"),
    );
    root.append(explanation);
  }
  const metrics = el("div", "verification-metrics");
  const result = el("div", "result " + v.verdict);
  result.append(
    el(
      "span",
      "eyebrow",
      v.kind === "final_system"
        ? v.verification_scope === "saved_final_result"
          ? "系统最终验证"
          : "独立系统复验"
        : v.kind === "initial_system"
          ? "初始系统仿真"
          : v.kind === "syntax"
            ? "语法检查 · 未运行仿真"
            : v.kind === "edit_only"
              ? "代码修改 · 未单独验证"
              : "候选仿真",
    ),
    el("strong", "", verdictText(v.verdict)),
  );
  const samples = el("div", "sample-metric");
  samples.append(
    el(
      "strong",
      "",
      `${v.mismatched_samples ?? "—"} / ${v.total_samples ?? "—"}`,
    ),
    el(
      "span",
      "muted",
      v.total_samples == null ? "报告未记录采样统计" : "差异采样 / 总采样",
    ),
  );
  const reportButton = button(
    "查看验证报告 ↗",
    async () => {
      try {
        modal(
          "验证报告 · " + v.validation_id,
          await content(v.report_artifact_id),
        );
      } catch (e) {
        modal("加载失败", errorText(e));
      }
    },
    "text-button",
  );
  metrics.append(result, samples, reportButton);
  root.append(metrics);
  if (v.signal_counter_status === "verified")
    root.append(
      note("报告各输出差异计数及首次时刻已与本版VCD测试平台计数核对。"),
    );
  if (v.signal_mismatches?.length) {
    const signals = el("div", "signal-mismatches");
    for (const s of v.signal_mismatches)
      signals.append(
        note(
          `${s.signal}：${s.count} 次差异 · 首次 ${s.first_failure_ticks} ps`,
        ),
      );
    signals.append(
      note("各输出分别计数，不相加为不匹配采样数；报告未记录总采样数。"),
    );
    root.append(signals);
  }
  if (v.verification_scope === "saved_final_result")
    root.append(note("这是最后一次保存的通过结果，未发现另一次独立复验记录。"));
  if (v.report_scope === "recorded_tool_excerpt")
    root.append(
      note("验证报告为当时工具返回的原始摘录，完整中间报告已被覆盖。"),
    );
  const binding = el(
    "div",
    "binding-line mono",
    "RTL " +
      hash(
        b.versions.find((x) => x.version_id === v.version_id)?.tree_sha256 ||
          version()?.tree_sha256,
      ) +
      "  ·  VCD " +
      hash(v.waveform_sha256),
  );
  binding.title =
    "版本 " +
    v.version_id +
    "\n验证 " +
    v.validation_id +
    "\n" +
    (v.binding_level === "full_input_manifest"
      ? "完整受测环境指纹"
      : "候选记录绑定");
  root.append(binding);
  if (
    v.internal_mismatch_count != null &&
    v.internal_mismatch_count !== v.mismatched_samples
  )
    root.append(
      note(
        "内部差异计数 " +
          v.internal_mismatch_count +
          "（独立于采样点统计，不能作为不匹配采样数）",
      ),
    );
  if (state.mode === "historical" && !options) {
    const counts = note(
      (run
        ? run.label +
          " · " +
          run.attempts.length +
          (run.attempts.some((a) => a.lint_pass === null)
            ? " 次候选修改。"
            : " 次候选验证。")
        : b.trial_count == null
          ? "候选验证次数未记录。"
          : "本案例共 " + b.trial_count + " 次候选验证（含语法失败）。") +
        "结论仅适用于对应版本和本次测试。",
    );
    root.append(counts);
  }
  const heading = el("div", "wave-heading");
  const title = el("div");
  title.append(
    el("strong", "", "DUT / Reference"),
    note("DUT＝生成设计 · Reference＝参考设计 · 结果按测试平台采样判定"),
  );
  let jump: ((t: string) => void) | null = null;
  if (v.first_failure_ticks)
    heading.append(
      button(
        (v.waveform_artifact_id ? "定位差异 · " : "查看差异附近探针 · ") +
          v.first_failure_ticks +
          " ps",
        () => jump?.(v.first_failure_ticks!),
        "failure-jump",
      ),
    );
  heading.prepend(title);
  root.append(heading);
  const target = el("div");
  target.append(
    note(
      v.waveform_artifact_id
        ? "加载真实波形…"
        : v.waveform_note || "本次验证没有产生波形。",
    ),
  );
  root.append(target);
  if (!v.waveform_artifact_id && v.probe_samples?.length) {
    const probes = probeSamples(v);
    root.append(probes.element);
    jump = probes.jump;
  }
  const waveError = el("p", "muted");
  root.append(waveError);
  let loadId = 0;
  async function loadWave(range?: [bigint, bigint]) {
    const token = ++loadId,
      previous = state.viewport;
    if (range) state.viewport = range;
    try {
      let data = await wave(v!.validation_id, range);
      if (token !== loadId || !root.isConnected) return;
      assertWave(v!, data);
      if (state.waveScale && state.viewport) {
        try {
          state.viewport = [
            convertTicks(state.viewport[0], state.waveScale, data.timescale),
            convertTicks(state.viewport[1], state.waveScale, data.timescale),
          ];
          if (state.cursor !== null)
            state.cursor = convertTicks(
              state.cursor,
              state.waveScale,
              data.timescale,
            );
        } catch {
          state.viewport = null;
          state.cursor = null;
          waveError.textContent = "时间范围无法精确对齐，已切换当前波形范围。";
        }
      }
      state.waveScale = data.timescale;
      let alignment = "";
      if (state.viewport) {
        const hi = BigInt(data.full_end_ticks || data.end_ticks);
        const a = state.viewport[0] < 0n ? 0n : state.viewport[0],
          b = state.viewport[1] > hi ? hi : state.viewport[1];
        if (b <= a) {
          state.viewport = null;
          state.cursor = null;
          alignment = "两次仿真没有重叠窗口，已显示当前波形。";
        } else {
          state.viewport = [a, b];
          if (state.cursor !== null)
            state.cursor =
              state.cursor < a ? a : state.cursor >= b ? b - 1n : state.cursor;
          if (a < BigInt(data.start_ticks) || b > BigInt(data.end_ticks)) {
            data = await wave(v!.validation_id, [a, b]);
            assertWave(v!, data);
            if (token !== loadId || !root.isConnected) return;
          }
        }
      }
      if (!state.viewport && v!.first_failure_ticks) {
        const t = BigInt(v!.first_failure_ticks);
        state.viewport = [t > 100n ? t - 100n : 0n, t + 150n];
        state.cursor = t;
      }
      const w = waveform(data, onContext, (r) => void loadWave(r));
      jump = w.jump;
      target.replaceChildren(w.element);
      waveError.textContent = alignment;
      if (range) onContext();
    } catch (e) {
      if (token !== loadId) return;
      state.viewport = previous;
      waveError.textContent = errorText(e);
      if (!target.querySelector(".wave-panel"))
        target.replaceChildren(note("本次波形暂不可用。"));
    }
  }
  if (v.waveform_artifact_id) void loadWave();
  if (state.mode === "historical") root.append(note(b.binding_note));
  if (state.mode === "live" && state.liveRun?.attempts?.length) {
    const list = el("div", "attempts");
    list.append(el("strong", "", "修复记录"));
    for (const a of state.liveRun.attempts) {
      const val = state.liveRun.validations.find(
        (v) => v.validation_id === a.validation_id,
      );
      list.append(
        button(
          `候选 ${a.trial_no} · ${a.decision === "accepted" ? "接受" : a.decision === "rolled_back" ? "回滚" : "评估中"}${val ? " · " + verdictText(val.verdict) : ""}`,
          () => {
            if (val) select(val);
          },
          "text-button",
        ),
      );
    }
    root.append(list);
  }
  return root;
}
