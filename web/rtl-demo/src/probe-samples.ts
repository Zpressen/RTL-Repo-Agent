import type { Validation } from "./state";
import { el, note } from "./dom";

function compact(value: string) {
  if (/^[01]+$/.test(value))
    return (
      "0x" +
      BigInt("0b" + value)
        .toString(16)
        .padStart(Math.ceil(value.length / 4), "0")
    );
  return value;
}

export function probeSamples(v: Validation) {
  const root = el("section", "probe-samples");
  const samples = v.probe_samples || [];
  const select = el("select");
  select.setAttribute("aria-label", "探针信号");
  for (const signal of new Set(samples.map((s) => s.signal))) {
    const o = el("option", "", signal);
    o.value = signal;
    select.append(o);
  }
  const firstFailure = v.signal_mismatches?.find((s) =>
    samples.some((p) => p.signal === s.signal),
  )?.signal;
  if (firstFailure && samples.some((s) => s.signal === firstFailure))
    select.value = firstFailure;
  const heading = el("h3", "", "历史波形探针 · 离散采样"),
    table = el("table", "probe-table"),
    pager = el("div", "verification-toolbar");
  let page = 0;
  const previous = el("button", "segment", "上一页"),
    next = el("button", "segment", "下一页"),
    count = el("span", "muted");
  function render() {
    const filtered = samples.filter((s) => s.signal === select.value),
      perPage = 12;
    page = Math.min(
      page,
      Math.max(0, Math.ceil(filtered.length / perPage) - 1),
    );
    const header = el("tr");
    for (const label of ["时刻 (ps)", "Reference", "DUT", "探针比较"])
      header.append(el("th", "", label));
    const head = el("thead"),
      body = el("tbody");
    head.append(header);
    for (const sample of filtered.slice(page * perPage, (page + 1) * perPage)) {
      const row = el("tr");
      row.title = sample.reference_path + " / " + sample.dut_path;
      const known =
          /^[01]+$/.test(sample.reference) && /^[01]+$/.test(sample.dut),
        same = sample.reference === sample.dut;
      for (const value of [
        sample.time_ticks,
        compact(sample.reference),
        compact(sample.dut),
        known ? (same ? "一致" : "差异") : "未知值",
      ])
        row.append(el("td", "mono", value));
      row.className = known && !same ? "probe-difference" : "";
      body.append(row);
    }
    table.replaceChildren(head, body);
    previous.disabled = page === 0;
    next.disabled = (page + 1) * perPage >= filtered.length;
    count.textContent = `${page + 1} / ${Math.max(1, Math.ceil(filtered.length / perPage))} · ${filtered.length} 条记录`;
  }
  previous.onclick = () => {
    page--;
    render();
  };
  next.onclick = () => {
    page++;
    render();
  };
  select.onchange = () => {
    page = 0;
    render();
  };
  pager.append(previous, count, next);
  const wrap = el("div", "probe-table-wrap");
  wrap.append(table);
  root.append(
    heading,
    note("表内一致/差异仅表示该时刻的探针值，不替代测试平台的验证结论。"),
    select,
    wrap,
    pager,
  );
  render();
  return {
    element: root,
    jump: (ticks: string) => {
      const failure = firstFailure;
      if (failure && samples.some((s) => s.signal === failure))
        select.value = failure;
      const filtered = samples.filter((s) => s.signal === select.value);
      const t = BigInt(ticks);
      let closest = 0;
      for (let i = 0; i < filtered.length; i++) {
        const distance = (x: string) => {
          const d = BigInt(x) - t;
          return d < 0n ? -d : d;
        };
        if (
          distance(filtered[i].time_ticks) <
          distance(filtered[closest].time_ticks)
        )
          closest = i;
      }
      page = Math.floor(closest / 12);
      render();
      root.scrollIntoView({ block: "nearest" });
    },
  };
}
