import {
  state,
  type Bundle,
  type Wave,
  type Session,
  type Context,
  type Operation,
  type Health,
  type Run,
  type CaseEntry,
} from "./state";
import type { StoryView } from "./stories";
export class APIError extends Error {
  constructor(
    public code: string,
    message: string,
    public status?: number,
    public retryAfter?: number,
  ) {
    super(message);
  }
}
export const key = () => crypto.randomUUID();
export async function request<T>(
  path: string,
  body?: unknown,
  method = body ? "POST" : "GET",
  idempotency?: string,
  timeoutMs = 12000,
  requestCase = state.caseId,
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch("/api" + path, {
      method,
      credentials: "same-origin",
      signal: controller.signal,
      headers: body
        ? {
            "X-Demo-Case": requestCase,
            "Content-Type": "application/json",
            "X-Demo-Request": "1",
            "Idempotency-Key": idempotency || key(),
          }
        : { "X-Demo-Case": requestCase },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.headers.get("Content-Type")?.includes("application/json"))
      throw new APIError(
        "invalid_api_response",
        "后台未返回有效接口数据，请检查服务连接。",
        res.status,
      );
    const data = await res.json();
    if (!res.ok)
      throw new APIError(
        data.error?.code || "request_failed",
        data.error?.message || "服务暂不可用",
        res.status,
        Number(res.headers.get("Retry-After")) || undefined,
      );
    return data as T;
  } catch (e) {
    if (e instanceof APIError) throw e;
    throw new APIError(
      "connection_lost",
      "无法连接执行后台，历史案例仍可浏览。",
    );
  } finally {
    clearTimeout(timeout);
  }
}
async function staticJSON<T>(url: string | undefined): Promise<T> {
  if (!url) throw new Error("此记录没有静态副本");
  const res = await fetch(url);
  if (!res.ok) throw new Error("历史产物加载失败");
  return await res.json();
}
export async function loadBundle() {
  const [live, saved] = await Promise.allSettled([
    request<Bundle>(
      "/cases/" + state.caseId,
      undefined,
      "GET",
      undefined,
      1800,
    ),
    staticJSON<Bundle>("/cases/" + state.caseId + "/manifest.json"),
  ]);
  if (live.status === "fulfilled") {
    state.online = true;
    const b = live.value;
    if (
      saved.status === "fulfilled" &&
      saved.value.bundle_id === b.bundle_id &&
      saved.value.source_fingerprint === b.source_fingerprint &&
      saved.value.debug_history?.history_fingerprint === b.debug_history?.history_fingerprint
    )
      return {
        ...b,
        content_urls: saved.value.content_urls,
        waveform_urls: saved.value.waveform_urls,
        evidence_packages: saved.value.evidence_packages,
        debug_trace: saved.value.debug_trace,
        debug_history: saved.value.debug_history,
        versions: saved.value.versions,
        validations: saved.value.validations,
      };
    return b;
  }
  if (saved.status === "fulfilled") return saved.value;
  throw new Error("案例数据未准备，请先运行 prepare-cases。");
}

