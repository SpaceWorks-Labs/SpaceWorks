import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EmptyState, Field, Modal, SettingsSection, StatusPill } from "../../../components/ui";
import { formatPrice } from "../../../lib/money";
import { guestErrorText, guestKeys, guestStaffApi, type DayPassProduct, type Entitlements } from "../api";
import { BORROW_MODES, MACHINE_MODES, borrowModeLabel, entitlementSummary, machineModeLabel } from "../labels";

type Draft = { name: string; amount: string; currency: string; daily_cap: string; is_public: boolean; is_active: boolean; entitlements: Entitlements };
const blank = (currency: string): Draft => ({ name: "", amount: "0", currency, daily_cap: "", is_public: true, is_active: true, entitlements: {} });
const toDraft = (row: DayPassProduct): Draft => ({ name: row.name, amount: row.amount, currency: row.currency,
  daily_cap: row.daily_cap === null ? "" : String(row.daily_cap), is_public: row.is_public, is_active: row.is_active, entitlements: row.entitlements ?? {} });

/** Settings › Guest passes: the day passes a guest can buy or staff can sell (223 b). */
export function DayPassProductsSettings({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const key = guestKeys.products(makerspaceId);
  const products = useQuery({ queryKey: key, queryFn: () => guestStaffApi.products(makerspaceId) });
  const [editing, setEditing] = useState<{ id: number | null; draft: Draft } | null>(null);
  const done = () => { void client.invalidateQueries({ queryKey: guestKeys.all(makerspaceId) }); };
  const save = useMutation({
    mutationFn: ({ id, draft }: { id: number | null; draft: Draft }) => {
      const body = { ...draft, amount: draft.amount.trim() || "0", daily_cap: draft.daily_cap.trim() ? Number(draft.daily_cap) : null };
      return id === null ? guestStaffApi.createProduct(makerspaceId, body) : guestStaffApi.updateProduct(makerspaceId, id, body);
    },
    onSuccess: () => { setEditing(null); done(); },
  });
  const archive = useMutation({ mutationFn: (id: number) => guestStaffApi.archiveProduct(makerspaceId, id), onSuccess: done });
  const rows = products.data ?? [];
  return <SettingsSection title={t`Day passes`} description={t`A priced pass records the amount owed under membership charges and can be paid online when online payments are on. A day pass gives no credit toward joining.`}>
    {products.isLoading ? <p role="status" className="py-4 text-sm text-muted">{t`Loading day passes…`}</p> : null}
    {products.isError ? <p role="alert" className="py-4 text-sm text-danger">{guestErrorText(products.error)}</p> : null}
    {products.isSuccess && !rows.length ? <EmptyState message={t`No day passes yet.`} /> : null}
    <ul className="grid gap-3 py-3">
      {rows.map((row) => <li key={row.id} className="flex flex-wrap items-start gap-3 rounded-2xl border border-line p-4">
        <div className="min-w-0 flex-1 basis-56">
          <p className="title-section break-words">{row.name}</p>
          <p className="text-sm text-muted">{formatPrice(row.amount, row.currency)}{row.daily_cap ? ` · ${t`${row.daily_cap} per day`}` : ""} · {entitlementSummary(row.entitlements)}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {row.archived_at ? <StatusPill label={t`Archived`} /> : <>
            <StatusPill tone={row.is_active ? "success" : "neutral"} label={row.is_active ? t`On sale` : t`Paused`} />
            {row.is_public ? <StatusPill label={t`Shown publicly`} /> : null}
            <button type="button" className="desk-button min-h-11" onClick={() => { save.reset(); setEditing({ id: row.id, draft: toDraft(row) }); }}>{t`Edit`}</button>
            <button type="button" className="desk-button-ghost min-h-11" disabled={archive.isPending} onClick={() => archive.mutate(row.id)}>{t`Archive`}</button>
          </>}
        </div>
      </li>)}
    </ul>
    {archive.error ? <p role="alert" className="text-sm text-danger">{guestErrorText(archive.error)}</p> : null}
    <button type="button" className="desk-button min-h-11" onClick={() => { save.reset(); setEditing({ id: null, draft: blank("") }); }}>{t`Add a day pass`}</button>
    {editing ? <DayPassEditor editing={editing} pending={save.isPending} error={save.error ? guestErrorText(save.error) : null}
      onChange={(draft) => setEditing({ ...editing, draft })} onClose={() => setEditing(null)} onSave={() => save.mutate(editing)} /> : null}
  </SettingsSection>;
}

function DayPassEditor({ editing, pending, error, onChange, onClose, onSave }: {
  editing: { id: number | null; draft: Draft }; pending: boolean; error: string | null;
  onChange: (draft: Draft) => void; onClose: () => void; onSave: () => void;
}) {
  const { draft } = editing;
  const set = <K extends keyof Draft>(field: K, value: Draft[K]) => onChange({ ...draft, [field]: value });
  const narrow = (field: keyof Entitlements, value: string) => {
    const next = { ...draft.entitlements };
    if (value) next[field] = value as never; else delete next[field];
    set("entitlements", next);
  };
  return <Modal open title={editing.id === null ? t`Add a day pass` : t`Edit day pass`} onClose={() => { if (!pending) onClose(); }}
    footer={<div className="flex flex-wrap justify-end gap-2">
      <button type="button" className="desk-button" disabled={pending} onClick={onClose}>{t`Cancel`}</button>
      <button type="button" className="desk-button-primary" disabled={pending || !draft.name.trim()} onClick={onSave}>{pending ? t`Saving…` : t`Save day pass`}</button>
    </div>}>
    <div className="grid gap-4">
      <Field label={t`Name`}><input className="desk-input" maxLength={120} value={draft.name} onChange={(event) => set("name", event.target.value)} /></Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t`Price`} hint={t`0 for a free pass.`}><input className="desk-input" inputMode="decimal" value={draft.amount} onChange={(event) => set("amount", event.target.value.replace(/[^\d.]/g, ""))} /></Field>
        <Field label={t`Currency`} hint={t`Blank uses the space's currency.`}><input className="desk-input uppercase" maxLength={3} value={draft.currency} onChange={(event) => set("currency", event.target.value.toUpperCase())} /></Field>
      </div>
      <Field label={t`Passes per day`} hint={t`Blank for no limit beyond the space's daily cap.`}>
        <input className="desk-input" type="number" min={1} value={draft.daily_cap} onChange={(event) => set("daily_cap", event.target.value)} /></Field>
      <Field label={t`Borrowing on this pass`} hint={t`A pass can only narrow the space's guest rules, never widen them.`}>
        <select className="desk-input" value={draft.entitlements.borrow ?? ""} onChange={(event) => narrow("borrow", event.target.value)}>
          <option value="">{t`Same as the guest rules`}</option>{BORROW_MODES.map((mode) => <option key={mode} value={mode}>{borrowModeLabel(mode)}</option>)}</select></Field>
      <Field label={t`Machine use on this pass`}>
        <select className="desk-input" value={draft.entitlements.machines ?? ""} onChange={(event) => narrow("machines", event.target.value)}>
          <option value="">{t`Same as the guest rules`}</option>{MACHINE_MODES.map((mode) => <option key={mode} value={mode}>{machineModeLabel(mode)}</option>)}</select></Field>
      <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" className="h-5 w-5 accent-accent" checked={draft.is_active} onChange={(event) => set("is_active", event.target.checked)} />{t`On sale`}</label>
      <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" className="h-5 w-5 accent-accent" checked={draft.is_public} onChange={(event) => set("is_public", event.target.checked)} />{t`Show on the public page and in the member area`}</label>
      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
    </div>
  </Modal>;
}
