import { state, type Wave, type WaveSignal } from "./state";
import { el, button, note } from "./dom";
export function valueAt(s: WaveSignal, t: bigint) {
  let value = s.initial_value;
  for (const [time, v] of s.changes) {
    if (BigInt(time) > t) break;
    value = v;
  }
  return value;
}
export function displayValue(value: string, width: number) {
  if (/[xz]/i.test(value)) return value;
  if (width === 1) return value;
  try {
    return (
      "0x" +
      BigInt("0b" + value)
        .toString(16)
        .padStart(Math.ceil(width / 4), "0")
    );
  } catch {
    return value;
  }
}
export function fitWindow(
  start: bigint,
  end: bigint,
  lo: bigint,
  hi: bigint,
): [bigint, bigint] {
  if (hi <= lo) return [lo, lo + 1n];
  let size = end - start;
  if (size < 1n) size = 1n;
  if (size >= hi - lo) return [lo, hi];
  if (start < lo) start = lo;
  if (start + size > hi) start = hi - size;
  return [start, start + size];
}
export function zoomWindow(
  start: bigint,
  end: bigint,
  center: bigint,
  numerator: bigint,
  denominator: bigint,
  lo: bigint,
  hi: bigint,
) {
  const size = ((end - start) * numerator) / denominator || 1n;
  return fitWindow(center - size / 2n, center + (size - size / 2n), lo, hi);
}
const ns = "http://www.w3.org/2000/svg";
function svg<K extends keyof SVGElementTagNameMap>(
  tag: K,
  attrs: Record<string, string | number>,
  text?: string,
) {
  const n = document.createElementNS(ns, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, String(v));
  if (text) n.textContent = text;
  return n;
}
export function waveform(
  data: Wave,
  onContext: () => void,
  onWindow?: (range: [bigint, bigint]) => void,
) {
  const root = el("section", "wave-panel");
  const controls = el("div", "wave-controls");
  const time = el("span", "mono");
  const canvas = el("div", "wave-canvas");
  const values = el("div", "cursor-values");
  const lo = 0n,
    hi = BigInt(data.full_end_ticks || data.end_ticks);
  if (state.viewport && (state.viewport[0] < lo || state.viewport[1] > hi))
    root.append(
      note("两次仿真时间范围不同，已显示当前可用范围；范围外没有比较数据。"),
    );
  state.viewport = state.viewport
    ? fitWindow(...state.viewport, lo, hi)
    : state.caseId === "e203"
      ? fitWindow(1000n, 1250n, lo, hi)
      : fitWindow(0n, 200n, lo, hi);
  if (state.cursor === null)
    state.cursor = 1125n >= lo && 1125n <= hi ? 1125n : lo;
  let drag: number | null = null;
  function change(range: [bigint, bigint]) {
    if (
      onWindow &&
      (range[0] < BigInt(data.start_ticks) || range[1] > BigInt(data.end_ticks))
    ) {
      onWindow(range);
      return;
    }
    state.viewport = range;
    draw();
    onContext();
  }
  controls.append(
    button("−", () => {
      const [a, b] = state.viewport!;
      change(zoomWindow(a, b, (a + b) / 2n, 2n, 1n, lo, hi));
    }),
    button("+", () => {
      const [a, b] = state.viewport!;
      change(
        zoomWindow(
          a,
          b,
          state.cursor! >= a && state.cursor! <= b
            ? state.cursor!
            : (a + b) / 2n,
          1n,
          2n,
          lo,
          hi,
        ),
      );
    }),
    button("←", () => {
      const [a, b] = state.viewport!;
      change(fitWindow(a - (b - a) / 2n, b - (b - a) / 2n, lo, hi));
    }),
    button("→", () => {
      const [a, b] = state.viewport!;
      change(fitWindow(a + (b - a) / 2n, b + (b - a) / 2n, lo, hi));
    }),
    button("全程", () => change([lo, hi])),
    time,
  );
  const tickInput = el("input");
  tickInput.placeholder = "时间刻度";
  tickInput.inputMode = "numeric";
  tickInput.maxLength = 40;
  tickInput.setAttribute("aria-label", "跳转到时间刻度");
  controls.insertBefore(tickInput, time);
  controls.insertBefore(
    button("跳转", () => {
      if (!/^\d+$/.test(tickInput.value)) {
        tickInput.setCustomValidity("请输入整数时间刻度");
        tickInput.reportValidity();
        return;
      }
      tickInput.setCustomValidity("");
      const t = BigInt(tickInput.value);
      state.cursor = t < lo ? lo : t > hi ? hi - 1n : t;
      const [a, b] = state.viewport!;
      change(
        fitWindow(
          state.cursor - (b - a) / 2n,
          state.cursor + (b - a + 1n) / 2n,
          lo,
          hi,
        ),
      );
    }),
    time,
  );
  root.append(controls, canvas, values);
  function draw() {
    const [a, b] = state.viewport!;
    time.textContent = a + "–" + b + " " + data.timescale.unit;
    canvas.replaceChildren();
    values.replaceChildren();
    const width = 1000,
      labelWidth = 208,
      plot = width - labelWidth - 18,
      row = 31,
      height = 36 + data.signals.length * row;
    const chart = svg("svg", {
      viewBox: `0 0 ${width} ${height}`,
      role: "img",
      "aria-label": "真实 DUT 与参考设计仿真波形",
    });
    const x = (t: bigint) =>
      labelWidth + (Number(((t - a) * 1000000n) / (b - a)) / 1000000) * plot;
    for (let i = 0; i <= 5; i++) {
      const t = a + ((b - a) * BigInt(i)) / 5n;
      chart.append(
        svg("line", {
          x1: x(t),
          x2: x(t),
          y1: 24,
          y2: height,
          stroke: "#29374b",
          "stroke-width": 1,
        }),
        svg(
          "text",
          { x: x(t) + 3, y: 16, fill: "#8c9db2", "font-size": 11 },
          String(t),
        ),
      );
    }
    const failures = data.sample_markers.filter(
      (m) =>
        m.verdict === "fail" &&
        BigInt(m.time_ticks) >= a &&
        BigInt(m.time_ticks) <= b,
    );
    for (const m of data.sample_markers) {
      const t = BigInt(m.time_ticks);
      if (t < a || t > b) continue;
      chart.append(
        svg("line", {
          x1: x(t),
          x2: x(t),
          y1: 25,
          y2: height,
          stroke: m.verdict === "fail" ? "#f87979" : "#497468",
          "stroke-opacity": m.verdict === "fail" ? 1 : 0.23,
          "stroke-dasharray": m.verdict === "fail" ? "4 3" : "1 5",
        }),
      );
      if (m.verdict === "fail" && (failures.length <= 3 || m === failures[0]))
        chart.append(
          svg(
            "text",
            { x: x(t) + 4, y: 30, fill: "#ff8d8d", "font-size": 11 },
            failures.length > 3
              ? "采样差异 × " + failures.length + "（当前窗口）"
              : "采样差异 · " + m.failed_signals.join(", "),
          ),
        );
    }
    for (const [sIndex, s] of data.signals.entries()) {
      const y = 35 + sIndex * row;
      const color =
        s.id.startsWith("ref") || s.id.endsWith("_ref")
          ? "#e5bf71"
          : s.id.startsWith("dut") || s.id.endsWith("_dut")
            ? "#77d4b8"
            : "#9baed0";
      chart.append(
        svg("text", { x: 12, y: y + 16, fill: color, "font-size": 11 }, s.id),
        svg("line", {
          x1: 0,
          x2: width,
          y1: y + row - 2,
          y2: y + row - 2,
          stroke: "#233044",
        }),
      );
      const changes: [[bigint, string], ...[bigint, string][]] = [
        [a, valueAt(s, a)],
        ...s.changes
          .filter(([t]) => BigInt(t) > a && BigInt(t) <= b)
          .map(([t, v]) => [BigInt(t), v] as [bigint, string]),
      ];
      changes.push([b, changes[changes.length - 1][1]]);
      for (let i = 0; i < changes.length - 1; i++) {
        const [t, v] = changes[i],
          next = changes[i + 1][0],
          x1 = x(t),
          x2 = x(next);
        if (s.width === 1) {
          const yy = v === "1" ? y + 5 : y + 22;
          chart.append(
            svg("path", {
              d: `M ${x1} ${yy} H ${x2}`,
              stroke: color,
              fill: "none",
              "stroke-width": 1.4,
            }),
          );
          if (i) {
            const py = changes[i - 1][1] === "1" ? y + 5 : y + 22;
            chart.append(
              svg("path", {
                d: `M ${x1} ${py} V ${yy}`,
                stroke: color,
                fill: "none",
              }),
            );
          }
          if (/[xz]/i.test(v) && x2 - x1 > 10)
            chart.append(
              svg(
                "text",
                { x: x1 + 3, y: y + 16, fill: "#f59e98", "font-size": 10 },
                v,
              ),
            );
        } else {
          chart.append(
            svg("path", {
              d: `M ${x1} ${y + 14} L ${x1 + Math.min(4, (x2 - x1) / 2)} ${y + 5} H ${x2 - 2} L ${x2} ${y + 14} L ${x2 - 2} ${y + 23} H ${x1 + Math.min(4, (x2 - x1) / 2)} Z`,
              stroke: color,
              fill: color,
              "fill-opacity": 0.055,
              "stroke-width": 1,
            }),
          );
          const text = displayValue(v, s.width);
          if (x2 - x1 > text.length * 6 + 8)
            chart.append(
              svg(
                "text",
                { x: x1 + 6, y: y + 18, fill: color, "font-size": 10 },
                text,
              ),
            );
        }
      }
      const cell = el(
        "span",
        "mono",
        s.id + ": " + displayValue(valueAt(s, state.cursor!), s.width),
      );
      values.append(cell);
    }
    if (state.cursor! >= a && state.cursor! <= b)
      chart.append(
        svg("line", {
          x1: x(state.cursor!),
          x2: x(state.cursor!),
          y1: 24,
          y2: height,
          stroke: "#99baff",
          "stroke-width": 1.5,
        }),
      );
    const caption = el(
      "div",
      "cursor-caption",
      "游标 " + state.cursor + " " + data.timescale.unit + " · 原始波形显示值",
    );
    values.prepend(caption);
    chart.onpointerdown = (e) => {
      drag = e.clientX;
      chart.setPointerCapture(e.pointerId);
    };
    chart.onpointerup = (e) => {
      if (drag === null) return;
      const rect = chart.getBoundingClientRect();
      const dx = e.clientX - drag;
      drag = null;
      if (Math.abs(dx) > 8) {
        const shift =
          ((b - a) * BigInt(Math.round((dx / rect.width) * 1000000))) /
          1000000n;
        change(fitWindow(a - shift, b - shift, lo, hi));
        return;
      }
      const relative =
        (((e.clientX - rect.left) / rect.width) * width - labelWidth) / plot;
      state.cursor =
        a +
        ((b - a) *
          BigInt(Math.round(Math.max(0, Math.min(1, relative)) * 1000000))) /
          1000000n;
      draw();
      onContext();
    };
    canvas.append(chart);
  }
  if (data.missing_signals.length)
    root.append(note("缺失信号：" + data.missing_signals.join("、")));
  if (data.marker_status !== "verified")
    root.append(note("本次波形的采样标记尚未核验，仅展示原始信号。"));
  draw();
  return {
    element: root,
    jump: (ticks: string) => {
      state.cursor = BigInt(ticks);
      change(fitWindow(state.cursor - 80n, state.cursor + 80n, lo, hi));
    },
  };
}