export async function content(id: string): Promise<string> {
  if (state.bundle?.content_urls?.[id]) {
    try {
      return (
        await staticJSON<{ content: string }>(state.bundle.content_urls[id])
      ).content;
    } catch {
      /* The API remains available if a static file is missing. */
    }
  }
  if (state.online) {
    try {
      return (
        await request<{ content: string }>(
          "/artifacts/" + encodeURIComponent(id) + "/content",
        )
      ).content;
    } catch (e) {
      if (!state.bundle?.content_urls?.[id]) throw e;
    }
  }
  return (
    await staticJSON<{ content: string }>(state.bundle?.content_urls?.[id])
  ).content;
}
type TileIndex = {
  tiled: true;
  full_end_ticks: string;
  tiles: { start_ticks: string; end_ticks: string; url: string }[];
};
const waveCache = new Map<string, Promise<Wave>>();
async function staticWave(
  url: string,
  range?: [bigint, bigint],
): Promise<Wave> {
  const data = await staticJSON<Wave | TileIndex>(url);
  if (!("tiled" in data)) return data;
  const a = range?.[0] ?? BigInt(data.tiles[0].start_ticks),
    b = range?.[1] ?? BigInt(data.tiles[0].end_ticks);
  const tiles = data.tiles.filter(
    (t) => BigInt(t.end_ticks) > a && BigInt(t.start_ticks) < b,
  );
  if (!tiles.length) throw new Error("窗口超出本次仿真的时间范围。");
  const parts = await Promise.all(
    tiles.map((t) => {
      if (!waveCache.has(t.url)) waveCache.set(t.url, staticJSON<Wave>(t.url));
      return waveCache.get(t.url)!;
    }),
  );
  const signals = parts[0].signals.map((s, index) => {
    const transitions: [string, string][] = [];
    let value = s.initial_value;
    for (const [pi, p] of parts.entries()) {
      const current = p.signals[index];
      if (pi && current.initial_value !== value)
        transitions.push([p.start_ticks, current.initial_value]);
      transitions.push(...current.changes);
      value = current.changes.at(-1)?.[1] ?? current.initial_value;
    }
    let initial = s.initial_value;
    for (const [t, v] of transitions) {
      if (BigInt(t) > a) break;
      initial = v;
    }
    return {
      ...s,
      initial_value: initial,
      changes: transitions.filter(([t]) => BigInt(t) > a && BigInt(t) < b),
    };
  });
  if (signals.reduce((n, s) => n + s.changes.length, 0) > 20000)
    throw new Error("变化数量过多，请缩小波形窗口。");
  return {
    ...parts[0],
    start_ticks: String(a),
    end_ticks: String(b),
    full_end_ticks: data.full_end_ticks,
    signals,
    sample_markers: parts
      .flatMap((p) => p.sample_markers)
      .filter((m) => BigInt(m.time_ticks) >= a && BigInt(m.time_ticks) < b),
  };
}
export async function wave(
  id: string,
  range?: [bigint, bigint],
): Promise<Wave> {
  const url = state.bundle?.waveform_urls?.[id];
  if (url) {
    try {
      return await staticWave(url, range);
    } catch (e) {
      if (
        !state.online ||
        (e instanceof Error && e.message.includes("变化数量"))
      )
        throw e;
    }
  }
  const query = range
    ? "?start_ticks=" + range[0] + "&end_ticks=" + range[1]
    : "";
  return request<Wave>(
    "/validations/" + encodeURIComponent(id) + "/waveform" + query,
  );
}
export async function restoreSession() {
  const sessionKey =
    state.caseId === "e203"
      ? "rtl-demo-session"
      : "rtl-demo-session:" + state.caseId;
  const prior = localStorage.getItem(sessionKey);
  if (prior) {
    try {
      return await request<Session>("/sessions/" + prior);
    } catch (error) {
      if (
        !(error instanceof APIError) ||
        !["session_required", "session_forbidden", "not_found"].includes(
          error.code,
        )
      )
        throw error;
      localStorage.removeItem(sessionKey);
    }
  }
  const s = await request<Session>("/sessions", { case_id: state.caseId });
  localStorage.setItem(sessionKey, s.session_id);
  return s;
}
export const refreshSession = (
  id = state.session!.session_id,
  cid = state.caseId,
) =>
  request<Session>("/sessions/" + id, undefined, "GET", undefined, 12000, cid);
export const health = () => request<Health>("/health?case_id=" + state.caseId);
export const saveSelection = (ctx: Context) =>
  state.session
    ? request(
        "/sessions/" + state.session.session_id + "/selection",
        {
          ...ctx,
          browsing_mode: state.mode,
          workspace_panel: ctx.workspace_panel || state.tab,
        },
        "PATCH",
      )
    : Promise.resolve();
export const send = (text: string, ctx: Context, id: string) =>
  request(
    "/sessions/" + state.session!.session_id + "/messages",
    { text, context_ref: ctx, client_message_id: id },
    "POST",
    id,
    12000,
    ctx.case_id,
  );
