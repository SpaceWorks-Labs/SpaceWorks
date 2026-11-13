import { t } from "@lingui/core/macro";
import { useContext, type ReactNode } from "react";

import { ListRow, StatusPill } from "../../../components/ui";
import { formatDate } from "../../../lib/format";
import { openLinks, RelatedLinks } from "../crossLinks/RelatedLinks";
import { useCrossLink } from "../crossLinks/staffHref";
import { useSubjectIncidents } from "../crossLinks/subjectIncidents";
import { opsStatusLabel } from "../opsPresentation";
import { StaffListContext } from "../StaffListContext";
import { useEventGuestPasses, useEventLoans } from "./eventLinksApi";

/**
 * EB9-EB11: an event's incidents, loans and guest passes from inside the event. Loans and passes
 * are read-only here (decision 242(g)); the equipment desk stays the place to issue and return,
 * so the loan list is shown only to someone who does not already see that desk.
 */
export function EventCrossLinks({ makerspaceId, eventId }: { makerspaceId: number; eventId: number }) {
  const link = useCrossLink();
  const { actions, isSuperadmin, makerspace } = useContext(StaffListContext);
  const modules = makerspace?.enabled_modules ?? [];
  const hasDesk = Boolean(isSuperadmin || actions?.includes("issue_request"));
  const incidents = useSubjectIncidents(makerspaceId, "event", eventId);
  const loans = useEventLoans(eventId, !hasDesk && modules.includes("request_workflow"));
  const passes = useEventGuestPasses(eventId, (makerspace?.enabled_features ?? []).includes("membership.guest_passes"));
  const links = openLinks([
    ...(!incidents.hidden ? [{ key: "incidents", label: t`Incidents`, helper: t`Reported at this event`, count: incidents.count, href: link("incidents", { event: eventId }) }] : []),
  ]);
  const showLoans = !hasDesk && !loans.hidden && loans.query.isFetched;
  const showPasses = !passes.hidden && passes.query.isFetched;
  if (!links.length && !showLoans && !showPasses) return null;
  return <div className="grid min-w-0 gap-6">
    {links.length ? <RelatedLinks links={links} /> : null}
    {showLoans ? <ReadOnlyList title={t`Equipment on loan for this event`} error={loans.query.isError} onRetry={() => { void loans.query.refetch(); }}
      empty={t`No equipment is lent for this event.`} count={loans.count}>
      {loans.rows.map(row => <ListRow key={row.request_id} title={row.items.map(item => `${item.product_name} ×${item.issued || item.requested}`).join(", ") || t`Loan #${row.request_id}`}
        meta={[row.holder, row.due_at ? t`Due ${formatDate(row.due_at)}` : ""].filter(Boolean).join(" · ")}
        right={<StatusPill tone={["issued", "partially_returned"].includes(row.status) ? "accent" : "neutral"} label={opsStatusLabel(row.status)} />} />)}
    </ReadOnlyList> : null}
    {showPasses ? <ReadOnlyList title={t`Guest passes for this event`} error={passes.query.isError} onRetry={() => { void passes.query.refetch(); }}
      empty={t`No guest passes were issued for this event.`} count={passes.count}>
      {passes.rows.map(row => <ListRow key={row.id} title={row.holder || t`Guest`}
        meta={row.valid_until ? t`Until ${formatDate(row.valid_until)}` : undefined}
        right={<StatusPill tone={row.status === "active" ? "success" : "neutral"} label={opsStatusLabel(row.status)} />} />)}
    </ReadOnlyList> : null}
  </div>;
}

function ReadOnlyList({ title, count, empty, error, onRetry, children }: {
  title: string; count: number; empty: string; error: boolean; onRetry: () => void; children: ReactNode;
}) {
  return <section className="grid min-w-0 gap-2" aria-label={title}>
    <h3 className="title-section">{title} <span className="tabular-nums text-muted">({count})</span></h3>
    {error ? <div role="alert" className="flex flex-wrap items-center gap-3 text-sm text-danger"><p>{t`Couldn't load this list.`}</p>
      <button type="button" className="desk-button" onClick={onRetry}>{t`Retry`}</button></div>
      : count ? <div className="grid gap-2">{children}</div> : <p className="text-sm text-muted">{empty}</p>}
  </section>;
}
