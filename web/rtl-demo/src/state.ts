export type Panel = "spec" | "architecture" | "code" | "verify" | "repair";
export type CaseId =
  | "e203"
  | "aes_cipher_system_hard"
  | "aes_inv_cipher_top_system"
  | "sdc_controller_system";
export const activeCase = (): CaseId => {
  if (typeof location === "undefined") return "e203";
  const id = new URLSearchParams(location.search).get("case");
  return [
    "aes_cipher_system_hard",
    "aes_inv_cipher_top_system",
    "sdc_controller_system",
  ].includes(id || "")
    ? (id as CaseId)
    : "e203";
};
export type CaseEntry = {
  case_id: CaseId;
  title: string;
  subtitle: string;
  available: boolean;
};
export type Context = {
  case_id: CaseId;
  workspace_panel?: Panel;
  view?: "workspace" | "optimization" | "experience";
  story_id?: string;
  memory_revision_id?: string;
  memory_use_id?: string;
  run_id?: string;
  version_id?: string;
  validation_id?: string;
  module_id?: string;
  signal_id?: string;
  time_range?: string[];
};
export type Module = {
  module_id: string;
  role?: string;
  status?: string;
  children?: string[];
  parents?: string[];
  artifact_id?: string;
  file?: string;
  sha256?: string;
};
export type Version = {
  version_id: string;
  run_id: string;
  tree_sha256: string;
  parent_version_id?: string;
  modules: Module[];
  file_manifest: { path: string; sha256: string }[];
};
export type Validation = {
  validation_id: string;
  run_id: string;
  version_id: string;
  kind: string;
  verdict: "pass" | "fail" | "unverified";
  simulation_completed: boolean;
  total_samples: number | null;
  mismatched_samples: number | null;
  internal_mismatch_count?: number | null;
  first_failure_ticks: string | null;
  report_artifact_id: string;
  waveform_artifact_id?: string;
  waveform_sha256?: string;
  marker_status: string;
  binding_level: string;
  verifier_fingerprint?: string;
  signal_mismatches?: {
    signal: string;
    count: number;
    first_failure_ticks: string;
  }[];
  probe_samples?: {
    time_ticks: string;
    signal: string;
    reference: string;
    dut: string;
    reference_path: string;
    dut_path: string;
  }[];
  probe_source_sha256?: string;
  waveform_note?: string;
  report_scope?: string;
  verification_scope?: string;
  signal_counter_status?: string;
};
export type ReplayEvent = {
  sequence: number;
  origin?: "historical" | "live";
  artifact_id?: string;
  trial_no?: number;
  stage: string;
  text: string;
  replay_delay_ms: number;
  validation_id?: string;
  version_id?: string;
  observed_at: string | null;
};
export type Bundle = {
  debug_history?: {
    schema_version: "rtl-debug-history-v1";
    source_fingerprint: string;
    history_fingerprint: string;
    runs: HistoricalRun[];
  };
  debug_trace?: DebugTrace;
  case_id: CaseId;
  subtitle?: string;
  bundle_id: string;
  source_fingerprint: string;
  title: string;
  summary: string;
  trial_count: number | null;
  source_run_id: string;
  spec_artifact_id: string;
  planner_artifact_id: string;
  binding_note: string;
  modules: Module[];
  versions: Version[];
  validations: Validation[];
  events: ReplayEvent[];
  comparison_pair: {
    before_validation_id: string | null;
    after_validation_id: string;
  };
  evidence_packages?: EvidencePackageIndex;
  content_urls?: Record<string, string>;
  waveform_urls?: Record<string, string>;
};
export type DebugTrial = {
  trial_no: number;
  candidate_id: string;
  intent: string;
  expected_effect: string;
  files: { path: string; change: string }[];
  lint_pass: boolean | null;
  simulation_completed: boolean;
  verdict: "pass" | "fail" | "unverified";
  lint_excerpt: string;
  signals: string[];
  alignment: string;
  decision: "accept" | "rollback" | "unrecorded";
  mismatch_count?: number;
  first_fail_time?: number;
};
export type DebugTrace = {
  schema_version: "rtl-agent-debug-trace-v1";
  case_id: string;
  bundle_id: string;
  source_run_id: string;
  source_fingerprint: string;
  journal_sha256: string;
  source: string;
  trials: DebugTrial[];
};
export type Operation = {
  operation_id: string;
  run_id: string;
  kind: string;
  state: string;
  stage?: string;
  verdict?: string;
  error?: string;
  version_id?: string;
  validation_id?: string;
};
export type Message = {
  message_id: string;
  text: string;
  answer?: string;
  state: string;
  evidence_refs?: { artifact_id: string }[];
  operation_id?: string;
  context_ref: Context;
  answer_source?: "recorded_evidence" | "model" | "unsupported_notice";
  created_at?: string;
  model_receipt?: {
    model?: string;
    elapsed_ms?: number;
    input_tokens?: number;
    output_tokens?: number;
    total_tokens?: number;
  } | null;
};
export type Session = {
  session_id: string;
  selection: Context & { browsing_mode: string; workspace_panel?: string };
  messages: Message[];
  operations: Operation[];
  last_event_id?: number;
};
export type Health = {
  release_id?: string;
  phase?: "candidate" | "production";
  capabilities: Record<string, { available: boolean; missing: string[] }>;
};
export type WaveSignal = {
  id: string;
  full_path: string;
  width: number;
  initial_value: string;
  changes: [string, string][];
};
export type Marker = {
  time_ticks: string;
  sample_index: number;
  verdict: "pass" | "fail";
  failed_signals: string[];
  sampled_value_available: false;
};
export type Wave = {
  validation_id: string;
  version_id: string;
  waveform_sha256: string;
  timescale: { value: number; unit: string };
  start_ticks: string;
  end_ticks: string;
  full_end_ticks?: string;
  signals: WaveSignal[];
  sample_markers: Marker[];
  missing_signals: string[];
  marker_status: string;
};
export type Run = {
  run_id: string;
  events?: ReplayEvent[];
  case_id?: CaseId;
  origin?: "historical" | "live";
  versions: Version[];
  validations: Validation[];
  modules?: Module[];
  attempts?: {
    diagnosis?: RootCause;
    trial_no: number;
    decision: string;
    validation_id?: string;
    candidate_version_id: string;
  }[];
};
export type HistoricalAttempt = {
  diagnosis?: RootCause;
  trial_no: number;
  candidate_revision: number;
  candidate_id: string;
  candidate_version_id: string;
  baseline_version_id: string;
  validation_id: string;
  before_validation_id: string;
  decision: "accepted" | "rolled_back" | "superseded";
  lint_pass: boolean | null;
  simulation_completed: boolean;
  debug: DebugTrial;
};
export type RootCause = {
  status: "recorded_hypothesis" | "unrecorded";
  recorded_at: "before_edit" | "validation_request" | "unrecorded";
  summary: string;
  baseline_version_id: string;
  before_validation_id: string;
  statements: {
    kind: "agent_message" | "patch_hypothesis" | "validation_reason";
    text: string;
    sha256: string;
    line: number;
    timing:
      | "before_code_edit"
      | "before_candidate_validation"
      | "at_validation_request";
  }[];
  locations: {
    file: string;
    start_line: number;
    end_line: number;
    source: "agent_target" | "candidate_change_range";
  }[];
};
export type HistoricalRun = Omit<Run, "attempts"> & {
  label: string;
  round_no: number;
  initial_validation_id: string;
  final_validation_id: string;
  attempts: HistoricalAttempt[];
};
const journeys = new WeakMap<Bundle, HistoricalRun>();
export function historyJourney(b: Bundle): HistoricalRun | undefined {
  const sources = b.debug_history?.runs;
  if (!sources?.length) return;
  if (journeys.has(b)) return journeys.get(b);
  const first = sources[0],
    last = sources.at(-1)!;
  const attempts: HistoricalAttempt[] = [],
    events: ReplayEvent[] = [];
  for (const [i, run] of sources.entries()) {
    const offset = attempts.length;
    attempts.push(
      ...run.attempts.map((a) => ({
        ...a,
        trial_no: offset + a.trial_no,
        debug: { ...a.debug, trial_no: offset + a.trial_no },
      })),
    );
    for (const original of run.events || []) {
      if (i > 0 && ["spec", "architecture", "rtl"].includes(original.stage))
        continue;
      const intermediate =
        (original.stage === "complete" && run !== last) ||
        (i > 0 && original.stage === "verify");
      events.push({
        ...original,
        sequence: events.length + 1,
        trial_no:
          original.trial_no != null ? offset + original.trial_no : undefined,
        stage: intermediate ? "repair" : original.stage,
        text:
          original.trial_no != null
            ? original.text.replace(
                "候选验证 " + original.trial_no,
                "候选验证 " + (offset + original.trial_no),
              )
            : intermediate
              ? "阶段验证仍有差异，继续修复"
              : original.stage === "complete"
                ? last.validations.find(
                    (v) => v.validation_id === last.final_validation_id,
                  )?.verification_scope === "saved_final_result"
                  ? "最终保存的系统验证通过"
                  : "最终独立系统复验通过"
                : original.stage === "rtl"
                  ? "初始 RTL 快照"
                  : original.text,
      });
    }
  }
  const journey: HistoricalRun = {
    ...first,
    label: "完整修复过程",
    round_no: 0,
    final_validation_id: last.final_validation_id,
    attempts,
    events,
    versions: sources.flatMap((r) => r.versions),
    validations: sources.flatMap((r) => r.validations),
  };
  journeys.set(b, journey);
  return journey;
}
export const historicalRun = (): HistoricalRun | undefined =>
  state.mode === "historical" &&
  state.bundle?.debug_history?.runs.some(
    (r) => r.run_id === state.context.run_id,
  )
    ? historyJourney(state.bundle)
    : undefined;
