import type { StoryView } from "../../src/stories";
export const emptyStory = (case_id = "e203"): StoryView => ({
  schema_version: "rtl-demo-story-view-v1",
  case_id,
  origin: "historical",
  story_id: null,
  fingerprint: null,
  optimization: {
    state: "awaiting_data",
    message: "PPA 数据待接入",
    missing_evidence: ["同条件版本测量"],
  },
  experience: {
    state: "empty",
    missing_evidence: ["审核后的经验材料"],
    memories: [],
    uses: [],
    lifecycle_events: [],
    comparisons: [],
  },
});

// Entirely synthetic DTOs for rendering tests. Never exported with public cases.
export function storyScenario(
  kind:
    | "archived"
    | "pass"
    | "fail"
    | "revision"
    | "missing_reference"
    | "cross_case" = "archived",
): StoryView {
  const story = emptyStory(
    kind === "cross_case" ? "sdc_controller_system" : "e203",
  );
  story.story_id = "story-synthetic-ui";
  story.fingerprint = "0".repeat(64);
  story.experience.state = "archived_only";
  const memory = {
    memory_id: "synthetic-memory",
    revision_id: "synthetic-v1",
    content_sha256: "1".repeat(64),
    title: "Synthetic rule",
    lesson: "Test only",
    applicability: ["Fixture"],
    limitations: ["No real execution"],
    source_run_id: "synthetic-a",
    backend: "synthetic",
    state: "approved_active",
    validation_level: "unverified",
    evidence_refs: [],
  };
  story.experience.memories = [memory];
  if (kind === "pass" || kind === "fail" || kind === "missing_reference") {
    story.experience.state = "partial";
    story.experience.uses = [
      {
        use_id: "synthetic-use",
        revision_id: memory.revision_id,
        run_id: "synthetic-b",
        backend: "synthetic",
        snapshot_sha256: "2".repeat(64),
        events: ["provided", "applied", "validation_observed"].map(
          (stage, i) => ({
            event_id: "synthetic-" + i,
            kind: stage,
            event_artifact_id: "synthetic-proof-" + i,
            reason: "Test only",
            ...(stage === "validation_observed"
              ? { validation_id: "synthetic-validation" }
              : {}),
          }),
        ),
      },
    ];
    story.runs = [
      {
        run_id: "synthetic-b",
        origin: "historical",
        versions: [],
        validations:
          kind === "missing_reference"
            ? []
            : [
                {
                  validation_id: "synthetic-validation",
                  run_id: "synthetic-b",
                  version_id: "synthetic-candidate",
                  verdict: kind,
                  simulation_completed: true,
                } as import("../../src/state").Validation,
              ],
      },
    ];
  }
  if (kind === "revision") {
    story.experience.memories.push({
      ...memory,
      revision_id: "synthetic-v2",
      parent_revision_id: "synthetic-v1",
      content_sha256: "3".repeat(64),
      lesson: "New synthetic boundary",
    });
    story.experience.lifecycle_events = [
      {
        event_id: "synthetic-change",
        revision_id: "synthetic-v1",
        kind: "superseded",
        replacement_revision_id: "synthetic-v2",
        reason: "Test boundary",
        evidence_refs: [],
      },
    ];
  }
  return story;
}
