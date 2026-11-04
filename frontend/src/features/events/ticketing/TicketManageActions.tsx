import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Card, ErrorText, Field } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { useTenantPath } from "../../../lib/tenant";
import { fetchShop, money, ticketingKeys } from "./ticketingApi";
import { changeTicketType, safeCheckoutUrl, transferTicket } from "./ticketingMemberApi";

type Props = {
  makerspaceId: number; makerspaceSlug: string; registrationId: number; status: string;
  event: { public_token: string; starts_at: string }; currentTicketTypeId?: number | null;
};

function errorMessage(error: unknown) {
  if (error instanceof StructuredApiError) return error.detail ?? error.message;
  return error instanceof Error ? error.message : "Something went wrong. Try again.";
}

/** Release 2 L6 (G32, X39): pass my ticket to someone else, or switch to another ticket type.
 * Only for a confirmed place at an event that has not started; the server decides the money. */
export function TicketManageActions({ makerspaceId, makerspaceSlug, registrationId, status, event, currentTicketTypeId }: Props) {
  const confirmed = status === "registered" || status === "attended";
  const upcoming = Date.parse(event.starts_at) > Date.now();
  if (!confirmed || !upcoming || !makerspaceId) return null;
  return <div className="grid gap-4">
    <TransferCard makerspaceId={makerspaceId} registrationId={registrationId} />
    <ChangeTypeCard makerspaceId={makerspaceId} makerspaceSlug={makerspaceSlug} registrationId={registrationId}
      publicToken={event.public_token} currentTicketTypeId={currentTicketTypeId ?? null} />
  </div>;
}

function TransferCard({ makerspaceId, registrationId }: { makerspaceId: number; registrationId: number }) {
  const [email, setEmail] = useState("");
  const transfer = useMutation({ mutationFn: () => transferTicket(makerspaceId, registrationId, email.trim()) });
  return <Card><form className="grid gap-3" onSubmit={e => { e.preventDefault(); transfer.mutate(); }}>
    <h2 className="title-section">Transfer this ticket</h2>
    <p className="text-sm text-muted">We email the person a link. Your place becomes theirs only when they accept it while signed in
      with that address. The offer expires if they do not accept in time.</p>
    <Field label="Their email address"><input className="desk-input" type="email" required value={email}
      onChange={e => setEmail(e.target.value)} autoComplete="email" /></Field>
    {transfer.error ? <ErrorText message={errorMessage(transfer.error)} /> : null}
    {transfer.data ? <p role="status" className="text-sm text-ink">Offer sent. It expires {new Date(transfer.data.expires_at).toLocaleString()}.</p> : null}
    <button type="submit" className="desk-button justify-self-start" disabled={transfer.isPending || !email.trim()}>
      {transfer.isPending ? "Sending…" : "Send the transfer offer"}</button>
  </form></Card>;
}

function ChangeTypeCard({ makerspaceId, makerspaceSlug, registrationId, publicToken, currentTicketTypeId }: {
  makerspaceId: number; makerspaceSlug: string; registrationId: number; publicToken: string; currentTicketTypeId: number | null;
}) {
  const client = useQueryClient();
  const tenantPath = useTenantPath(makerspaceSlug);
  const shop = useQuery({ queryKey: ticketingKeys.shop(makerspaceSlug, publicToken), retry: false,
    enabled: Boolean(makerspaceSlug && publicToken), queryFn: () => fetchShop(makerspaceSlug, publicToken) });
  const [choice, setChoice] = useState(0);
  const change = useMutation({ mutationFn: () => changeTicketType(makerspaceId, registrationId, choice),
    onSuccess: result => { if (result.status === "changed") void client.invalidateQueries({ queryKey: ["event-ticket"] }); } });
  const options = (shop.data?.ticket_types ?? []).filter(row => !row.sold_out && row.id !== currentTicketTypeId);
  if (shop.isLoading) return null;
  if (shop.error || !shop.data?.orders_enabled || !options.length) return null;
  const result = change.data;
  const checkout = safeCheckoutUrl(result?.checkout_url);
  return <Card><form className="grid gap-3" onSubmit={e => { e.preventDefault(); change.mutate(); }}>
    <h2 className="title-section">Change ticket type</h2>
    <p className="text-sm text-muted">A dearer ticket asks you to pay the difference; a cheaper one gives the difference back
      under the event's refund policy.</p>
    <Field label="New ticket type"><select className="desk-input" value={choice} required onChange={e => setChoice(Number(e.target.value))}>
      <option value={0} disabled>Choose a ticket type</option>
      {options.map(row => <option key={row.id} value={row.id}>{row.name} · {money(row.amount, shop.data!.currency)}</option>)}
    </select></Field>
    {change.error ? <ErrorText message={errorMessage(change.error)} /> : null}
    {result?.status === "changed" ? <p role="status" className="text-sm text-ink">Your ticket type is changed.</p> : null}
    {result?.status === "payment_required" ? <div role="status" className="grid gap-2 text-sm text-ink">
      <p>Pay the difference to finish the change.</p>
      <div className="flex flex-wrap gap-2">
        {checkout ? <a className="desk-button" href={checkout}>Pay the difference</a> : null}
        {result.order ? <a className="desk-button" href={tenantPath(`member/orders/${result.order.id}`)}>View the order</a> : null}
      </div>
    </div> : null}
    <button type="submit" className="desk-button justify-self-start" disabled={change.isPending || !choice}>
      {change.isPending ? "Changing…" : "Change my ticket"}</button>
  </form></Card>;
}
