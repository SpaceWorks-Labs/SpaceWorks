import { formatDateTime } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { paymentMethodLabel } from "../../../lib/money";
import { money } from "./format";
import { permits } from "./types";
import type { PayoutEntry } from "./types";

export function PayoutHistory({ entries, onAmend }: { entries: PayoutEntry[]; onAmend?: (entry: PayoutEntry) => void }) {
  return <section aria-label={t`Payout history`} className="grid gap-3"><h2 className="font-semibold">{t`Payout history`}</h2>
    <p className="text-sm text-muted">{t`Corrections replace the effective amount of their chain. Original records stay visible.`}</p>
    {entries.length === 0 ? <p>{t`No payouts have been recorded.`}</p> : entries.map(entry => {
      const replaced = entries.some(item => item.amends_id === entry.id);
      return <article className="grid gap-2 rounded-2xl border border-line p-4" key={entry.id}>
        <h3 className="font-semibold">{entry.is_void ? t`Voided recording` : money(entry.amount_minor, entry.currency)}{replaced ? t` · Replaced by a correction` : t` · Current record`}</h3>
        <p>{paymentMethodLabel(entry.method)} · {entry.reference} · {formatDateTime(entry.paid_at)}</p>
        <p className="text-sm text-muted">{entry.amends_id ? t`Corrects record ${entry.amends_id}` : t`Original record`}</p>
        {onAmend && permits(entry, "amend") ? <button className="desk-button min-h-11" type="button" onClick={() => onAmend(entry)}>{t`Correct recording error`}</button> : null}
      </article>;
    })}
  </section>;
}
