import {
  state,
  context,
  selectValidation,
  validation,
  version,
  type Context,
  type Module,
  type Operation,
  type Validation,
  type Run,
  type Panel,
  type ReplayEvent,
  historicalRun,
  historyJourney,
  historicalEvents,
  selectedAttempt,
  type HistoricalAttempt,
} from "./state";
import * as api from "./api";
import { el, button, note, modal, errorText } from "./dom";
import { architecture } from "./architecture";
import { code } from "./code";
import { verification } from "./verification";
import { chat } from "./chat";
import {
  parseRoute,
  publicLink,
  panels,
  panelNames,
  normalizePanel,
} from "./router";
import { resolveEvidence } from "./evidence-selection";
import { studioModel, eventStep, stepForPanel } from "./studio-model";
import { timeline } from "./timeline";
import { specification } from "./spec";
import { repair } from "./repair";
import { historyRepair } from "./history-repair";
import { historyDiagnosis } from "./history-diagnosis";
import { agentTrace, type LiveTrace } from "./agent-trace";
const app = document.querySelector<HTMLDivElement>("#app")!;
export async function start() {
  app.replaceChildren(el("div", "loading", "正在载入 RTL 工作台…"));
  const cases = await api.catalog();
  state.bundle = await api.loadBundle();
  const b = state.bundle;
  state.archivedRuns = b.debug_history?.runs || [];
  selectValidation(
    b.validations.find(
      (v) =>
        v.validation_id ===
        (b.debug_history?.runs[0]?.initial_validation_id ||
          b.comparison_pair.after_validation_id),
    )!,
  );
  state.step = historicalRun() ? "verify" : "complete";
  if (state.online) {
    try {
      [state.session, state.health] = await Promise.all([
        api.restoreSession(),
        api.health(),
      ]);
    } catch {
      state.online = false;
    }
  }
  let timer: ReturnType<typeof setTimeout> | undefined,
    closeEvents: (() => void) | undefined,
    epoch = 0,
    routeError = "",
    refreshing = false,
    refreshQueued = false;
  const traces: LiveTrace[] = [];
  const header = el("header", "topbar");
  const brand = el("a", "brand");
  brand.href = "/?case=" + state.caseId + "#/workspace";
  brand.append(
    el("span", "chip-logo", "◉"),
    el("span", "", "Deep Valley Chip"),
    el("span", "brand-divider", "/"),
    el("strong", "", "RTL Studio"),
  );
  const selector = el("select", "case-select mono");
  selector.setAttribute("aria-label", "演示任务");
  for (const c of cases) {
    const o = el("option", "", c.title);
    o.value = c.case_id;
    o.disabled = !c.available;
    selector.append(o);
  }
  selector.value = state.caseId;
  selector.onchange = () =>
    location.assign(
      "/?case=" + encodeURIComponent(selector.value) + "#/workspace",
    );
  const badge = el("span", "status-badge"),
    mode = el("span", "mode-label");
  const headLeft = el("div", "header-left");
  headLeft.append(brand, selector, badge);
  const headRight = el("div", "header-right");
  const play = button("播放回放", toggleReplay, "primary"),
    restart = button("从头回放", () => {
      stop();
      state.replayIndex = -1;
      state.context = {
        case_id: state.caseId,
        run_id: historicalRun()?.run_id || b.source_run_id,
      };
      state.mode = "historical";
      state.liveRun = null;
      state.replaying = true;
      advance();
    });
  const download = button("下载证据包", () => void downloadEvidence());
  const chatDialog = el("dialog", "chat-dialog");
  chatDialog.setAttribute("aria-label", "AI 对话");
  const closeChat = () => chatDialog.close();
  const chatToggle = button(
    "AI 对话",
    () => {
      if (chatDialog.open) {
        closeChat();
        return;
      }
      chatDialog.show();
      chatToggle.setAttribute("aria-expanded", "true");
      c.reveal();
    },
    "chat-launcher",
  );
  chatToggle.setAttribute("aria-expanded", "false");
  chatToggle.setAttribute("aria-haspopup", "dialog");
  chatDialog.onclose = () => {
    chatToggle.setAttribute("aria-expanded", "false");
    chatToggle.focus();
  };
  chatDialog.onkeydown = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      closeChat();
    }
  };
  headRight.append(mode, play, restart, download, chatToggle);
  header.append(headLeft, headRight);
  const progress = el("div", "replay-progress"),
    bar = el("div", "replay-progress-bar");
  progress.append(bar);
  progress.setAttribute("role", "progressbar");
  progress.setAttribute("aria-label", "历史回放位置");
  const main = el("div", "studio-layout");
  const center = el("main", "studio-main");
  const tabs = el("nav", "tabs");
  tabs.setAttribute("role", "tablist");
  tabs.setAttribute("aria-label", "设计证据");
  for (const p of panels) {
    const t = button(panelNames[p], () => {
      stop();
      // A tab is explicit archive browsing; don't carry a previous replay cutoff
      // into an unrelated stage (e.g. showing final verification as unrecorded).
      if (state.mode === "historical") state.replayIndex = -1;
      state.tab = p;
      const r = historicalRun();
      if (r && p === "verify") {
        selectValidation(
          r.validations.find(
            (v) => v.validation_id === r.initial_validation_id,
          )!,
        );
        state.step = "verify";
      } else if (r && p === "repair" && !selectedAttempt()) {
        selectValidation(
          r.validations.find(
            (v) => v.validation_id === r.attempts[0].validation_id,
          )!,
        );
        state.step = "repair";
      }
      state.comparing =
        p === "repair" && !!b.comparison_pair.before_validation_id;
      render();
      remember(true);
    });
    t.setAttribute("role", "tab");
    t.dataset.panel = p;
    tabs.append(t);
  }
  tabs.onkeydown = (e) => {
    if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(e.key)) return;
    e.preventDefault();
    let i = panels.indexOf(state.tab);
    i =
      e.key === "Home"
        ? 0
        : e.key === "End"
          ? panels.length - 1
          : (i + (e.key === "ArrowRight" ? 1 : -1) + panels.length) %
            panels.length;
    (tabs.children[i] as HTMLButtonElement).click();
    (tabs.children[i] as HTMLElement).focus();
  };
  const selectionInfo = el("div", "selection-info"),
    error = el("p", "context-error");
  error.setAttribute("role", "alert");
  const panel = el("section", "studio-panel");
  panel.setAttribute("role", "tabpanel");
  center.append(tabs, selectionInfo, error, panel);
  const right = el("aside", "agent-sidebar");
  right.setAttribute("aria-label", "RTL Agent 信息和对话");
  const metrics = el("div", "sidebar-metrics");
  const trace = agentTrace(navigateStep, choose, inspectAttempt);
  const c = chat(
    (id, ctx) => {
      closeChat();
      void openEvidence(id, ctx);
    },
    (op) => {
      closeChat();
      void openRun(op);
    },
    reconnect,
  );
  const chatHead = el("div", "dialog-head");
  chatHead.append(el("strong", "", "AI 对话"), button("收起对话", closeChat));
  chatDialog.append(chatHead, c.element);
  right.append(metrics, trace.element);
  function navigateStep(id: string, e?: ReplayEvent) {
    stop();
    if (id === "diagnose" && state.mode === "historical" && !historicalRun()) {
      const journey = historyJourney(b);
      const initial = journey?.validations.find(
        (v) => v.validation_id === journey.initial_validation_id,
      );
      if (initial) selectValidation(initial);
    }
    state.step = id;
    const d = studioModel(
      b,
      state.mode === "live" ? state.liveRun : historicalRun(),
    ).steps.find((s) => s.id === id)!;
    state.tab = d.panel;
    if (e) {
      if (state.mode === "historical") state.replayIndex = -1;
      if (state.mode === "historical") applyEvent(e);
      else {
        const v = state.liveRun?.validations.find(
          (v) => v.validation_id === e.validation_id,
        );
        if (v) selectValidation(v);
      }
    } else if (d.validation_id) {
      const v = allValidations().find(
        (v) => v.validation_id === d.validation_id,
      );
      if (v) selectValidation(v);
      if (state.mode === "historical") state.replayIndex = -1;
    }
    state.comparing =
      d.panel === "repair" && !!b.comparison_pair.before_validation_id;
    render();
    remember(true);
  }
  const tl = timeline(navigateStep);
  const timelineToggle = button(
    "运行步骤",
    () => {
      tl.element.classList.toggle("mobile-open");
      timelineToggle.setAttribute(
        "aria-expanded",
        String(tl.element.classList.contains("mobile-open")),
      );
    },
    "timeline-toggle",
  );
  timelineToggle.setAttribute("aria-expanded", "false");
  center.prepend(timelineToggle);
  main.append(tl.element, center, right);
  app.replaceChildren(header, progress, main, chatDialog);
  function allRuns() {
    return [...state.archivedRuns, ...(state.liveRun ? [state.liveRun] : [])];
  }
  function allValidations() {
    return [...b.validations, ...allRuns().flatMap((r) => r.validations)];
  }
  function stop() {
    if (timer) clearTimeout(timer);
    state.replaying = false;
  }
  function applyEvent(e: (typeof b.events)[number]) {
    const run = historicalRun();
    state.step = eventStep(e);
    const d = studioModel(b, run).steps.find((d) => d.id === state.step);
    if (d) state.tab = d.panel;
    if (e.validation_id) {
      const v = allValidations().find(
        (x) => x.validation_id === e.validation_id,
      );
      if (v) selectValidation(v);
    } else if (e.version_id)
      state.context = {
        case_id: state.caseId,
        run_id: run?.run_id || b.source_run_id,
        version_id: e.version_id,
      };
    else if (e.trial_no)
      state.context = {
        case_id: state.caseId,
        run_id: run?.run_id || b.source_run_id,
      };
  }
  function advance() {
    if (!state.replaying) return;
    state.replayIndex++;
    const e = historicalEvents()[state.replayIndex];
    if (!e) {
      state.replayIndex = historicalEvents().length - 1;
      stop();
      render();
      return;
    }
    applyEvent(e);
    render();
    remember(false);
    timer = setTimeout(advance, e.replay_delay_ms || 1500);
  }
  function toggleReplay() {
    if (state.replaying) {
      stop();
      render();
      return;
    }
    if (state.mode !== "historical") {
      state.mode = "historical";
      state.liveRun = null;
      state.replayIndex = -1;
    }
    if (state.replayIndex >= historicalEvents().length - 1) {
      state.replayIndex = -1;
      state.context = {
        case_id: state.caseId,
        run_id: historicalRun()?.run_id || b.source_run_id,
      };
    }
    state.replaying = true;
    advance();
  }
  function remember(push = false) {
    if (routeError) return;
    const ctx = context();
    const isPublic =
      !ctx.run_id ||
      ctx.run_id === b.source_run_id ||
      state.archivedRuns.some(
        (r) => r.run_id === ctx.run_id && r.origin === "historical",
      );
    const u = new URL(
      publicLink(
        isPublic ? ctx : { case_id: state.caseId },
        "workspace",
        state.tab,
      ),
      location.origin,
    );
    u.searchParams.set("step", state.step);
    const comparisonBefore =
      selectedAttempt()?.before_validation_id ||
      b.comparison_pair.before_validation_id;
    if (isPublic && state.comparing && comparisonBefore)
      u.searchParams.set("before_validation_id", comparisonBefore);
    const hist = { context: ctx, panel: state.tab, mode: state.mode };
    if (push) history.pushState(hist, "", u);
    else history.replaceState(hist, "", u);
    if (state.online && state.session)
      void api.saveSelection(ctx).catch(() => {});
    c.render();
  }
  async function route(initial = false) {
    const token = ++epoch;
    stop();
    const u = new URL(location.href),
      r = parseRoute(u);
    state.view = "workspace";
    routeError = "";
    try {
      let ctx: Context = r.explicitEvidence
        ? { case_id: state.caseId, ...r.context }
        : !initial && history.state?.context
          ? history.state.context
          : initial &&
              (state.session?.selection?.version_id ||
                state.session?.selection?.run_id)
            ? state.session!.selection
            : context();
      ctx = {
        ...ctx,
        case_id: state.caseId,
        view: "workspace",
        story_id: undefined,
        memory_revision_id: undefined,
        memory_use_id: undefined,
      };
      if (r.explicitEvidence && !Object.keys(r.context).length)
        throw new Error("无效的证据链接。");
      if (
        ctx.validation_id &&
        !allValidations().some((v) => v.validation_id === ctx.validation_id) &&
        state.online
      ) {
        const v = await api.request<Validation>(
          "/validations/" + encodeURIComponent(ctx.validation_id),
        );
        const run = await api.run(v.run_id);
        if (token !== epoch) return;
        if (run.case_id !== state.caseId) throw new Error("证据属于其他案例。");
        state.archivedRuns.push(run);
      }
      if (
        ctx.run_id &&
        ctx.run_id !== b.source_run_id &&
        !allRuns().some((x) => x.run_id === ctx.run_id) &&
        state.online
      ) {
        const run = await api.run(ctx.run_id);
        if (token !== epoch) return;
        if (run.case_id !== state.caseId) throw new Error("运行属于其他案例。");
        state.archivedRuns.push(run);
      }
      if (ctx.run_id && !ctx.validation_id && !ctx.version_id) {
        const r = b.debug_history?.runs.find((r) => r.run_id === ctx.run_id);
        if (r) ctx.validation_id = r.initial_validation_id;
        else if (ctx.run_id === b.source_run_id)
          ctx.validation_id = b.comparison_pair.after_validation_id;
      }
      state.context = resolveEvidence(b, ctx, allRuns());
      state.mode =
        state.context.run_id && state.context.run_id !== b.source_run_id
          ? allRuns().find((x) => x.run_id === state.context.run_id)?.origin ||
            "live"
          : "historical";
      if (state.mode === "live")
        state.liveRun =
          allRuns().find((x) => x.run_id === state.context.run_id) || null;
      state.tab =
        r.panel ||
        normalizePanel(
          !initial
            ? history.state?.panel
            : state.session?.selection?.workspace_panel,
        ) ||
        "verify";
      state.step =
        r.step ||
        (validation()?.kind === "final_system" ? "complete" : "verify");
      state.comparing = !!r.before;
      if (
        r.before &&
        r.before !==
          (selectedAttempt()?.before_validation_id ||
            b.comparison_pair.before_validation_id)
      )
        throw new Error("前后比较记录不匹配。");
      if (r.legacy) {
        u.hash = "/workspace";
        for (const k of ["story_id", "memory_revision_id", "memory_use_id"])
          u.searchParams.delete(k);
        history.replaceState(null, "", u);
      }
    } catch (e) {
      routeError = errorText(e);
      state.context = { case_id: state.caseId };
    }
    if (token !== epoch) return;
    render();
    if (!routeError) remember(false);
  }
  function choose(v: Validation) {
    stop();
    state.context = resolveEvidence(
      b,
      { case_id: state.caseId, validation_id: v.validation_id },
      allRuns(),
    );
    selectValidation(v);
    state.tab = "verify";
    state.step = v.kind === "final_system" ? "complete" : "verify";
    state.replayIndex = -1;
    render();
    remember(true);
  }
  function inspectAttempt(a: HistoricalAttempt) {
    const r = historicalRun();
    const v = r?.validations.find((v) => v.validation_id === a.validation_id);
    if (!v) return;
    stop();
    const phase =
      state.step === "diagnose"
        ? "diagnose"
        : state.step === "syntax"
          ? "syntax"
          : "repair";
    selectValidation(v);
    state.step = phase;
    state.tab = phase === "syntax" ? "code" : "repair";
    state.replayIndex = -1;
    state.comparing = true;
    state.viewport = null;
    state.cursor = null;
    render();
    remember(true);
  }
  function openModule(m: Module) {
    if (!version()) {
      const v = b.validations.find(
        (x) => x.validation_id === b.comparison_pair.after_validation_id,
      )!;
      selectValidation(v);
    }
    state.context.module_id = m.module_id;
    state.tab = "code";
    state.step = "rtl";
    render();
    remember(true);
  }
  async function openEvidence(id: string, ctx: Context = context()) {
    if (ctx.case_id !== state.caseId) {
      location.assign(
        publicLink(ctx, "workspace", ctx.workspace_panel || "verify"),
      );
      return;
    }
    try {
      const module = [...b.versions, ...allRuns().flatMap((r) => r.versions)]
        .flatMap((v) => v.modules.map((m) => ({ v, m })))
        .find(
          (x) =>
            x.m.artifact_id === id &&
            (!ctx.version_id || x.v.version_id === ctx.version_id),
        );
      if (module) {
        state.context = resolveEvidence(
          b,
          {
            case_id: state.caseId,
            version_id: module.v.version_id,
            module_id: module.m.module_id,
          },
          allRuns(),
        );
        state.tab = "code";
        render();
        remember(true);
        return;
      }
      modal(
        id === b.spec_artifact_id ? b.title + " · 系统规格" : "设计依据",
        await api.content(id),
      );
    } catch (e) {
      modal("证据不可用", errorText(e));
    }
  }
  async function openRun(op: Operation) {
    try {
      const r = await api.run(op.run_id);
      if (r.case_id && r.case_id !== state.caseId)
        throw new Error("运行属于其他案例。");
      state.liveRun = r;
      state.mode = r.origin || "live";
      state.context = { case_id: state.caseId, run_id: r.run_id };
      const v =
        [...r.validations].reverse().find((v) => v.kind === "final_system") ||
        r.validations.at(-1);
      if (v) selectValidation(v);
      state.tab = v ? "verify" : "architecture";
      state.replayIndex = -1;
      render();
      remember(true);
    } catch (e) {
      modal("运行不可用", errorText(e));
    }
  }
  async function refresh() {
    if (refreshing) {
      refreshQueued = true;
      return;
    }
    if (!state.session) return;
    refreshing = true;
    const sid = state.session.session_id,
      cid = state.caseId;
    try {
      const s = await api.refreshSession();
      if (s.session_id !== sid || state.caseId !== cid) return;
      state.session = s;
      if (state.mode === "live" && state.context.run_id) {
        state.liveRun = await api.run(state.context.run_id);
        if (!state.context.validation_id && state.liveRun.validations.length) {
          selectValidation(state.liveRun.validations.at(-1)!);
          state.tab = "verify";
        }
        render();
      } else {
        c.render();
        renderActivity();
        renderHeader();
      }
    } catch {
      c.setConnection(false);
    } finally {
      refreshing = false;
      if (refreshQueued) {
        refreshQueued = false;
        void refresh();
      }
    }
  }
  function watch() {
    closeEvents?.();
    if (!state.session) return;
    closeEvents = api.subscribe(
      () => void refresh(),
      (up) => c.setConnection(up),
      (event) => {
        const p = event.payload;
        if (
          state.mode === "live" &&
          p.run_id === state.context.run_id &&
          typeof p.stage === "string"
        )
          state.step = p.stage;
        const text = [
          p.stage,
          p.module_id,
          p.state,
          p.verdict,
          p.attempt?.trial_no != null
            ? "候选 " + p.attempt.trial_no
            : undefined,
        ]
          .filter((x) => typeof x === "string" || typeof x === "number")
          .join(" · ");
        if (!traces.some((t) => t.id === event.id)) {
          traces.unshift({
            id: event.id,
            runId: typeof p.run_id === "string" ? p.run_id : undefined,
            stage: typeof p.stage === "string" ? p.stage : undefined,
            validationId:
              typeof p.validation_id === "string" ? p.validation_id : undefined,
            trialNo:
              typeof p.attempt?.trial_no === "number"
                ? p.attempt.trial_no
                : undefined,
            tag: "实时 · " + event.type,
            text: text || "状态已更新",
          });
          traces.splice(100);
        }
        renderActivity();
      },
    );
  }
  async function reconnect() {
    [state.session, state.health] = await Promise.all([
      api.restoreSession(),
      api.health(),
    ]);
    state.online = true;
    watch();
    renderHeader();
    c.render();
  }
  function renderActivity() {
    right.classList.toggle("debug-focused", state.tab === "repair");
    trace.render(traces);
  }
  function renderHeader() {
    const diagnosing =
      state.step === "diagnose" ? selectedAttempt() : undefined;
    const v = diagnosing
      ? historicalRun()?.validations.find(
          (v) => v.validation_id === diagnosing.before_validation_id,
        )
      : validation();
    mode.textContent =
      state.mode === "historical"
        ? "历史运行回放 · 真实归档"
        : "实时执行 · 隔离运行";
    badge.textContent = v
      ? (diagnosing ? "修复前" : "所选") +
        (state.mode === "historical" ? "历史" : "实时") +
        "记录 · " +
        v.verdict.toUpperCase()
      : "所选阶段 · 无详细验证";
    badge.className = "status-badge " + (v?.verdict || "");
    play.textContent = state.replaying
      ? "暂停回放"
      : state.replayIndex >= 0
        ? "继续回放"
        : "播放回放";
    const n = Math.max(0, state.replayIndex + 1);
    const count = historicalEvents().length;
    bar.style.width = (100 * n) / Math.max(1, count) + "%";
    progress.setAttribute("aria-valuenow", String(n));
    progress.setAttribute("aria-valuemax", String(count));
    progress.title = "回放位置 " + n + " / " + count + "，不代表现场执行进度";
    const active = state.session?.operations.find(
      (o) =>
        o.run_id === state.context.run_id &&
        ["accepted", "running"].includes(o.state),
    );
    if (state.mode === "live" && active)
      badge.textContent = "实时执行中 · " + (active.stage || "已接收");
    download.disabled =
      !v || !b.validations.some((x) => x.validation_id === v.validation_id);
    download.title = download.disabled
      ? "先选择可公开的历史验证记录"
      : diagnosing
        ? "下载当前根因判断关联的修改前验证证据包"
        : "下载当前" + (state.comparing ? "前后比较" : "验证") + "的公开证据包";
  }
  async function downloadEvidence() {
    try {
      const { downloadEvidence } = await import("./evidence-download");
      download.disabled = true;
      download.textContent = "准备下载…";
      await downloadEvidence();
    } catch (e) {
      modal("证据下载", errorText(e));
    } finally {
      download.textContent = "下载证据包";
      renderHeader();
    }
  }
  function render() {
    state.step = stepForPanel(state.tab, state.step, validation()?.kind);
    if (historicalRun())
      state.comparing =
        !!selectedAttempt() && ["repair", "syntax"].includes(state.step);
    renderHeader();
    tl.render();
    renderActivity();
    error.hidden = !routeError;
    error.textContent = routeError;
    for (const t of tabs.children) {
      const yes = (t as HTMLElement).dataset.panel === state.tab;
      t.classList.toggle("active", yes);
      t.setAttribute("aria-selected", String(yes));
      (t as HTMLElement).tabIndex = yes ? 0 : -1;
    }
    selectionInfo.textContent =
      state.bundle!.title +
      " · " +
      ((state.step === "diagnose"
        ? selectedAttempt()?.baseline_version_id
        : undefined) ||
        state.context.version_id ||
        "未选择受测版本") +
      (state.replayIndex >= 0 ? " · 回放记录 " + (state.replayIndex + 1) : "");
    const m = studioModel(
      b,
      state.mode === "live"
        ? state.liveRun || {
            run_id: state.context.run_id || "",
            versions: [],
            validations: [],
            modules: [],
          }
        : historicalRun(),
    );
    metrics.replaceChildren();
    for (const [name, value] of [
      ["规划模块", m.moduleCount],
      [
        historicalRun()?.attempts.some((a) => a.lint_pass === null)
          ? "代码修改"
          : "候选验证",
        m.trialCount ?? "—",
      ],
      [
        historicalRun() ? "最终复验" : "案例最终复验",
        m.final?.verdict.toUpperCase() || "未记录",
      ],
    ]) {
      const n = el("div", "metric");
      n.append(
        el("small", "", String(name)),
        el("strong", "mono", String(value)),
      );
      metrics.append(n);
    }
    panel.replaceChildren(
      routeError
        ? note("请检查证据链接；未替换为其他通过记录。")
        : state.step === "diagnose"
          ? historyDiagnosis(
              inspectAttempt,
              (a) => {
                state.step = "repair";
                inspectAttempt(a);
              },
              choose,
              () => remember(false),
            )
          : historicalRun() &&
              ["diagnose", "repair", "syntax"].includes(state.step)
            ? historyRepair(choose, () => remember(false))
            : state.tab === "spec"
              ? specification()
              : state.tab === "architecture"
                ? architecture(
                    openModule,
                    () => void openEvidence(b.spec_artifact_id),
                  )
                : state.tab === "code"
                  ? code(() => remember(false))
                  : state.tab === "repair"
                    ? repair(choose)
                    : verification(choose, () => remember(false)),
    );
    c.render();
  }
  window.addEventListener("popstate", () => void route());
  window.addEventListener("hashchange", () => void route());
  window.addEventListener("pagehide", () => {
    stop();
    closeEvents?.();
  });
  await route(true);
  if (state.online && state.session) watch();
}
