import { useState } from "react";
import { Card } from "../../../components/ui";
import { panelEmpty, panelField, panelInput, panelRow } from "../eventPanelStyles";
import { useEventAddons } from "./staffTicketingApi";

/** G30: kit, lunch, T-shirts with sizes, session seats -- event-local stock, never hardware inventory. */
export function EventAddonsEditor({ eventId, disabled = false }: { eventId: number; disabled?: boolean }) {
  const { rows, create, update, remove } = useEventAddons(eventId);
  const [name, setName] = useState("");
  const [amount, setAmount] = useState("0.00");
  const [kind, setKind] = useState("other");
  const [stock, setStock] = useState(0);
  const [sizes, setSizes] = useState("");
  const error = rows.error || create.error || update.error || remove.error;
  const submit = () => create.mutate({ name, amount, kind, stock,
    variants: sizes.split(",").map(label => label.trim()).filter(Boolean).map(label => ({ label, stock: 0 })) },
    { onSuccess: () => { setName(""); setSizes(""); } });
  return <section className="grid gap-3" aria-label="Ticket add-ons">
    <h3 className="title-section">Add-ons</h3>
    <Card><form className="grid gap-4" onSubmit={event => { event.preventDefault(); submit(); }}>
      <label className={panelField}>Name<input className={panelInput} required maxLength={100} value={name} disabled={disabled} onChange={event => setName(event.target.value)} /></label>
      <label className={panelField}>Kind<select className={panelInput} value={kind} disabled={disabled} onChange={event => setKind(event.target.value)}>
        <option value="kit">Kit</option><option value="meal">Meal</option><option value="merch">Merchandise</option>
        <option value="session">Session seat</option><option value="other">Other</option></select></label>
      <label className={panelField}>Price<input className={panelInput} type="number" min="0" step="0.01" value={amount} disabled={disabled} onChange={event => setAmount(event.target.value)} /></label>
      <label className={panelField}>Stock (0 = unlimited)<input className={panelInput} type="number" min="0" value={stock} disabled={disabled} onChange={event => setStock(Number(event.target.value))} /></label>
      <label className={panelField}>Sizes or options, comma separated (optional)<input className={panelInput} value={sizes} disabled={disabled} onChange={event => setSizes(event.target.value)} /></label>
      <button className="desk-button-primary justify-self-start" type="submit" disabled={disabled || create.isPending}>Add add-on</button>
    </form></Card>
    {error ? <p role="alert" className="text-sm text-danger">{error.message}</p> : null}
    {rows.data?.results.length === 0 ? <p className={panelEmpty}>No add-ons yet.</p> : null}
    <ul className="grid gap-3">{rows.data?.results.map(addon => <li key={addon.id} className={panelRow}>
      <span className="grid gap-0.5"><span className="font-semibold text-ink">{addon.name}{addon.is_active ? "" : " (off)"}</span>
        <span className="text-sm text-muted">{addon.amount} · sold {addon.sold}{addon.remaining != null ? ` · ${addon.remaining} left` : ""}
          {addon.variants.length ? ` · ${addon.variants.map(variant => variant.label).join(", ")}` : ""}</span></span>
      <span className="flex gap-2">
        <button className="desk-button" type="button" disabled={disabled} onClick={() => update.mutate({ id: addon.id, patch: { is_active: !addon.is_active } })}>
          {addon.is_active ? "Stop selling" : "Sell again"}</button>
        {addon.sold === 0 ? <button className="desk-button" type="button" disabled={disabled} onClick={() => remove.mutate(addon.id)}>Delete</button> : null}
      </span>
    </li>)}</ul>
  </section>;
}
