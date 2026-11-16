import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Field, StatusPill } from "../../../../../components/ui";
import { adapterErrorMessage, capabilityLabel, targetTypeLabel } from "./adapterCopy";
import { adapterKeys, adaptersApi, type AdapterSummary, type Binding, type BindingCreate, type AdapterSwitches, type TargetType } from "./adaptersApi";
import { FREE_TEXT_TARGETS, TARGET_TYPES, useTargetLabel, useTargetOptions } from "./bindingTargets";
import { BoxArt } from "../../../../../components/BoxSpinner";

/** A capability whose child switch is off cannot be bound (the server refuses it too). */
const allowed = (name: string, switches: AdapterSwitches) => name === "checkout.kiosk" ? switches.kiosk : name === "access.authorize" ? switches.access : name.startsWith("media.") ? switches.video : true;

function BindForm({ makerspaceId, adapter, switches }: { makerspaceId: number; adapter: AdapterSummary; switches: AdapterSwitches }) {
  const client = useQueryClient();
  const [type, setType] = useState<TargetType>("machine");
  const [target, setTarget] = useState("");
  const [ref, setRef] = useState("");
  const [caps, setCaps] = useState<string[]>([]);
  const { options, loading } = useTargetOptions(makerspaceId, type);
  const freeText = FREE_TEXT_TARGETS.includes(type);
  const bind = useMutation({
    mutationFn: () => {
      const body: BindingCreate = { target_type: type, capabilities: caps, ...(ref.trim() ? { external_ref: ref.trim() } : {}),
        ...(type === "machine" ? { machine_id: Number(target) } : { target_id: target.trim() }) };
      return adaptersApi.bind(adapter.id, body);
    },
    onSuccess: () => { setTarget(""); setRef(""); setCaps([]); void client.invalidateQueries({ queryKey: adapterKeys.root(makerspaceId) }); },
  });
  const ready = caps.length > 0 && (type === "door" ? Boolean(target.trim() || ref.trim()) : Boolean(target));
  return <form className="grid gap-4 rounded-2xl border border-line bg-panel p-4" aria-label={t`Bind a target`}
    onSubmit={event => { event.preventDefault(); if (ready) bind.mutate(); }}>
    <h3 className="title-section">{t`Bind a target`}</h3>
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label={t`What kind of thing`}>
        <select className="desk-input" value={type} onChange={event => { setType(event.target.value as TargetType); setTarget(""); }}>
          {TARGET_TYPES.map(row => <option key={row} value={row}>{targetTypeLabel(row)}</option>)}</select>
      </Field>
      {freeText ? <Field label={t`Door name`} hint={t`The name the bridge uses for this door.`}>
        <input className="desk-input" maxLength={64} value={target} onChange={event => setTarget(event.target.value)} /></Field>
        : <Field label={targetTypeLabel(type)} hint={type === "storage_location" ? t`Staff only. Storage locations never appear on public pages.` : undefined}>
          <select className="desk-input" value={target} disabled={loading} onChange={event => setTarget(event.target.value)}>
            <option value="">{loading ? t`Loading…` : options.length ? t`Choose…` : t`Nothing to choose from`}</option>
            {options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></Field>}
    </div>
    <Field label={t`Bridge's name for it (optional)`} hint={t`Only if the bridge calls this target something else.`}>
      <input className="desk-input" maxLength={120} value={ref} onChange={event => setRef(event.target.value)} /></Field>
    <fieldset className="grid gap-2"><legend className="text-sm font-semibold text-ink">{t`What the adapter does for it`}</legend>
      {adapter.capabilities.length ? <div className="flex flex-wrap gap-x-5 gap-y-2">{adapter.capabilities.filter(cap => allowed(cap.name, switches)).map(cap => <label key={cap.name} className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={caps.includes(cap.name)} onChange={event => setCaps(event.target.checked ? [...caps, cap.name] : caps.filter(name => name !== cap.name))} />
        {capabilityLabel(cap)}</label>)}</div>
        : <p className="text-sm text-muted">{t`This adapter has not said what it can do yet. Once the bridge connects, its capabilities appear here.`}</p>}
    </fieldset>
    {bind.isError ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(bind.error)}</p> : null}
    <button type="submit" className="desk-button-primary justify-self-start" disabled={!ready || bind.isPending}>{bind.isPending ? <><BoxArt size={16} mono />{t`Binding…`}</> : t`Bind`}</button>
  </form>;
}

function BindingRow({ binding, name, makerspaceId, disabled }: { binding: Binding; name: string; makerspaceId: number; disabled: boolean }) {
  const client = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const unbind = useMutation({ mutationFn: () => adaptersApi.unbind(binding.id),
    onSuccess: () => { void client.invalidateQueries({ queryKey: adapterKeys.root(makerspaceId) }); } });
  return <li className="grid gap-2 rounded-2xl border border-line bg-panel p-4">
    <div className="flex flex-wrap items-center gap-3">
      <div className="min-w-0 flex-1"><p className="title-section break-words">{name}</p>
        <p className="text-sm text-muted">{targetTypeLabel(binding.target_type)} · {binding.capabilities.map(capabilityLabel).join(", ")}</p></div>
      {binding.enabled ? null : <StatusPill label={t`Disabled`} tone="warn" />}
      {confirming ? <span className="flex flex-wrap items-center gap-2" role="group" aria-label={t`Confirm unbind of ${name}`}>
        <span className="text-sm text-danger">{t`Queued commands for it are dropped.`}</span>
        <button type="button" className="desk-button" onClick={() => setConfirming(false)}>{t`Keep`}</button>
        <button type="button" className="desk-button-danger" disabled={unbind.isPending} onClick={() => unbind.mutate()}>{t`Unbind`}</button></span>
        : <button type="button" className="desk-button" disabled={disabled} aria-label={t`Unbind ${name}`} onClick={() => setConfirming(true)}>{t`Unbind`}</button>}
    </div>
    {unbind.isError ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(unbind.error)}</p> : null}
  </li>;
}

/** Bind or unbind the things a bridge looks after: machines, machine types, storage locations, boxes, items, doors and spaces. */
export function AdapterBindings({ makerspaceId, adapter, disabled, switches }: { makerspaceId: number; adapter: AdapterSummary; disabled: boolean; switches: AdapterSwitches }) {
  const label = useTargetLabel(makerspaceId, adapter.bindings);
  return <div className="grid gap-6">
    {adapter.bindings.length ? <ul className="grid gap-3" aria-label={t`Bound targets`}>{adapter.bindings.map(binding =>
      <BindingRow key={binding.id} binding={binding} makerspaceId={makerspaceId} disabled={disabled}
        name={label(binding.target_type, binding.machine_id, binding.target_id, binding.external_ref)} />)}</ul>
      : <p className="text-sm text-muted">{t`Nothing is bound yet.`}</p>}
    {disabled ? null : <BindForm makerspaceId={makerspaceId} adapter={adapter} switches={switches} />}
  </div>;
}
