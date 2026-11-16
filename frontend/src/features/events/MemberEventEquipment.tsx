import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { StatusBadge, StatusPill } from "../../components/ui";
import { requestStatusLabel } from "../../components/ui/StatusStepper";
import { RouteLink } from "../../components/ui/RouteLink";
import { memberRequest } from "../../lib/api";
import { formatLocale } from "../../lib/format";

type EventEquipment = {
  event_id: number; event_ends_at: string | null; can_request: boolean;
  requests: { public_token: string; status: string; created_at: string; return_due_at: string | null; overdue: boolean;
    items: { product_name: string; requested_quantity: number; accepted_quantity: number; issued_quantity: number; returned_quantity: number }[] }[];
};

const quantity = (item: EventEquipment["requests"][number]["items"][number], status: string) =>
  ["issued", "partially_returned", "returned", "closed_with_issue"].includes(status) ? item.issued_quantity
    : status === "accepted" ? item.accepted_quantity : item.requested_quantity;

/** The member route needs Events, the request workflow and `loans.enabled`; ask only when all three are on. */
export function memberEventEquipmentEnabled(space?: { modules?: readonly string[]; features?: readonly string[] } | null) {
  const modules = space?.modules ?? [];
  return modules.includes("events") && modules.includes("request_workflow") && (space?.features ?? []).includes("loans.enabled");
}

/** A registrant's own equipment for this event. Hidden when the space does not lend for events. */
export function MemberEventEquipment({ makerspaceId, registrationId, requestHref, historyHref }: {
  makerspaceId: number; registrationId: number; requestHref: string; historyHref: string;
}) {
  const equipment = useQuery({
    queryKey: ["member-event-equipment", makerspaceId, registrationId], retry: false, refetchOnWindowFocus: true,
    queryFn: ({ signal }) => memberRequest<EventEquipment>(`/member/makerspaces/${makerspaceId}/event-registrations/${registrationId}/equipment/`, { signal }),
  });
  // Off modules, someone else's registration and a disabled lending switch all answer 404.
  if (!Array.isArray(equipment.data?.requests) || (!equipment.data.requests.length && !equipment.data.can_request)) return null;
  const { requests, can_request: canRequest } = equipment.data;
  return <section className="grid gap-2" aria-labelledby={`event-equipment-${registrationId}`}>
    <h2 id={`event-equipment-${registrationId}`} className="title-section">{t`Your equipment for this event`}</h2>
    {requests.length ? <ul className="grid gap-2">{requests.map(row => <li key={row.public_token} className="grid gap-1 rounded-lg border border-line p-2">
      <span className="flex flex-wrap items-center gap-2"><StatusBadge status={row.status} label={requestStatusLabel(row.status)} />{row.overdue ? <StatusPill tone="danger" label={t`Overdue`} /> : null}</span>
      <span className="[overflow-wrap:anywhere]">{row.items.map(item => `${item.product_name} × ${quantity(item, row.status)}`).join(", ")}</span>
      {row.return_due_at && ["issued", "partially_returned"].includes(row.status)
        ? <span className="text-sm">{t`Return by ${new Date(row.return_due_at).toLocaleString(formatLocale())}`}</span> : null}
    </li>)}</ul> : <p className="text-sm">{t`Equipment can be borrowed for this event. Inventory staff review each request.`}</p>}
    <div className="flex flex-wrap gap-2">
      {canRequest ? <RouteLink className="desk-button" href={requestHref}>{t`Request equipment`}</RouteLink> : null}
      {requests.length ? <RouteLink className="desk-button" href={historyHref}>{t`Your borrowing history`}</RouteLink> : null}
    </div>
  </section>;
}
