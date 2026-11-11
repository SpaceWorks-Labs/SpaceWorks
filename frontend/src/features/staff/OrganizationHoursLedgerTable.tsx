import { t } from "@lingui/core/macro";

import { formatDateTime } from "../../lib/format";
import { hoursText } from "../payments/IncludedHoursLine";
import type { OrganizationHoursLedgerRow } from "./organizationHoursApi";

const entryLabel = (entry: OrganizationHoursLedgerRow["entry"]) => ({
  grant: t`Granted`, consume: t`Used by a booking`, release: t`Returned from a booking`, adjust: t`Adjusted`,
})[entry];

export const minutesToHours = (minutes: number) => hoursText(minutes / 60);

/** Open item B13: one page of an organization's append-only hours ledger (newest first). */
export function OrganizationHoursLedgerTable({ rows, showActor }: { rows: OrganizationHoursLedgerRow[]; showActor: boolean }) {
  if (!rows.length) return <p className="text-sm text-muted">{t`No hours have been granted or used yet.`}</p>;
  return <div className="overflow-x-auto"><table className="w-full text-left text-sm">
    <caption className="sr-only">{t`Hours ledger`}</caption>
    <thead><tr className="text-muted">
      <th scope="col" className="py-1 pr-3 font-medium">{t`When`}</th>
      <th scope="col" className="py-1 pr-3 font-medium">{t`What`}</th>
      <th scope="col" className="py-1 pr-3 text-right font-medium">{t`Hours`}</th>
      <th scope="col" className="py-1 pr-3 font-medium">{t`Note`}</th>
    </tr></thead>
    <tbody>{rows.map(row => {
      const hours = minutesToHours(Math.abs(row.minutes));
      const sign = row.minutes < 0 ? "−" : "+";
      return <tr key={row.id} className="border-t border-line">
        <td className="py-1 pr-3 whitespace-nowrap">{formatDateTime(row.created_at)}</td>
        <td className="py-1 pr-3">{entryLabel(row.entry)}{row.booking_id ? t` (booking ${row.booking_id})` : ""}</td>
        <td className="py-1 pr-3 text-right tabular-nums">{sign}{hours}</td>
        <td className="py-1 pr-3">{row.reason}{showActor && row.actor_name ? <span className="text-muted">{` · ${row.actor_name}`}</span> : null}</td>
      </tr>;
    })}</tbody>
  </table></div>;
}
