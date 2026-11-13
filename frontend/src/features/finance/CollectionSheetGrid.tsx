import { t } from "@lingui/core/macro";
import { Trash2 } from "lucide-react";

import { StatusPill } from "../../components/ui";
import { SETTLEMENT_METHODS, settlementMethodLabel } from "../staff/paymentsApi";
import { rowFailureText } from "./collectionApi";
import type { SheetRow } from "./collectionSheetRows";

const cell = "p-1.5 align-top";
const input = "desk-input w-full min-w-0";

function RowStatus({ row, problem }: { row: SheetRow; problem: string | null }) {
  const result = row.result;
  if (result?.outcome === "recorded") return <StatusPill tone="success" label={t`Recorded`} />;
  if (result?.outcome === "awaiting_confirmation") return <StatusPill tone="warn" label={t`Waiting for a second person`} />;
  if (result?.outcome === "failed") return <span className="grid gap-1"><StatusPill tone="danger" label={t`Not recorded`} />
    <span className="text-xs text-danger">{rowFailureText(result.code, result.detail)}</span></span>;
  if (problem) return <span className="text-xs text-danger">{problem}</span>;
  return <span className="text-xs text-muted">{t`Ready`}</span>;
}

/** The editable table. A row the server already took is locked so it cannot be sent twice. */
export function CollectionSheetGrid({ rows, problems, today, disabled, onChange, onRemove }: {
  rows: SheetRow[]; problems: (string | null)[]; today: string; disabled: boolean;
  onChange: (key: number, patch: Partial<SheetRow>) => void; onRemove: (key: number) => void;
}) {
  return <div role="region" aria-label={t`Collection sheet rows`} tabIndex={0}
    className="overflow-x-auto rounded-xl border border-line bg-panel focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
    <table className="w-full min-w-[46rem] text-sm">
      <caption className="sr-only">{t`Payments on this collection sheet`}</caption>
      <thead><tr className="border-b border-line text-left text-xs text-muted">
        <th scope="col" className="w-10 p-2 text-right">#</th>
        <th scope="col" className="w-32 p-2">{t`Charge number`}</th>
        <th scope="col" className="w-40 p-2">{t`Method`}</th>
        <th scope="col" className="p-2">{t`Reference`}</th>
        <th scope="col" className="w-40 p-2">{t`Received on`}</th>
        <th scope="col" className="w-56 p-2">{t`Status`}</th>
        <th scope="col" className="w-12 p-2"><span className="sr-only">{t`Remove`}</span></th>
      </tr></thead>
      <tbody>{rows.map((row, index) => {
        const locked = disabled || (row.result !== undefined && row.result.outcome !== "failed");
        const problem = row.result ? null : problems[index];
        const line = index + 1;
        return <tr key={row.key} className="border-t border-line">
          <td className={`${cell} pt-3 text-right tabular-nums text-muted`}>{line}</td>
          <td className={cell}><input className={`${input} tabular-nums`} inputMode="numeric" value={row.payment} disabled={locked}
            aria-label={t`Charge number, row ${line}`} aria-invalid={Boolean(problem) || undefined}
            onChange={(event) => onChange(row.key, { payment: event.target.value })} /></td>
          <td className={cell}><select className={input} value={row.method} disabled={locked} aria-label={t`Method, row ${line}`}
            onChange={(event) => onChange(row.key, { method: event.target.value })}>
            {SETTLEMENT_METHODS.some(([code]) => code === row.method) ? null : <option value={row.method}>{row.method || t`Choose`}</option>}
            {SETTLEMENT_METHODS.map(([code]) => <option key={code} value={code}>{settlementMethodLabel(code)}</option>)}
          </select></td>
          <td className={cell}><input className={input} maxLength={64} value={row.reference} disabled={locked}
            aria-label={t`Reference, row ${line}`} placeholder={t`Receipt book no., UTR…`}
            onChange={(event) => onChange(row.key, { reference: event.target.value })} /></td>
          <td className={cell}><input className={input} type="date" max={today} value={row.date} disabled={locked}
            aria-label={t`Received on, row ${line}`} onChange={(event) => onChange(row.key, { date: event.target.value })} /></td>
          <td className={`${cell} pt-2.5`} aria-live="polite"><RowStatus row={row} problem={problem} /></td>
          <td className={cell}><button type="button" className="desk-button-ghost min-h-11 min-w-11 justify-center" disabled={disabled}
            aria-label={t`Remove row ${line}`} onClick={() => onRemove(row.key)}><Trash2 aria-hidden="true" size={16} /></button></td>
        </tr>;
      })}</tbody>
    </table>
  </div>;
}
