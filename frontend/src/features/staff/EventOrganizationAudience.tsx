import type { StaffEvent } from "./eventsApi";

export function EventOrganizationAudience({ event, pending = false, onReconfigure }: {
  event: Pick<StaffEvent, "registration_audience" | "participating_organizations" | "organization_admission_blocked">;
  pending?: boolean; onReconfigure?: () => void;
}) {
  if (event.registration_audience !== "participating_organizations") return null;
  const names = event.participating_organizations?.map((row) => row.name) ?? [];
  return <section className="rounded-lg border border-line bg-surface p-3">
    <h3 className="title-section">Participating organizations</h3>
    <p className="mt-1 text-sm">{names.length ? names.join(", ") : "No usable participating organizations."}</p>
    <p className="mt-1 text-sm text-muted">The event organizers and venue owner determine this audience. Active organization members and members of their owned makerspaces qualify. Manager and affiliate links do not qualify.</p>
    {event.organization_admission_blocked ? <>
      <p className="mt-2 text-sm text-warn" role="status">This imported audience is blocked until staff review the local organizations and ownership.</p>
      {onReconfigure ? <button type="button" className="desk-button mt-2" disabled={pending} onClick={onReconfigure}>Confirm local audience</button> : null}
    </> : null}
  </section>;
}
