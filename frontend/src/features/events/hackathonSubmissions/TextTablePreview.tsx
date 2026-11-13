import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState } from "react";
import { ActionControl } from "../../../components/ui";

const LIMIT = 5 * 1024 ** 2;

export function parseTable(text: string): string[][] {
  const first = text.split(/\r?\n/, 1)[0];
  const delimiter = [",", ";", "\t"].sort((a, b) => first.split(b).length - first.split(a).length)[0];
  const rows: string[][] = [];
  let row: string[] = [], cell = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (char === '"') {
      if (quoted && text[i + 1] === '"') { cell += '"'; i++; }
      else quoted = !quoted;
    } else if (!quoted && (char === delimiter || char === "\n")) {
      row.push(cell.replace(/\r$/, "")); cell = "";
      if (char === "\n") { rows.push(row); row = []; if (rows.length === 1000) break; }
    } else cell += char;
    if (cell.length > 8192 || row.length > 100) throw new Error(t`Table preview limit.`);
  }
  if (quoted) throw new Error(t`Invalid quoted table.`);
  if (cell || row.length) { row.push(cell.replace(/\r$/, "")); rows.push(row); }
  if (!rows.length || rows[0].length > 100) throw new Error(t`Invalid table.`);
  return rows;
}

/** CSV export is inert in spreadsheet applications; original bytes stay immutable. */
export function safeTableCsv(rows: readonly string[][]) {
  return rows.map(row => row.map(value => {
    const inert = /^[\s]*[=+\-@]/.test(value) ? "'" + value : value;
    return '"' + inert.replace(/"/g, '""') + '"';
  }).join(",")).join("\r\n");
}

export function TextTablePreview({ bytes, table, load, download }: {
  bytes: number; table: boolean; load: (signal: AbortSignal) => Promise<Blob>; download: () => void;
}) {
  const [text, setText] = useState<string | null>(null), [rows, setRows] = useState<string[][] | null>(null);
  const [error, setError] = useState(false), [pending, setPending] = useState(false);
  const controller = useRef<AbortController | null>(null), alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; controller.current?.abort(); }; }, []);
  async function preview() {
    setPending(true); setError(false); controller.current = new AbortController();
    try {
      const blob = await load(controller.current.signal);
      if (blob.size > LIMIT || blob.size !== bytes) throw new Error();
      const buffer = await blob.arrayBuffer(), prefix = new Uint8Array(buffer);
      const value = new TextDecoder(prefix[0] === 255 && prefix[1] === 254 ? "utf-16le" : "utf-8", { fatal: true }).decode(buffer);
      if (alive.current) { if (table) setRows(parseTable(value)); else setText(value); }
    } catch { if (alive.current) setError(true); }
    finally { if (alive.current) setPending(false); }
  }
  function exportCsv() {
    if (!rows) return;
    const url = URL.createObjectURL(new Blob([safeTableCsv(rows)], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = "project-table.csv"; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
  return <section aria-label={table ? t`Table preview` : t`Source preview`} className="grid gap-3">
    {bytes > LIMIT ? <p className="text-sm text-muted">{t`This file is too large for an inline text preview. Download the original to inspect it.`}</p> :
      <ActionControl action={{ label: table ? t`Preview table` : t`Preview text`, pending, onClick: () => void preview() }} />}
    {error ? <p role="status">{t`Preview unavailable. The original remains available.`}</p> : null}
    {text !== null ? <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-xl border border-line bg-panel p-4 text-sm text-ink" style={{ fontFamily: "inherit" }}>{text}</pre> : null}
    {rows ? <div className="max-h-96 overflow-auto"><table className="w-full text-left text-sm text-ink"><caption className="text-muted">{t`First ${rows.length} rows; values are displayed as text.`}</caption>
      <thead><tr>{rows[0].map((cell, i) => <th key={i} scope="col" className="border-b border-line p-2">{cell || t`Column ${i + 1}`}</th>)}</tr></thead>
      <tbody>{rows.slice(1).map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j} className="border-b border-line p-2">{cell}</td>)}</tr>)}</tbody></table></div> : null}
    <div className="flex flex-wrap gap-3"><ActionControl action={{ label: t`Download original`, onClick: download }} />
      {rows ? <ActionControl action={{ label: t`Export displayed table safely`, onClick: exportCsv }} /> : null}</div>
  </section>;
}
