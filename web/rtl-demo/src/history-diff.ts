// Full line alignment with bounded memory; emit only changed hunks plus context.
export function unifiedDiff(before: string, after: string, file: string) {
  const a = before ? before.replace(/\n$/, "").split("\n") : [],
    b = after ? after.replace(/\n$/, "").split("\n") : [];
  if ((a.length + 1) * (b.length + 1) > 4_000_000)
    throw new Error("文件较大，请在 RTL 代码页查看完整版本。");
  const rows = Array.from(
    { length: a.length + 1 },
    () => new Uint16Array(b.length + 1),
  );
  for (let i = a.length - 1; i >= 0; i--)
    for (let j = b.length - 1; j >= 0; j--)
      rows[i][j] =
        a[i] === b[j]
          ? rows[i + 1][j + 1] + 1
          : Math.max(rows[i + 1][j], rows[i][j + 1]);
  const lines: { mark: string; text: string; left: number; right: number }[] =
    [];
  let i = 0,
    j = 0;
  while (i < a.length || j < b.length) {
    const l = i + 1,
      r = j + 1;
    if (i < a.length && j < b.length && a[i] === b[j]) {
      lines.push({ mark: " ", text: a[i++], left: l, right: r });
      j++;
    } else if (
      i < a.length &&
      (j === b.length || rows[i + 1][j] >= rows[i][j + 1])
    )
      lines.push({ mark: "-", text: a[i++], left: l, right: r });
    else lines.push({ mark: "+", text: b[j++], left: l, right: r });
  }
  const intervals: [number, number][] = [];
  for (let k = 0; k < lines.length; k++)
    if (lines[k].mark !== " ") {
      const start = Math.max(0, k - 3),
        end = Math.min(lines.length, k + 4),
        last = intervals.at(-1);
      if (last && start <= last[1]) last[1] = end;
      else intervals.push([start, end]);
    }
  return (
    `--- 基线/${file}\n+++ 候选/${file}\n` +
    intervals
      .map(([start, end]) => {
        const chunk = lines.slice(start, end),
          left = chunk.filter((x) => x.mark !== "+").length,
          right = chunk.filter((x) => x.mark !== "-").length;
        return (
          `@@ -${chunk[0].left},${left} +${chunk[0].right},${right} @@\n` +
          chunk.map((x) => x.mark + x.text).join("\n")
        );
      })
      .join("\n")
  );
}
