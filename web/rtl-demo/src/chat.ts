import {
  state,
  context,
  selectedAttempt,
  type Operation,
  type Context,
} from "./state";
import { send, key, refreshSession } from "./api";
import { el, button, note, errorText } from "./dom";
export function chat(
  openEvidence: (id: string, ctx: Context) => void,
  openRun: (op: Operation) => void,
  reconnect: () => Promise<void>,
) {
  const root = el("aside", "chat");
  const head = el("div", "chat-head");
  head.append(
    el("div", "agent-symbol", "✳"),
    el("div", "", "RTL Agent"),
    el("span", "chat-status", ""),
  );
  const status = head.lastChild as HTMLElement;
  const history = el("div", "chat-history");
  history.setAttribute("aria-live", "polite");
  const intro = el("div", "chat-intro");
  intro.append(
    el("span", "eyebrow", "DESIGN WITH CONFIDENCE"),
    el("h2", "", "从想法，到经过验证的 RTL。"),
    note("围绕当前模块、代码和波形提问，或直接分析已保存的验证与修复记录。"),
  );
  history.append(intro);
  const suggestions = el("div", "suggestions");
  for (const text of [
    "这个设计如何拆分模块？",
    "解释当前验证结果",
    "重新验证当前设计",
    "按预置规格生成并验证",
    "分析失败原因与修复记录",
  ])
    suggestions.append(
      button(
        text,
        () => {
          if (unsupported.has(text)) {
            feedback = unsupportedNotice;
            render();
            return;
          }
          textarea.value = text;
          saveDraft();
          render();
          textarea.focus();
          form.requestSubmit();
        },
        "suggestion",
      ),
    );
  const list = el("div", "messages");
  const notice = el("p", "chat-notice");
  notice.setAttribute("role", "status");
  history.append(suggestions, notice, list);
  const form = el("form", "chat-form");
  const textarea = el("textarea");
  textarea.placeholder = "询问当前设计、验证结果或失败原因…";
  textarea.setAttribute("aria-label", "与 RTL Agent 对话");
  textarea.maxLength = 4000;
  const target = el("div", "chat-target mono");
  const footer = el("div", "composer-footer");
  const hint = el("span", "muted", "Enter 发送 · Shift + Enter 换行");
  const submit = button(
    "发送 ↑",
    () => {
      form.requestSubmit();
    },
    "primary",
  );
  footer.append(hint, submit);
  const error = el("p", "chat-error");
  error.setAttribute("role", "status");
  const retry = button(
    "重新连接",
    async () => {
      connecting = true;
      feedback = "";
      render();
      try {
        await reconnect();
        textarea.focus();
      } catch (e) {
        feedback = errorText(e);
      } finally {
        connecting = false;
        render();
      }
    },
    "text-button",
  );
  form.append(target, textarea, footer, error, retry);
  let pending = false;
  let connecting = false;
  let feedback = "";
  const unsupported = new Set(["重新验证当前设计", "按预置规格生成并验证"]);
  const normalize = (s: string) => s.trim().replace(/[？?。！!]+$/, "");
  const unsupportedNotice =
    "当前演示暂不支持现场重新验证或生成并验证。模块拆分、验证解释和失败原因与修复记录分析可以使用。";
  let pollTimer: ReturnType<typeof setTimeout> | undefined;
  let polling = false;
  let disposed = false;
  async function syncReply() {
    pollTimer = undefined;
    if (disposed || polling || !state.session || state.caseId !== initialCase)
      return;
    const sid = state.session.session_id;
    polling = true;
    try {
      const saved = await refreshSession(sid, initialCase);
      if (
        !disposed &&
        state.session?.session_id === sid &&
        state.caseId === initialCase
      ) {
        state.session = saved;
        state.online = true;
        render();
      }
    } catch {
      feedback = "正在恢复回答状态，草稿已保留；不会重复发送问题。";
    } finally {
      polling = false;
      if (!disposed) render();
    }
  }
  const initialCase = state.caseId;
  function scheduleReplySync() {
    if (disposed || polling || pollTimer || state.caseId !== initialCase)
      return;
    if (state.session?.messages.some((m) => m.state === "replying"))
      pollTimer = setTimeout(() => void syncReply(), 2000);
  }
  window.addEventListener(
    "pagehide",
    () => {
      disposed = true;
      clearTimeout(pollTimer);
    },
    { once: true },
  );
  const draftKey = "rtl-chat-draft:" + state.caseId;
  function saveDraft() {
    try {
      if (textarea.value) sessionStorage.setItem(draftKey, textarea.value);
      else sessionStorage.removeItem(draftKey);
    } catch {}
  }
  textarea.oninput = () => {
    saveDraft();
    render();
  };
  let unresolved: {
    id: string;
    text: string;
    ctx: ReturnType<typeof context>;
  } | null = null;
  try {
    unresolved = JSON.parse(
      sessionStorage.getItem("rtl-pending-message:" + state.caseId) || "null",
    );
    textarea.value = sessionStorage.getItem(draftKey) ?? unresolved?.text ?? "";
  } catch {}
  form.onsubmit = async (e) => {
    e.preventDefault();
    const draft = textarea.value;
    if (unsupported.has(normalize(draft))) {
      feedback = unsupportedNotice;
      render();
      return;
    }
    if (state.health?.capabilities.chat?.available !== true) {
      feedback =
        "AI 模型暂不可用，请稍后重试或重新连接；不会使用固定摘要代替模型回答。";
      render();
      return;
    }
    const text = draft.trim();
    if (
      !text ||
      pending ||
      !state.online ||
      !state.session ||
      state.session.messages.some((m) => m.state === "replying")
    )
      return;
    pending = true;
    submit.disabled = true;
    feedback = "";
    saveDraft();
    const ctx = context();
    if (state.step === "diagnose") {
      const attempt = selectedAttempt();
      if (attempt) {
        ctx.version_id = attempt.baseline_version_id;
        ctx.validation_id = attempt.before_validation_id;
      }
    }
    const sentSession = state.session!.session_id;
    if (
      !unresolved ||
      unresolved.text !== text ||
      JSON.stringify(unresolved.ctx) !== JSON.stringify(ctx)
    )
      unresolved = { id: key(), text, ctx };
    sessionStorage.setItem(
      "rtl-pending-message:" + state.caseId,
      JSON.stringify(unresolved),
    );
    try {
      await send(text, unresolved.ctx, unresolved.id);
      sessionStorage.removeItem("rtl-pending-message:" + state.caseId);
      unresolved = null;
      if (textarea.value === draft) textarea.value = "";
      saveDraft();
      if (
        state.session?.session_id === sentSession &&
        state.caseId === ctx.case_id
      )
        state.session = await refreshSession(sentSession, ctx.case_id);
      render();
    } catch (e) {
      feedback = errorText(e);
    } finally {
      pending = false;
      render();
    }
  };
  textarea.onkeydown = (e) => {
    if (
      e.key === "Enter" &&
      !e.shiftKey &&
      !e.isComposing &&
      e.keyCode !== 229
    ) {
      e.preventDefault();
      form.requestSubmit();
    }
  };
  root.append(head, history, form);
  let previous = "";
  function render() {
    scheduleReplySync();
    status.textContent = state.online ? "已连接" : "历史浏览";
    status.classList.toggle("connected", state.online);
    target.textContent =
      (state.mode === "historical" ? "历史 · " : "实时 · ") +
      (state.context.module_id?.replace("e203_exu_", "") ||
        state.bundle?.title ||
        "RTL") +
      " · " +
      (state.context.version_id?.split("-").at(-1) || "规格");
    target.textContent +=
      " · " +
      {
        workspace: "设计工作台",
        optimization: "持续优化",
        experience: "自进化",
      }[state.view];
    if (state.context.memory_revision_id)
      target.textContent +=
        " · 经验 " + state.context.memory_revision_id.slice(-8);
    const available = !!state.session && state.online;
    const capable =
      unsupported.has(normalize(textarea.value)) ||
      state.health?.capabilities.chat?.available === true;
    submit.disabled =
      !available ||
      !capable ||
      pending ||
      state.session?.messages.some((m) => m.state === "replying") === true;
    retry.hidden = available;
    retry.disabled = connecting;
    retry.textContent = connecting ? "正在连接…" : "重新连接";
    error.textContent = !available
      ? (feedback ? feedback + " " : "") +
        "后台未连接，可先输入；草稿会保留，连接后可发送。"
      : feedback ||
        (state.health?.capabilities.chat?.available === false
          ? "AI 模型暂不可用，请稍后重试或重新连接。"
          : "");
    notice.hidden = !feedback;
    notice.textContent = feedback;
    const signature = JSON.stringify([
      state.session?.messages,
      state.session?.operations,
    ]);
    if (signature === previous) return;
    previous = signature;
    const follow =
      history.scrollHeight - history.scrollTop - history.clientHeight < 90 ||
      pending;
    list.replaceChildren();
    for (const m of state.session?.messages || []) {
      const item = el("article", "message");
      const user = el("div", "user-message", m.text);
      const answer = el(
        "div",
        "agent-message",
        m.state === "replying"
          ? "Agent 正在分析…"
          : m.answer || "对话中断，请重新发送。",
      );
      answer.classList.toggle(
        "failed",
        m.state === "failed" || m.state === "interrupted",
      );
      item.append(user, answer);
      if (m.answer_source === "recorded_evidence")
        item.append(el("small", "muted", "历史消息 · 归档摘要（未调用模型）"));
      if (m.answer_source === "model")
        item.append(
          el(
            "small",
            "muted",
            "AI 模型回答" +
              (m.model_receipt?.model ? " · " + m.model_receipt.model : "") +
              " · 基于当前任务证据",
          ),
        );
      if (m.state === "replying")
        item.append(
          button("刷新回答状态", () => void syncReply(), "text-button"),
        );
      for (const ref of m.evidence_refs || [])
        item.append(
          button(
            "查看依据 ↗",
            () => openEvidence(ref.artifact_id, m.context_ref),
            "evidence-button",
          ),
        );
      list.append(item);
    }
    for (const op of state.session?.operations || []) {
      const card = el("div", "operation-card");
      const name =
        {
          verify: "系统验证",
          fix: "分析并修复",
          generate_and_verify: "RTL 生成与验证",
        }[op.kind] || op.kind;
      card.append(
        el("strong", "", "实时 · " + name),
        note(
          ({
            accepted: "已接收",
            running: "执行中",
            completed: "已完成",
            failed: "执行失败",
            timed_out: "达到时间上限",
            interrupted: "运行中断",
          }[op.state] || op.state) + (op.stage ? " · " + op.stage : ""),
        ),
      );
      if (op.error) card.append(note(op.error));
      card.append(
        button(
          op.state === "completed" ? "查看本次结果 ↗" : "查看实时过程 ↗",
          () => openRun(op),
          "text-button",
        ),
      );
      list.append(card);
    }
    requestAnimationFrame(() => {
      if (follow) history.scrollTop = history.scrollHeight;
    });
  }
  render();
  return {
    element: root,
    render,
    reveal: () => {
      textarea.focus();
      requestAnimationFrame(() => {
        history.scrollTop = history.scrollHeight;
      });
    },
    setConnection: (up: boolean) => {
      status.textContent = up ? "已连接" : "正在重连";
      status.classList.toggle("connected", up);
    },
  };
}