export const historicalEvents = () =>
  historicalRun()?.events || state.bundle?.events || [];
export const selectedAttempt = () =>
  historicalRun()?.attempts.find(
    (a) => a.validation_id === state.context.validation_id,
  );
export const state = {
  caseId: activeCase(),
  bundle: null as Bundle | null,
  session: null as Session | null,
  health: null as Health | null,
  online: false,
  tab: "verify" as Panel,
  step: "complete",
  comparing: false,
  waveScale: null as { value: number; unit: string } | null,
  context: { case_id: activeCase() } as Context,
  mode: "historical",
  replayIndex: -1,
  replaying: false,
  viewport: null as [bigint, bigint] | null,
  cursor: null as bigint | null,
  liveRun: null as Run | null,
  archivedRuns: [] as Run[],
  story: null as import("./stories").StoryView | null,
  storyError: "",
  view: "workspace" as import("./router").View,
};
export const context = (): Context => ({
  case_id: state.caseId,
  view: "workspace",
  workspace_panel: state.tab,
  story_id: state.context.story_id,
  memory_revision_id: state.context.memory_revision_id,
  memory_use_id: state.context.memory_use_id,
  run_id: state.context.run_id,
  version_id: state.context.version_id,
  validation_id: state.context.validation_id,
  module_id: state.context.module_id,
  signal_id: state.context.signal_id,
  time_range: state.context.validation_id
    ? state.viewport?.map(String)
    : undefined,
});
export const version = () =>
  [
    ...(state.bundle?.versions || []),
    ...state.archivedRuns.flatMap((r) => r.versions),
    ...(state.liveRun?.versions || []),
  ].find((v) => v.version_id === state.context.version_id);
