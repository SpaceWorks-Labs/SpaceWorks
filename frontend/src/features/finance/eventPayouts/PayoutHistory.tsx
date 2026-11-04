import { money } from "./format";
import { permits } from "./types";
import type { PayoutEntry } from "./types";

export function PayoutHistory({ entries, onAmend }: { entries: PayoutEntry[]; onAmend?: (entry: PayoutEntry) => void }) {
  return <section aria-label="Payout history" className="grid gap-3"><h2 className="font-semibold">Payout history</h2>
    <p className="text-sm text-muted">Corrections replace the effective amount of their chain. Original records stay visible.</p>
    {entries.length === 0 ? <p>No payouts have been recorded.</p> : entries.map(entry => {
      const replaced = entries.some(item => item.amends_id === entry.id);
      return <article className="grid gap-2 rounded-2xl border border-line p-4" key={entry.id}>
        <h3 className="font-semibold">{entry.is_void ? "Voided recording" : money(entry.amount_minor, entry.currency)}{replaced ? " · Replaced by a correction" : " · Current record"}</h3>
        <p>{entry.method.replace(/_/g, " ")} · {entry.reference} · {new Date(entry.paid_at).toLocaleString()}</p>
        <p className="text-sm text-muted">{entry.amends_id ? `Corrects record ${entry.amends_id}` : "Original record"}</p>
        {onAmend && permits(entry, "amend") ? <button className="desk-button min-h-11" type="button" onClick={() => onAmend(entry)}>Correct recording error</button> : null}
      </article>;
    })}
  </section>;
}
