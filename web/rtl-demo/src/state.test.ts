import { test, expect } from "vitest";
import { context, state, type Context } from "./state";

test("恢复会话后，发送上下文不包含浏览状态或其他响应字段", () => {
  const previous = state.context;
  try {
    state.context = {
      case_id: "e203",
      run_id: "run-1",
      version_id: "version-1",
      validation_id: "validation-1",
      module_id: "alu",
      browsing_mode: "historical",
      request_id: "response-only",
    } as Context;
    const payload = JSON.parse(JSON.stringify(context()));
    expect(payload).toEqual({
      case_id: "e203",
      view: "workspace",
      workspace_panel: state.tab,
      run_id: "run-1",
      version_id: "version-1",
      validation_id: "validation-1",
      module_id: "alu",
    });
  } finally {
    state.context = previous;
  }
});

test("only whitelisted experience context is sent", () => {
  const previous = state.context;
  state.context = {
    case_id: "e203",
    story_id: "story-fixed",
    memory_revision_id: "revision-fixed",
    memory_use_id: "use-fixed",
  };
  const payload = context();
  expect(payload.memory_revision_id).toBe("revision-fixed");
  expect(payload.version_id).toBeUndefined();
  state.context = previous;
});

test("memory-only context does not inherit an unrelated waveform window", () => {
  const prior = state.context,
    viewport = state.viewport;
  state.context = {
    case_id: "e203",
    story_id: "story-fixed",
    memory_revision_id: "revision-fixed",
  };
  state.viewport = [10n, 20n];
  expect(context().time_range).toBeUndefined();
  state.context = prior;
  state.viewport = viewport;
});

test("additional historical run keeps historical origin", async () => {
  const { selectValidation } = await import("./state");
  const previous = {
    context: state.context,
    mode: state.mode,
    archived: state.archivedRuns,
  };
  try {
    state.archivedRuns = [
      {
        run_id: "extra-history",
        origin: "historical",
        versions: [],
        validations: [],
      },
    ];
    selectValidation({
      run_id: "extra-history",
      version_id: "fixed-version",
      validation_id: "fixed-validation",
    } as import("./state").Validation);
    expect(state.mode).toBe("historical");
    expect(state.context.run_id).toBe("extra-history");
  } finally {
    state.context = previous.context;
    state.mode = previous.mode;
    state.archivedRuns = previous.archived;
  }
});
