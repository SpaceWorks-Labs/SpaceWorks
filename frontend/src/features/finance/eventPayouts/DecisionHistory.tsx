import { money } from "./format";
import type { DecisionRevision } from "./types";

export function EvidenceDetails({ value }: { value: unknown }) {
  if (value == null) return <span className="text-muted">None</span>;
  if (typeof value === "boolean") return <span>{value ? "Yes" : "No"}</span>;
  if (typeof value !== "object") return <span className="break-words">{String(value)}</span>;
  if (Array.isArray(value)) return <ol className="grid gap-3 pl-4">{value.map((item, index) => <li key={index}><EvidenceDetails value={item} /></li>)}</ol>;
  return <dl className="grid gap-2">{Object.entries(value).map(([key, item]) => <div key={key} className="border-l border-line pl-3">
    <dt className="text-sm font-semibold">{key.replace(/_/g, " ")}</dt><dd><EvidenceDetails value={item} /></dd>
  </div>)}</dl>;
}
export function DecisionHistory({ revisions, currency }: { revisions: DecisionRevision[]; currency: string }) {
  return <section aria-label="Financial decisions" className="grid gap-3"><h2 className="font-semibold">Financial decisions</h2>
    {revisions.map(revision => <details key={revision.id} className="rounded-2xl border border-line p-4">
      <summary className="min-h-11 cursor-pointer font-semibold">Revision {revision.sequence} · {revision.kind} · {money(revision.approved_minor, currency)}</summary>
      <p className="mb-3 text-sm text-muted">{revision.created_at} · {revision.reason_code.replace(/_/g, " ")}</p>
      <EvidenceDetails value={revision.decision_summary} />
    </details>)}
  </section>;
}
