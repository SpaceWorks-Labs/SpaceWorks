import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { financeError } from "../../finance/financeApi";
import { useEvents } from "../eventsApi";
import { PAYMENT_STATUS, sponsorApi, sponsorKeys, type ChargeInput } from "./staffSponsorsApi";

/** Hack-money G8: the body for "record as owed"; a prize-pool earmark always names its event. */
export function chargeBody(amount: string, description: string, eventId: string, prizePool: boolean): ChargeInput {
  const event_id = eventId ? Number(eventId) : null;
  return { amount, description, event_id, earmark: event_id && prizePool ? "prize_pool" : "general" };
}

/** What the sponsor agreed to pay: each is an account-less charge, settled offline or by a pay link. */
export function SponsorCharges({ makerspaceId, sponsorId, canRecord }: { makerspaceId: number; sponsorId: number; canRecord: boolean }) {
  const client = useQueryClient();
  const key = sponsorKeys.charges(makerspaceId, sponsorId);
  const charges = useQuery({ queryKey: key, queryFn: () => sponsorApi.charges(makerspaceId, sponsorId) });
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [eventId, setEventId] = useState("");
  const [prizePool, setPrizePool] = useState(false);
  const events = useEvents(makerspaceId);
  const titles = new Map((events.data?.results ?? []).map(row => [row.id, row.title]));
  const raise = useMutation({ mutationFn: () => sponsorApi.raiseCharge(makerspaceId, sponsorId, chargeBody(amount, description, eventId, prizePool)),
    onSuccess: () => { setAmount(""); setDescription(""); setEventId(""); setPrizePool(false); void client.invalidateQueries({ queryKey: key }); } });
  const back = useMutation({ mutationFn: (charge: number) => sponsorApi.returnCharge(makerspaceId, charge),
    onSuccess: () => void client.invalidateQueries({ queryKey: key }) });
  return <section className="grid gap-3" aria-label="Sponsorship money">
    <h3 className="title-section">Sponsorship money</h3>
    <p className="text-sm text-muted">Settle these under Payments (cash, UPI, bank) or send a pay link. A return opens a refund
      case that staff decide.</p>
    {charges.data?.length ? <ul className="grid gap-2">{charges.data.map(charge => <li key={charge.id}
      className="flex flex-wrap items-center gap-3 text-sm">
      <span className="font-semibold tabular-nums text-ink">{charge.currency.toUpperCase()} {charge.amount}</span>
      <span className="text-muted">{charge.description}</span>
      {charge.event ? <span className="text-xs">{titles.get(charge.event) ?? `Event #${charge.event}`}{charge.earmark === "prize_pool"
        ? " · prize pool" : ""}</span> : null}
      <span className="ml-auto text-xs">{PAYMENT_STATUS[charge.payment_status] ?? charge.payment_status}</span>
      {canRecord && ["paid_online", "paid_offline"].includes(charge.payment_status) ? <button type="button"
        className="desk-button-ghost" disabled={back.isPending}
        onClick={() => { if (window.confirm("Open a refund case to return this payment?")) back.mutate(charge.id); }}>Return…</button> : null}
    </li>)}</ul> : <p className="text-sm text-muted">Nothing recorded yet.</p>}
    {canRecord ? <form className="flex flex-wrap items-end gap-2" onSubmit={event => { event.preventDefault(); raise.mutate(); }}>
      <label className="grid gap-1 text-sm font-semibold text-ink">Amount<input className="desk-input tabular-nums" inputMode="decimal"
        required pattern="[0-9]+(\.[0-9]{1,2})?" value={amount} onChange={event => setAmount(event.target.value)} /></label>
      <label className="grid flex-1 gap-1 text-sm font-semibold text-ink">For<input className="desk-input" maxLength={200}
        value={description} onChange={event => setDescription(event.target.value)} /></label>
      <label className="grid gap-1 text-sm font-semibold text-ink">Event (optional)<select className="desk-input" value={eventId}
        onChange={event => { setEventId(event.target.value); if (!event.target.value) setPrizePool(false); }}>
        <option value="">No particular event</option>
        {(events.data?.results ?? []).map(row => <option key={row.id} value={row.id}>{row.title}</option>)}
      </select></label>
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" disabled={!eventId} checked={prizePool}
        onChange={event => setPrizePool(event.target.checked)} />Earmark for this event&apos;s prize pool</label>
      <button type="submit" className="desk-button" disabled={raise.isPending}>Record as owed</button>
    </form> : null}
    {raise.error || back.error ? <p role="alert" className="text-sm text-danger">{financeError(raise.error || back.error)}</p> : null}
  </section>;
}

/** Events this sponsor backs: a link to the event's own sponsor row, never a copy of it. */
export function SponsorEventLinks({ makerspaceId, sponsorId, canRecord }: { makerspaceId: number; sponsorId: number; canRecord: boolean }) {
  const client = useQueryClient();
  const key = sponsorKeys.links(makerspaceId, sponsorId);
  const links = useQuery({ queryKey: key, queryFn: () => sponsorApi.links(makerspaceId, sponsorId) });
  const choices = useQuery({ queryKey: sponsorKeys.eventSponsors(makerspaceId), enabled: canRecord,
    queryFn: () => sponsorApi.eventSponsors(makerspaceId) });
  const open = (choices.data ?? []).filter(row => row.linked_sponsor_id === null && row.active);
  const [eventSponsor, setEventSponsor] = useState("");
  const link = useMutation({ mutationFn: () => sponsorApi.link(makerspaceId, sponsorId, Number(eventSponsor)),
    onSuccess: () => {
      setEventSponsor("");
      void client.invalidateQueries({ queryKey: key });
      void client.invalidateQueries({ queryKey: sponsorKeys.eventSponsors(makerspaceId) });
    } });
  const unlink = useMutation({ mutationFn: (row: number) => sponsorApi.unlink(makerspaceId, row),
    onSuccess: () => void client.invalidateQueries({ queryKey: key }) });
  return <section className="grid gap-3" aria-label="Linked events">
    <h3 className="title-section">Events</h3>
    {links.data?.length ? <ul className="grid gap-2">{links.data.map(row => <li key={row.id} className="flex items-center gap-3 text-sm">
      <span className="text-ink">{row.event_title}</span><span className="text-muted">as “{row.label}”</span>
      {canRecord ? <button type="button" className="desk-button-ghost ml-auto" disabled={unlink.isPending}
        onClick={() => unlink.mutate(row.id)}>Unlink</button> : null}</li>)}</ul>
      : <p className="text-sm text-muted">Not linked to an event. Add the sponsor on the event first, then link it here.</p>}
    {canRecord && open.length ? <form className="flex flex-wrap items-end gap-2" onSubmit={event => { event.preventDefault(); link.mutate(); }}>
      <label className="grid gap-1 text-sm font-semibold text-ink">Event sponsor<select className="desk-input" required
        value={eventSponsor} onChange={event => setEventSponsor(event.target.value)}>
        <option value="">Choose an event sponsor</option>
        {open.map(row => <option key={row.id} value={row.id}>{row.event_title}: {row.label}</option>)}
      </select></label>
      <button type="submit" className="desk-button" disabled={link.isPending || !eventSponsor}>Link</button>
    </form> : null}
    {link.error || unlink.error ? <p role="alert" className="text-sm text-danger">{financeError(link.error || unlink.error)}</p> : null}
  </section>;
}
