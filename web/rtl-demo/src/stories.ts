import type { Run, Validation } from "./state";
export type Evidence = { kind: string; id: string; sha256?: string | null };
export type MemoryRevision = {
  memory_id: string;
  revision_id: string;
  content_sha256: string;
  parent_revision_id?: string | null;
  title: string;
  lesson: string;
  applicability: string[];
  limitations: string[];
  source_run_id: string;
  source_version_id?: string | null;
  backend: string;
  state: string;
  validation_level: string;
  evidence_refs: Evidence[];
};
export type UseEvent = {
  event_id: string;
  kind: string;
  event_artifact_id: string;
  candidate_version_id?: string | null;
  validation_id?: string | null;
  reason: string;
};
export type MemoryUse = {
  use_id: string;
  revision_id: string;
  run_id: string;
  backend: string;
  snapshot_sha256: string;
  events: UseEvent[];
};
export type LifecycleEvent = {
  event_id: string;
  revision_id: string;
  kind: string;
  replacement_revision_id?: string | null;
  reason: string;
  evidence_refs: Evidence[];
};
export type StoryView = {
  schema_version: "rtl-demo-story-view-v1";
  case_id: string;
  origin: "historical";
  story_id: string | null;
  fingerprint: string | null;
  optimization: {
    state: "awaiting_data";
    message: string;
    missing_evidence: string[];
  };
  experience: {
    state: string;
    missing_evidence: string[];
    memories: MemoryRevision[];
    uses: MemoryUse[];
    lifecycle_events: LifecycleEvent[];
    comparisons: {
      comparison_id: string;
      state: string;
      message: string;
      limitations: string[];
    }[];
  };
  runs?: Run[];
  content_urls?: Record<string, string>;
  waveform_urls?: Record<string, string>;
};
export const stageLabels: Record<string, string> = {
  retrieved: "已检索",
  provided: "已提供给执行者",
  application_declared: "采用声明",
  applied: "已实际采用",
  validation_observed: "已记录后续验证",
};
export const readinessLabels: Record<string, string> = {
  empty: "材料待准备",
  archived_only: "已沉淀 · 复用待验证",
  partial: "证据链尚未完整",
  complete: "经验链可追溯 · 收益待验证",
  incomplete_evidence: "证据不完整",
};
export function applicationFacts(events: UseEvent[]) {
  const kinds = new Set(events.map((e) => e.kind));
  return {
    retrieved: kinds.has("retrieved"),
    provided: kinds.has("provided"),
    declared: kinds.has("application_declared"),
    adopted: kinds.has("applied"),
    observed: kinds.has("validation_observed"),
  };
}
export function resultForUse(
  use: MemoryUse,
  event: UseEvent,
  runs: Run[],
): Validation["verdict"] {
  if (event.kind !== "validation_observed" || !event.validation_id)
    return "unverified";
  const run = runs.find((r) => r.run_id === use.run_id);
  const val = run?.validations.find(
    (v) => v.validation_id === event.validation_id,
  );
  if (
    !val ||
    val.run_id !== use.run_id ||
    (event.candidate_version_id &&
      val.version_id !== event.candidate_version_id)
  )
    return "unverified";
  if (val.verdict === "pass" && !val.simulation_completed) return "unverified";
  return val.verdict;
}
