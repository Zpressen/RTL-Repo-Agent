import {
  state,
  validation,
  selectedAttempt,
  historicalRun,
  type PackageDescriptor,
} from "./state";
export function selectedPackage() {
  const b = state.bundle!,
    v = validation();
  if (!v || !b.validations.some((x) => x.validation_id === v.validation_id))
    throw new Error("当前记录未公开，不能下载公开证据包。");
  const diagnosis = state.step === "diagnose" ? selectedAttempt() : undefined;
  const before =
    !diagnosis && state.comparing
      ? selectedAttempt()?.before_validation_id ||
        (historicalRun() ? undefined : b.comparison_pair.before_validation_id)
      : undefined;
  const after = diagnosis
    ? diagnosis.before_validation_id
    : state.comparing
      ? selectedAttempt()?.validation_id ||
        (historicalRun()
          ? v.validation_id
          : b.comparison_pair.after_validation_id)
      : v.validation_id;
  const descriptor = before
    ? b.evidence_packages?.comparisons.find(
        (x) => x.before_validation_id === before && x.validation_id === after,
      )
    : b.evidence_packages?.single[after];
  if (
    descriptor &&
    (descriptor.validation_id !== after ||
      descriptor.kind !== (before ? "comparison" : "single") ||
      (descriptor.before_validation_id || undefined) !==
        (before || undefined) ||
      descriptor.url !==
        `/cases/${state.caseId}/evidence/${descriptor.sha256}.zip`)
  )
    throw new Error("证据包选择与当前验证不一致。");
  return { after, before, descriptor };
}
export async function downloadEvidence() {
  const { after, before, descriptor } = selectedPackage();
  const cid = state.caseId;
  let url = descriptor?.url;
  if (!url) {
    if (!state.online)
      throw new Error("后台未连接，且本次选择没有静态证据包。");
    url =
      "/api/cases/" +
      cid +
      "/evidence.zip?validation_id=" +
      encodeURIComponent(after) +
      (before ? "&before_validation_id=" + encodeURIComponent(before) : "");
  }
  if (
    descriptor &&
    !/^\/cases\/[a-z0-9_]+\/evidence\/[a-f0-9]{64}\.zip$/.test(url!)
  )
    throw new Error("证据包地址不合法。");
  const res = await fetch(url, {
    credentials: "same-origin",
    headers: { "X-Demo-Case": cid },
  });
  if (
    !res.ok ||
    !res.headers.get("Content-Type")?.includes("application/zip")
  ) {
    let text = "证据包暂时不可用。";
    try {
      text = (await res.json()).error?.message || text;
    } catch {}
    throw new Error(text);
  }
  const blob = await res.blob();
  if (blob.size > 64 * 1024 * 1024) throw new Error("证据包超过下载上限。");
  if (descriptor) {
    const digest = await crypto.subtle.digest(
      "SHA-256",
      await blob.arrayBuffer(),
    );
    const h = Array.from(new Uint8Array(digest), (b) =>
      b.toString(16).padStart(2, "0"),
    ).join("");
    if (h !== descriptor.sha256 || blob.size !== descriptor.size_bytes)
      throw new Error("证据包完整性校验失败。");
  }
  const object = URL.createObjectURL(blob),
    a = document.createElement("a");
  a.href = object;
  a.download = cid + "-" + (before ? "comparison" : "validation") + ".zip";
  a.click();
  setTimeout(() => URL.revokeObjectURL(object), 1000);
}
