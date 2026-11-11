import { t } from "@lingui/core/macro";

import { DetailLayout } from "../../components/layouts";
import { KeyValueCard, StatusPill } from "../../components/ui";
import { formatDateTime } from "../../lib/format";
import { RouteLink } from "../../components/ui/RouteLink";
import { useCrossLink } from "../staff/crossLinks/staffHref";
import {
  AREA_LABELS, incidentErrorMessage, KIND_LABELS, SEVERITY_LABELS, severityTone, STATUS_LABELS, statusTone, useIncident,
  useIncidentChange, type Incident,
} from "./api";
import { IncidentFollowUps } from "./IncidentFollowUps";
import { IncidentTriage } from "./IncidentTriage";

const LINKS: [keyof Incident, string][] = [
  ["machine", t`Machine`], ["room", t`Room`], ["event", t`Event`], ["loan", t`Loan`], ["booking", t`Booking`],
  ["repair_issue", t`Repair job`], ["guest_pass", t`Guest pass`],
];

type LinkTarget = (tab: string, query?: Record<string, string | number | null | undefined>) => string | undefined;

/** Where each linked record opens in the console (MC12); undefined when the viewer cannot open that area. */
function subjectHref(incident: Incident, key: keyof Incident, link: LinkTarget) {
  const id = incident[key] as number;
  switch (key) {
    case "machine": return link("machines", { machine: id });
    case "event": return link("events", { event: id });
    case "room": return link("bookings", { space: id });
    // A booking opens inside its room's agenda; without the room the Bookings console is the best landing.
    case "booking": return link("bookings", incident.room ? { space: incident.room, booking: id, bookingTab: "requests" } : {});
    case "loan": return link("requests", { id });
    case "repair_issue": return link("repairs", { issue: id });
    case "guest_pass": return link("members", { section: "guests" });
    default: return undefined;
  }
}

/** The involved member opens their member 360 in Members, for those who manage people. */
function personLink(incident: Incident, link: LinkTarget) {
  const href = incident.involved_user ? link("members", { member: incident.involved_user }) : undefined;
  return href ? <RouteLink className="font-semibold underline" href={href}>{incident.involved_name}</RouteLink> : incident.involved_name;
}

/** One incident: the report, its links, triage and the follow-up actions. */
export function IncidentDetail({ id, onBack }: { id: number; onBack: () => void }) {
  const query = useIncident(id);
  const change = useIncidentChange(id);
  const incident = query.data;
  const link = useCrossLink();
  return <DetailLayout title={incident?.title ?? t`Incident`} back={{ label: t`All incidents`, onClick: onBack }}
    identity={{ kind: "icon", icon: incident?.kind === "near_miss" ? "ShieldAlert" : "TriangleAlert",
      tone: incident ? severityTone(incident.severity) : "neutral" }}
    state={query.isLoading ? { status: "loading" } : query.error
      ? { status: "error", error: incidentErrorMessage(query.error), onRetry: () => { void query.refetch(); } } : { status: "ready" }}
    status={incident ? <>
      <StatusPill tone={statusTone(incident.status)} label={STATUS_LABELS[incident.status]} />
      <StatusPill tone={severityTone(incident.severity)} label={SEVERITY_LABELS[incident.severity]} />
    </> : undefined}
    meta={incident ? [KIND_LABELS[incident.kind], AREA_LABELS[incident.area],
      incident.reporter_name ? t`Reported by ${incident.reporter_name}` : t`Reporter unknown`] : undefined}
    main={incident ? <div className="grid min-w-0 gap-6">
      <section aria-label={t`Report`} className="grid gap-2">
        <p className="whitespace-pre-wrap break-words">{incident.description || t`No details given.`}</p>
      </section>
      <KeyValueCard title={t`Record`} items={[
        { label: t`Happened`, value: formatDateTime(incident.occurred_at) },
        ...(incident.location ? [{ label: t`Where`, value: incident.location }] : []),
        ...(incident.involved_name ? [{ label: t`Person involved`, value: personLink(incident, link) }] : []),
        ...(incident.involved_note && incident.involved_note !== incident.involved_name ? [{ label: t`Involvement note`, value: incident.involved_note }] : []),
        ...LINKS.filter(([key]) => incident[key] != null).map(([key, label]) => {
          const href = subjectHref(incident, key, link);
          const text = t`${label} #${String(incident[key])}`;
          return { label, value: href ? <RouteLink className="font-semibold underline" href={href}>{text}</RouteLink> : `#${String(incident[key])}` };
        }),
        { label: t`Recorded`, value: formatDateTime(incident.created_at) },
        ...(incident.closed_at ? [{ label: t`Closed`, value: formatDateTime(incident.closed_at) }] : []),
      ]} />
      <IncidentTriage key={incident.updated_at} incident={incident} mutation={change.triage} />
      <IncidentFollowUps incidentId={incident.id} actions={incident.actions} add={change.addAction} toggle={change.toggleAction} />
    </div> : null} />;
}