export const operate = (kind: string, ctx: Context, id = key()) =>
  request<Operation>(
    "/sessions/" + state.session!.session_id + "/operations",
    { kind, context_ref: ctx },
    "POST",
    id,
  );
export const run = (id: string) =>
  request<Run>("/runs/" + encodeURIComponent(id));
export async function loadStories(ident?: string): Promise<StoryView> {
  const base = "/cases/" + state.caseId + "/stories/manifest.json";
  const [live, saved] = await Promise.allSettled([
    request<StoryView>(
      ident
        ? "/stories/" + encodeURIComponent(ident)
        : "/cases/" + state.caseId + "/stories",
    ),
    staticJSON<StoryView>(base),
  ]);
  if (live.status === "fulfilled") {
    if (
      saved.status === "fulfilled" &&
      saved.value.story_id === live.value.story_id &&
      saved.value.fingerprint === live.value.fingerprint
    )
      return {
        ...live.value,
        content_urls: saved.value.content_urls,
        waveform_urls: saved.value.waveform_urls,
      };
    return live.value;
  }
  if (
    live.status === "rejected" &&
    live.reason instanceof APIError &&
    live.reason.status &&
    live.reason.code !== "invalid_api_response"
  ) {
    if (ident || live.reason.status !== 404) throw live.reason;
  }
  if (
    saved.status === "fulfilled" &&
    (!ident || saved.value.story_id === ident)
  )
    return saved.value;
  if (ident)
    throw new APIError(
      "story_evidence_invalid",
      "所选故事不可用，未借用其他记录。",
    );
  return {
    schema_version: "rtl-demo-story-view-v1",
    case_id: state.caseId,
    story_id: null,
    fingerprint: null,
    origin: "historical",
    optimization: {
      state: "awaiting_data",
      message: "PPA 数据待接入",
      missing_evidence: ["同条件版本测量", "测量报告与功能验证绑定"],
    },
    experience: {
      state: "empty",
      missing_evidence: ["审核后的经验材料"],
      memories: [],
      uses: [],
      lifecycle_events: [],
      comparisons: [],
    },
  };
}
export function subscribe(
  onUpdate: () => void,
  onStatus: (up: boolean) => void,
  onEvent?: (event: { id: string; type: string; payload: any }) => void,
) {
  const s = state.session!;
  let last = Number(sessionStorage.getItem("rtl-events-" + s.session_id) || 0);
  const es = new EventSource(
    "/api/sessions/" +
      s.session_id +
      "/events?case_id=" +
      state.caseId +
      "&after=" +
      last,
  );
  es.onopen = () => onStatus(true);
  es.onerror = () => onStatus(false);
  const handle = (event: MessageEvent) => {
    const n = Number(event.lastEventId);
    if (n <= last) return;
    last = n;
    sessionStorage.setItem("rtl-events-" + s.session_id, String(n));
    try {
      const data = JSON.parse(event.data);
      onEvent?.({
        id: String(n),
        type: event.type,
        payload: data.payload || {},
      });
    } catch {
      /* malformed event is never displayed */
    }
    onUpdate();
  };
  [
    "message.updated",
    "message.received",
    "operation.accepted",
    "operation.updated",
    "stage.updated",
    "module.updated",
    "artifact.available",
    "attempt.updated",
    "validation.completed",
    "operation.completed",
    "selection.updated",
  ].forEach((t) => es.addEventListener(t, handle as EventListener));
  return () => es.close();
}

export async function catalog(): Promise<CaseEntry[]> {
  try {
    return (await staticJSON<{ cases: CaseEntry[] }>("/cases/index.json"))
      .cases;
  } catch {
    try {
      return (await request<{ cases: CaseEntry[] }>("/cases")).cases;
    } catch {
      return [
        {
          case_id: "e203",
          title: "E203 执行单元",
          subtitle: "E203 · RISC-V EXECUTION UNIT",
          available: true,
        },
      ];
    }
  }
}
