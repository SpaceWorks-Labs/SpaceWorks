import { t } from "@lingui/core/macro";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useContext, useEffect, useRef, useState } from "react";
import { staffRequest } from "../../lib/api";
import { PendingIntake, submitContextualStaff, type StaffBody } from "../inventory/contextualIntake";
import { KitChoice } from "../inventory/KitChoice";
import type { SafeKit } from "../inventory/equipmentKitsApi";
import { StaffListContext } from "./StaffListContext";
import { useIntakeScope } from "../inventory/useIntakeScope";
import { getSessionOwner } from "../../lib/api/sessionTokens";
import { Choices, Participants } from "./loanContext/Choices";
import { capabilityOn } from "../../lib/features";
import { formatDate } from "../../lib/format";
import { refusalCode, eligibilityMessage } from "../../lib/eligibilityCopy";
import { EventsOnlyBadge } from "./eventEquipment/EventsOnlyBadge";
import { PagePager } from "../../components/ui";
import { LogoLoader } from "../../components/LogoLoader";
import { BoxArt } from "../../components/BoxSpinner";

type Page = { results: { id: number; name: string; image_url?: string | null; available_quantity?: number; next_due_back_at?: string | null; event_only?: boolean }[]; next: string | null; previous: string | null };
// Shown only when the server includes the availability owner's stored count (inventory-view staff).
function availabilityText(row: Page["results"][number]) {
  if (row.available_quantity === undefined) return "";
  const count = row.available_quantity;
  if (!row.next_due_back_at) return t`${count} available now`;
  const back = formatDate(row.next_due_back_at);
  return t`${count} available now, next back ${back}`;
}
type Availability = { events: boolean; bookings: boolean; loans: boolean; consumables: boolean };
function eligibleKit(kit: SafeKit, flags: Availability) { return kit.lines.length > 0 && kit.lines.every(line => line.kind === "returnable" ? flags.loans : flags.consumables); }
export function StaffEquipmentProposal(props: { tenant: number; domain: "event" | "booking"; resourceId: number; targetId: number; pendingOwner: PendingIntake<StaffBody> }) {
  const staff = useContext(StaffListContext); const actor = staff.actorId; const session = useIntakeScope();
  const place = staff.makerspace;
  const availability = { events: place?.id === props.tenant && !!place.enabled_modules?.includes("events"), bookings: place?.id === props.tenant && !!place.enabled_modules?.includes("bookings"), loans: place?.id === props.tenant && capabilityOn(place, "loans.enabled"), consumables: place?.id === props.tenant && capabilityOn(place, "inventory.consumables") };
  const scope = JSON.stringify([session.context, session.owner, actor ?? null, props.tenant, props.domain, props.resourceId, props.targetId]);
  if (!session.owner || !actor || session.owner !== String(actor) || !availability[props.domain === "event" ? "events" : "bookings"] || (!availability.loans && !availability.consumables)) return null;
  return <Proposal key={scope} {...props} availability={availability} scope={scope} actor={actor} context={session.context} />;
}
function Proposal({ tenant, domain, resourceId, targetId, scope, pendingOwner, actor, context, availability }: { tenant: number; domain: "event" | "booking"; resourceId: number; targetId: number; scope: string; pendingOwner: PendingIntake<StaffBody>; actor: number; context: ReturnType<typeof useIntakeScope>["context"]; availability: Availability }) {
  const client = useQueryClient();
  const [open, setOpen] = useState(false); const [page, setPage] = useState(1); const [selected, setSelected] = useState<number[]>([]); const [quantities, setQuantities] = useState<Record<number, number>>({});
  const [purpose, setPurpose] = useState(""); const [pending, setPending] = useState(false); const [uncertain, setUncertain] = useState(() => Boolean(pendingOwner.current(scope))); const [message, setMessage] = useState("");
  const [kit, setKit] = useState<SafeKit | null>(null);
  const currentKit = useRef(kit); currentKit.current = kit;
  const [addContext, setAddContext] = useState(false);
  const [otherTarget, setOtherTarget] = useState<number | null>(null);
  const [otherParticipant, setOtherParticipant] = useState<number | null>(null);
  const wasUncertain = useRef(uncertain);
  const currentAvailability = useRef(availability); currentAvailability.current = availability;
  const counterpartOn = domain === "event" ? availability.bookings : availability.events;
  const intent = pendingOwner;
  const held = intent.current(scope);
  const heldKitKnown = !!held?.kit && !!kit && held.kit.id === kit.id && held.kit.version === kit.version && eligibleKit(kit, availability);
  useEffect(() => {
    const sync = () => { const exists = Boolean(intent.current(scope)); setUncertain(exists); if (!exists) wasUncertain.current = false; };
    const unsubscribe = intent.subscribe(sync); sync(); return unsubscribe;
  }, [intent, scope]);
  useEffect(() => { if (!counterpartOn && !uncertain && !pending) { setAddContext(false); setOtherTarget(null); setOtherParticipant(null); } }, [counterpartOn, uncertain, pending]);
  const path = `/admin/makerspace/${tenant}/${domain === "event" ? "events" : "spaces"}/${resourceId}/equipment-request-products?page=${page}`;
  const products = useQuery({ queryKey: ["staff-equipment-products", scope, page], enabled: open && availability.loans, retry: false, queryFn: () => staffRequest<Page>(path) });
  async function send(body: Readonly<StaffBody>, unverifiedKit = false) {
    const flags = currentAvailability.current;
    const selectedKit = currentKit.current;
    const knownKit = !!body.kit && !!selectedKit && body.kit.id === selectedKit.id && body.kit.version === selectedKit.version && eligibleKit(selectedKit, flags);
    if ((!flags.events && body.event_registration_id) || (!flags.bookings && body.booking_id) || (!flags.loans && body.items) || (unverifiedKit && body.kit && (!flags.loans || !flags.consumables) && !knownKit) || (!flags.loans && !flags.consumables)) return;
    if (getSessionOwner(context) !== String(actor)) { setOpen(false); return; }
    setPending(true); setMessage("");
    try { const result = await submitContextualStaff(tenant, body); if (intent.complete(scope, body)) { wasUncertain.current = false; setUncertain(false); setMessage(result.kind === "request" ? t`Equipment request submitted for review.` : t`Consumable plan saved. No stock was used.`); } }
    catch (error) {
      const status = (error as { status?: number })?.status;
      if (status === 400 && !wasUncertain.current) {
        if (intent.complete(scope, body)) setMessage(t`Check your request and try again.`);
      } else if (refusalCode(error) === "event_only_product" && !wasUncertain.current) {
        // A definite refusal (221b: a booking is not an event), not an unknown outcome.
        if (intent.complete(scope, body)) setMessage(eligibilityMessage(error) ?? t`Check your request and try again.`);
      } else {
        wasUncertain.current = true; setUncertain(true);
        if ([401, 403, 404].includes(status ?? 0)) {
          setOpen(false); setSelected([]); setQuantities({}); setKit(null); setPurpose(""); setOtherTarget(null); setOtherParticipant(null); client.removeQueries({ queryKey: ["staff-equipment-products", scope] }); client.removeQueries({ queryKey: ["equipment-kits", scope] }); client.removeQueries({ queryKey: ["loan-context-choices", scope] }); client.removeQueries({ queryKey: ["loan-context-participants", scope] });
        }
        setMessage(t`The outcome may be unknown. Retry the same request or review request history.`);
      }
    }
    finally { setPending(false); }
  }
  function submit() { const flags = currentAvailability.current; const targetOn = domain === "event" ? flags.bookings : flags.events; if (getSessionOwner(context) !== String(actor)) { setOpen(false); return; } if ((addContext && !targetOn) || (!kit && !flags.loans) || (kit && !eligibleKit(kit, flags))) return; const selection = kit ? { kit: { id: kit.id, version: kit.version } } : { items: selected.map(product_id => ({ product_id, quantity: quantities[product_id] ?? 1 })) }; const body = intent.begin(scope, { operation_id: crypto.randomUUID(), event_registration_id: domain === "event" ? targetId : otherParticipant, booking_id: domain === "booking" ? targetId : otherTarget, ...selection, requested_for: purpose.trim() }); void send(body); }
  return <section className="grid gap-2" data-replay-block>
    {!open ? <button className="desk-button" type="button" onClick={() => setOpen(true)}>{t`Propose equipment`}</button> : <>
      <p className="text-sm text-muted">{t`Choose public requestable equipment for this person. Inventory staff review and issue it separately.`}</p>
      {counterpartOn ? <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={addContext} disabled={pending || uncertain} onChange={event => { setAddContext(event.target.checked); setOtherTarget(null); setOtherParticipant(null); }} /> {domain === "event" ? t`Also link a booking` : t`Also link an event`}</label> : null}
      {counterpartOn && addContext && !pending && !uncertain ? <div className="grid gap-2"><Choices tenant={tenant} scope={scope} domain={domain === "event" ? "booking" : "event"} onSelect={id => { setOtherTarget(id); setOtherParticipant(null); }} />{domain === "booking" && otherTarget ? <Participants key={otherTarget} eventId={otherTarget} scope={scope} value={otherParticipant} onChange={setOtherParticipant} /> : null}</div> : null}
      <KitChoice scope={scope} staff={{ tenant, domain, resource: resourceId }} value={kit} onChange={setKit} disabled={pending || uncertain} consumableOnly={!availability.loans} />
      {!availability.loans ? null : products.isPending ? <LogoLoader label={t`Loading equipment…`} size={48} className="min-h-16 py-3" /> : products.isError ? <p className="text-sm text-danger" role="alert">{t`Equipment is unavailable for your access.`}</p> : <>
        {!products.data.results.length ? <p className="text-sm text-muted">{t`No requestable equipment is listed for this person here.`}</p> : null}
        <ul className="grid gap-1" aria-label={t`Equipment`}>{products.data.results.map(row => <li key={row.id} className="flex flex-wrap items-center gap-2"><label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" disabled={pending || uncertain} checked={selected.includes(row.id)} onChange={event => setSelected(ids => event.target.checked ? [...ids, row.id] : ids.filter(id => id !== row.id))} /> {row.name}</label>{row.event_only ? <EventsOnlyBadge /> : null}{availabilityText(row) ? <span className="text-sm text-muted">{availabilityText(row)}</span> : null}{selected.includes(row.id) ? <label className="flex items-center gap-1 text-sm">{t`Quantity`}<input className="desk-input w-20" type="number" min={1} max={99} disabled={pending || uncertain} value={quantities[row.id] ?? 1} onChange={event => { const value = Math.min(99, Math.max(1, Math.trunc(Number(event.target.value) || 1))); setQuantities(previous => ({ ...previous, [row.id]: value })); }} /></label> : null}</li>)}</ul>
        <PagePager page={page} setPage={setPage} next={products.data.next} disabled={pending || uncertain} />
      </>}
      <label className="grid gap-1 text-sm">{t`Purpose`}<input className="desk-input" value={purpose} disabled={pending || uncertain} onChange={event => setPurpose(event.target.value)} /></label>
      {uncertain ? <button type="button" className="desk-button" disabled={pending || !held || (!availability.events && !!held.event_registration_id) || (!availability.bookings && !!held.booking_id) || (!availability.loans && !!held.items) || (!!held.kit && (!availability.loans || !availability.consumables) && !heldKitKnown)} onClick={() => { const body = intent.current(scope); if (body) void send(body, true); }}>{t`Retry the same request`}</button> : <button type="button" className="desk-button" disabled={pending || (addContext && (!counterpartOn || !otherTarget || (domain === "booking" && !otherParticipant))) || !purpose.trim() || (!kit && (!availability.loans || !selected.length || selected.length > 20)) || !!kit && kit.lines.some(line => line.kind === "returnable" ? !availability.loans : !availability.consumables)} onClick={submit}>{pending ? <><BoxArt size={16} mono />{t`Submitting…`}</> : t`Submit for review`}</button>}
    </>}
    {message ? <p className="text-sm" role="status">{message}</p> : null}
  </section>;
}
