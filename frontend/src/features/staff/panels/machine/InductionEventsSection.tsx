import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { RouteLink } from "../../../../components/ui/RouteLink";
import { staffRequest } from "../../../../lib/api";
import { formatDateTime } from "../../../../lib/format";
import { useCrossLink } from "../../crossLinks/staffHref";

type Upcoming = { link_id: number; event_id: number; title: string; starts_at: string; certification_type: number;
  certification_type_name: string; machine_type_id: number };

/**
 * Decision 259 (MC4): the upcoming induction events for this machine type, so a Machine Manager sees them
 * without the Events tab. The event page itself opens only for staff who may open Events; others see the list.
 * The route answers 404 while induction events are off, so the section then renders nothing.
 */
export function InductionEventsSection({ makerspaceId, machineTypeId }: { makerspaceId: number; machineTypeId: number }) {
  const link = useCrossLink();
  const rows = useQuery({ queryKey: ["induction-events", makerspaceId, machineTypeId], retry: false,
    queryFn: () => staffRequest<Upcoming[]>(`/admin/makerspaces/${makerspaceId}/induction-events?machine_type=${machineTypeId}`) });
  if (!rows.data?.length) return null;
  return <section aria-label={t`Induction events`} className="grid gap-2 rounded-xl border border-line p-3">
    <h4 className="title-section">{t`Induction events`}</h4>
    <ul className="grid gap-1 text-sm">{rows.data.map(row => {
      const href = link("events", { event: row.event_id });
      const label = `${row.title} · ${formatDateTime(row.starts_at)} · ${row.certification_type_name}`;
      return <li key={row.link_id}>{href ? <RouteLink className="underline" href={href}>{label}</RouteLink> : label}</li>;
    })}</ul>
  </section>;
}