export const validation = () =>
  [
    ...(state.bundle?.validations || []),
    ...state.archivedRuns.flatMap((r) => r.validations),
    ...(state.liveRun?.validations || []),
  ].find((v) => v.validation_id === state.context.validation_id);
export function selectValidation(v: Validation) {
  state.context = {
    case_id: state.caseId,
    run_id: v.run_id,
    version_id: v.version_id,
    validation_id: v.validation_id,
    module_id: [
      ...(state.bundle?.versions || []),
      ...state.archivedRuns.flatMap((r) => r.versions),
      ...(state.liveRun?.versions || []),
    ]
      .find((x) => x.version_id === v.version_id)
      ?.modules.some((m) => m.module_id === state.context.module_id)
      ? state.context.module_id
      : undefined,
  };
  state.mode =
    v.run_id === state.bundle?.source_run_id ||
    state.archivedRuns.some(
      (r) => r.run_id === v.run_id && r.origin === "historical",
    )
      ? "historical"
      : state.liveRun?.origin || "live";
}

export type PackageDescriptor = {
  kind: "single" | "comparison";
  validation_id: string;
  before_validation_id?: string;
  url: string;
  sha256: string;
  size_bytes: number;
};
export type EvidencePackageIndex = {
  schema_version: "rtl-demo-evidence-index-v1";
  single: Record<string, PackageDescriptor>;
  comparisons: PackageDescriptor[];
};
