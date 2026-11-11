import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Card, Skeleton } from "../../../components/ui";
import { eventErrorText } from "../eventUi";
import { useProgrammeQuery, type Live } from "./api";

export function EventDayPanel({ eventId }: { eventId: number }) {
  const [enabled, setEnabled] = useState(false);
  const query = useProgrammeQuery<Live>(eventId, "live", enabled);
  const row = query.data;
  return <section className="grid gap-4" aria-label={t`Event day`}><div className="flex flex-wrap items-center justify-between gap-3"><h3 className="title-section">{t`At the door`}</h3><label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />{t`Event-day mode · refresh every 15 seconds`}</label></div>
    {query.isLoading ? <Skeleton className="h-32 w-full" /> : null}{query.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(query.error)}</p> : null}
    {row ? <Card><div className="grid gap-4"><p className="text-sm text-muted">{row.active ? row.seconds_until_doors > 0 ? t`Doors open in ${Math.ceil(row.seconds_until_doors / 60)} minutes.` : t`Doors are open.` : t`Arrivals open from ${new Date(row.available_from).toLocaleString(formatLocale())}.`}</p>
      <label className="grid gap-2 text-sm font-semibold">{t`${row.checked_in} checked in of ${row.going} going`}<meter aria-label={t`Checked in of going`} min={0} max={Math.max(1, row.going)} value={Math.min(row.going, row.checked_in)} className="h-4 w-full accent-brand" /></label>
      {row.first_run ? <p className="rounded-xl border border-line bg-surface p-3 text-sm">{t`No arrivals yet. Open the check-in desk when your team is ready.`}</p> : null}
      <div className="overflow-x-auto"><table className="w-full text-left text-sm"><caption className="mb-2 text-left font-semibold">{t`Arrivals per 15 minutes`}</caption><thead><tr><th scope="col" className="p-2">{t`From`}</th><th scope="col" className="p-2">{t`Arrivals`}</th></tr></thead><tbody>{row.arrivals.map(item => <tr key={item.starts_at}><th scope="row" className="p-2 font-normal">{new Date(item.starts_at).toLocaleTimeString(formatLocale(), { hour: "2-digit", minute: "2-digit" })}</th><td className="p-2 tabular-nums">{item.count}</td></tr>)}</tbody></table></div>
    </div></Card> : null}
  </section>;
}
