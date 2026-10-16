import { Callout, Card } from "../../components/ui";
import type { StaffEvent } from "./eventsApi";

export function EventOrganizationAudience({ event, pending = false, onReconfigure }: {
  event: Pick<StaffEvent, "registration_audience" | "participating_organizations" | "organization_admission_blocked">;
  pending?: boolean; onReconfigure?: () => void;
}) {
  if (event.registration_audience !== "participating_organizations") return null;
  const names = event.participating_organizations?.map((row) => row.name) ?? [];
  return <Card>
    <section aria-labelledby="event-organization-audience" className="grid gap-3">
      <h2 id="event-organization-audience" className="title-panel">Participating organizations</h2>
      <p className="text-sm font-semibold text-ink">{names.length ? names.join(", ") : "No usable participating organizations."}</p>
      <p className="text-sm text-muted">The event organizers and venue owner determine this audience. Active organization members and members of their owned makerspaces qualify. Manager and affiliate links do not qualify.</p>
      {event.organization_admission_blocked ? <>
        <div role="status"><Callout size="inline" tone="warn" lead="Audience blocked."
          body="This imported audience is blocked until staff review the local organizations and ownership." /></div>
        {onReconfigure ? <button type="button" className="desk-button justify-self-start" disabled={pending} onClick={onReconfigure}>Confirm local audience</button> : null}
      </> : null}
    </section>
  </Card>;
}
