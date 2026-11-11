import { useContext } from "react";
import { StaffListContext } from "../StaffListContext";
import { DomainPanel } from "./DomainPanel";
import { useSessionScope } from "./scope";

/** A new identity or capability snapshot remounts the entire private editor synchronously. */
export function LoanContextPanel({ tenant, request, modules, unavailable }: {
  tenant: number; request: number; modules?: readonly string[]; unavailable?: readonly string[];
}) {
  const authority = useContext(StaffListContext);
  const session = useSessionScope();
  if (!Number.isSafeInteger(authority.actorId) || !authority.actorId || !Number.isSafeInteger(tenant)
      || !Number.isSafeInteger(request) || tenant < 1 || request < 1 || !modules || !authority.actions) return null;
  const flags = ["events", "bookings"].filter(key => modules.includes(key) && !(unavailable ?? []).includes(key));
  const scope = JSON.stringify([session.context, authority.actorId, session.generation, tenant, request,
    [...authority.actions].sort(), Boolean(authority.isSuperadmin), [...modules].sort(), [...(unavailable ?? [])].sort()]);
  return <div key={scope} className="grid gap-3">{flags.map(domain => <DomainPanel key={domain} tenant={tenant} request={request}
    domain={domain === "events" ? "event" : "booking"} scope={scope} />)}</div>;
}
