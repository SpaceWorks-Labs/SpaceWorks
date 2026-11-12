import { t } from "@lingui/core/macro";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useContext, useEffect, useState } from "react";
import { archiveKit, createKit, createKitVersion, publishKit, staffKit, staffKits, type KitLine, type KitSummary } from "../inventory/equipmentKitsApi";
import { useIntakeScope } from "../inventory/useIntakeScope";
import { StaffListContext } from "./StaffListContext";
import { KitProductPicker } from "./KitProductPicker";
import { getSessionOwner } from "../../lib/api/sessionTokens";
import { PagePager } from "../../components/ui";
import { LogoLoader } from "../../components/LogoLoader";

function kitLineLabel(line: KitLine) {
  const id = line.product_id; const quantity = line.quantity_per_person;
  return line.kind === "consumable" ? t`Item #${id} · ${quantity} per person · used up`
    : t`Item #${id} · ${quantity} per person · returned`;
}

/** Inventory authority remains server-enforced on every read and mutation. */
export function EquipmentKitManager({ tenant, canEdit }: { tenant: number; canEdit: boolean }) {
  const session = useIntakeScope(); const actor = useContext(StaffListContext).actorId;
  if (!session.owner || !actor || session.owner !== String(actor)) return null;
  const scope = JSON.stringify([session.context, session.owner, actor, tenant, canEdit]);
  return <KitManager key={scope} scope={scope} tenant={tenant} canEdit={canEdit} actor={actor} context={session.context} />;
}
function KitManager({ scope, tenant, canEdit, actor, context }: { scope: string; tenant: number; canEdit: boolean; actor: number; context: ReturnType<typeof useIntakeScope>["context"] }) {
  const client = useQueryClient(); const [page, setPage] = useState(1); const [selected, setSelected] = useState<KitSummary | null>(null);
  const [denied, setDenied] = useState(false);
  const [name, setName] = useState(""); const [lines, setLines] = useState<KitLine[]>([]); const [busy, setBusy] = useState(false); const [review, setReview] = useState(false); const [message, setMessage] = useState("");
  const list = useQuery({ queryKey: ["equipment-kit-management", scope, page], queryFn: () => staffKits(tenant, page, canEdit), enabled: !denied, retry: false });
  const detail = useQuery({ queryKey: ["equipment-kit-detail", scope, selected?.id, selected?.revision, selected?.current_version], queryFn: () => staffKit(tenant, selected!.id), enabled: Boolean(selected) && !denied, retry: false });
  const [loadedId, setLoadedId] = useState<number | null>(null);
  useEffect(() => {
    if (selected && detail.data?.id === selected.id && detail.data.revision === selected.revision && detail.data.current_version === selected.current_version && loadedId !== selected.id) {
      setLines(detail.data.lines.map(line => ({ ...line })));
      setLoadedId(selected.id);
    }
  }, [selected, detail.data, loadedId]);
  async function perform(action: () => Promise<unknown>) {
    if (getSessionOwner(context) !== String(actor)) { setDenied(true); return; }
    setBusy(true); setMessage("");
    try { await action(); if (selected) await client.invalidateQueries({ queryKey: ["equipment-kit-detail", scope, selected.id] }); setSelected(null); setName(""); setLines([]); setReview(false); await client.invalidateQueries({ queryKey: ["equipment-kit-management", scope] }); setMessage(t`Kit saved.`); }
    catch (error) { const status = (error as { status?: number })?.status; if ([401, 403, 404].includes(status ?? 0)) { setDenied(true); setSelected(null); setName(""); setLines([]); client.removeQueries({ queryKey: ["equipment-kit-management", scope] }); client.removeQueries({ queryKey: ["equipment-kit-detail", scope] }); } else if (status === 409) { setReview(true); await list.refetch(); setMessage(t`This kit changed. Review the latest version before trying again.`); } else setMessage(t`The kit could not be saved.`); }
    finally { setBusy(false); }
  }
  function edit(row: KitSummary) { setSelected(row); setName(row.name); setLines([]); setLoadedId(null); setReview(false); }
  if (denied || list.isError || detail.isError) return <p role="status">{t`Kits are unavailable for your access.`}</p>;
  return <section className="grid gap-3"><h2 className="title-panel">{t`Equipment kits`}</h2>
    <p className="text-sm text-muted">{t`Templates suggest items; saving a kit does not reserve equipment or use stock.`}</p>
    {message ? <p role="status">{message}</p> : null}
    {list.isPending ? <LogoLoader label={t`Loading kits…`} size={48} className="min-h-16 py-3" /> : list.isError ? <p role="alert">{t`Kits are unavailable.`}</p> : <>
      {list.data.results.map(row => <div key={row.id} className="flex flex-wrap items-center gap-2 rounded-xl border border-line p-3"><span className="min-w-0 flex-1 break-words text-sm text-ink">{row.name} · {row.published_for_contexts ? t`Published` : t`Private`}</span><button type="button" className="desk-button" onClick={() => edit(row)}>{t`View`}</button>
        {canEdit ? <><button type="button" className="desk-button" disabled={busy || review} onClick={() => void perform(() => publishKit(tenant, row.id, row.revision, !row.published_for_contexts))}>{row.published_for_contexts ? t`Unpublish` : t`Publish`}</button><button type="button" className="desk-button" disabled={busy || review} onClick={() => void perform(() => archiveKit(tenant, row.id, row.revision, !row.archived))}>{row.archived ? t`Restore` : t`Archive`}</button></> : null}</div>)}
      <PagePager page={page} setPage={setPage} next={list.data.next} />
    </>}
    {selected && detail.data && (detail.data.revision !== selected.revision || detail.data.current_version !== selected.current_version) ? <p role="status">{t`This kit changed. Your open edits are preserved; review the latest list when ready.`} <button type="button" className="desk-button" onClick={() => { void list.refetch(); }}>{t`Refresh kit list`}</button></p> : null}
    {selected && detail.data?.id === selected.id && detail.data.revision === selected.revision && detail.data.current_version === selected.current_version ? <div><p>{t`Current version ${detail.data.current_version}`}</p><ul>{detail.data.lines.map(line => <li key={line.product_id}>{kitLineLabel(line)}</li>)}</ul></div> : null}
    {canEdit ? <fieldset disabled={busy || review} className="grid min-w-0 gap-2"><legend className="text-sm font-semibold text-ink">{selected ? t`Create a new version` : t`Create a kit`}</legend>
      <label className="grid gap-1 text-sm">{t`Name`}<input className="desk-input" value={name} onChange={event => setName(event.target.value)} /></label>
      <KitProductPicker tenant={tenant} scope={scope} lines={lines} onChange={setLines} />
      {lines.map(line => <div key={line.product_id} className="flex flex-wrap items-end gap-2"><label className="grid gap-1 text-sm">{t`Quantity for item #${line.product_id}`}<input className="desk-input w-24" type="number" min="1" max="99" value={line.quantity_per_person} onChange={event => setLines(current => current.map(item => item.product_id === line.product_id ? { ...item, quantity_per_person: Number(event.target.value) } : item))} /></label><button type="button" className="desk-button-ghost" onClick={() => setLines(current => current.filter(item => item.product_id !== line.product_id))}>{t`Remove item #${line.product_id}`}</button></div>)}
      <button type="button" className="desk-button-primary w-fit" disabled={Boolean(selected && loadedId !== selected.id) || !name.trim() || !lines.length || lines.length > 50 || lines.some(line => !Number.isInteger(line.quantity_per_person) || line.quantity_per_person < 1 || line.quantity_per_person > 99)} onClick={() => void perform(() => selected ? createKitVersion(tenant, selected.id, selected.revision, name.trim(), lines) : createKit(tenant, name.trim(), lines))}>{t`Save kit`}</button>
    </fieldset> : null}
    {review ? <button type="button" className="desk-button w-fit" onClick={() => { setSelected(null); setReview(false); }}>{t`Review latest kits`}</button> : null}
  </section>;
}
