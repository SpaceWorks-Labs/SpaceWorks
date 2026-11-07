import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge, Skeleton } from "../../../components/ui";
import {
  collectionResults,
  createMachineType,
  getMachineTypePricing,
  getMachineTypes,
  machineKeys,
  setMachineTypePricing,
  updateMachineType,
  type MachineType,
  type MachineTypeCapabilityConfig,
  type MeteringUnit,
} from "../machinesApi";
import { CapabilityPresetListEditor } from "./machine/CapabilityPresetListEditor";
import { usePriceDropCheck } from "../priceDrop/usePriceDropCheck";
import { useStaffChargesOn } from "../useStaffChargesOn";

const meteringUnits: Array<{ value: MeteringUnit; label: string }> = [
  { value: "weight", label: t`Weight (grams)` },
  { value: "volume", label: t`Volume (milliliters)` },
  { value: "length", label: t`Length (millimeters)` },
  { value: "count", label: t`Count` },
  { value: "minutes", label: t`Minutes` },
];
const defaultConfig: MachineTypeCapabilityConfig = { metering_unit: "count", requires_booking: false };

function configFor(machineType: MachineType): MachineTypeCapabilityConfig {
  const config = machineType.capability_config;
  return config && meteringUnits.some((unit) => unit.value === config.metering_unit)
    ? config
    : defaultConfig;
}

type PresetKey = "accepted_materials" | "accepted_colours";

function withPresetList(config: MachineTypeCapabilityConfig, key: PresetKey, values: string[]) {
  if (values.length) return { ...config, [key]: values };
  const next = { ...config };
  delete next[key];
  return next;
}

function CapabilityPresetEditors({ config, disabled = false, onChange }: {
  config: MachineTypeCapabilityConfig;
  disabled?: boolean;
  onChange: (config: MachineTypeCapabilityConfig) => void;
}) {
  return <div className="grid gap-2 md:grid-cols-2">
    <CapabilityPresetListEditor
      label={t`Materials`}
      singularLabel="Material"
      values={config.accepted_materials ?? []}
      disabled={disabled}
      onChange={(values) => onChange(withPresetList(config, "accepted_materials", values))}
    />
    <CapabilityPresetListEditor
      label={t`Colours`}
      singularLabel="Colour"
      values={config.accepted_colours ?? []}
      disabled={disabled}
      onChange={(values) => onChange(withPresetList(config, "accepted_colours", values))}
    />
  </div>;
}

type PricingDraft = { rate: string; flatFee: string; paymentEnabled: boolean | null };
type TypeDraft = { name: string; icon: string; config: MachineTypeCapabilityConfig };
const blankPricing = (): PricingDraft => ({ rate: "", flatFee: "", paymentEnabled: null });

function PricingEditor({ makerspaceId, machineType, currency, canConfigure, draft, onDraftChange }: {
  makerspaceId: number; machineType: MachineType; currency: string; canConfigure: boolean; draft: PricingDraft; onDraftChange: (value: PricingDraft) => void;
}) {
  const queryClient = useQueryClient();
  const pricing = useQuery({ queryKey: machineKeys.pricing(makerspaceId), queryFn: () => getMachineTypePricing(makerspaceId), enabled: canConfigure });
  const row = pricing.data?.results.find((item) => item.machine_type_id === machineType.id);
  const { rate, flatFee, paymentEnabled } = draft;
  const setRate = (rate: string) => onDraftChange({ ...draft, rate });
  const setFlatFee = (flatFee: string) => onDraftChange({ ...draft, flatFee });
  const setPaymentEnabled = (paymentEnabled: boolean) => onDraftChange({ ...draft, paymentEnabled });
  const payload = () => ({
    rate_per_unit: rate || row?.rate_per_unit || "0.00",
    flat_fee: flatFee || row?.flat_fee || "0.00",
    payment_enabled: paymentEnabled ?? row?.payment_enabled ?? false,
  });
  const mutation = useMutation({
    mutationFn: () => setMachineTypePricing(makerspaceId, machineType.id, payload()),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: machineKeys.pricing(makerspaceId) }),
  });
  // Lane L24: a cheaper type price may owe prepaid jobs not started yet a refund.
  const drop = usePriceDropCheck(makerspaceId);
  const save = async () => {
    const path = `/admin/makerspace/${makerspaceId}/machine-type-pricing/${machineType.id}`;
    if (await drop.check(path, "PUT", payload())) mutation.mutate();
  };
  const shownRate = rate || row?.rate_per_unit || "0.00";
  const shownFlatFee = flatFee || row?.flat_fee || "0.00";
  const shownEnabled = paymentEnabled ?? row?.payment_enabled ?? false;
  // #184: with machine charges off the rate card is not edited here (stored rates stay).
  const chargesOn = useStaffChargesOn("machines", makerspaceId);

  if (!canConfigure || !chargesOn) return null;
  return <div className="grid gap-2 rounded-lg bg-bg p-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto_auto] md:items-end">
    <label className="eyebrow grid gap-1">{t`Rate per unit (${currency})`}<input className="desk-input" type="number" min="0" step="0.01" value={shownRate} onChange={(event) => setRate(event.target.value)} />
    </label>
    <label className="eyebrow grid gap-1">{t`Flat fee (${currency})`}<input className="desk-input" type="number" min="0" step="0.01" value={shownFlatFee} onChange={(event) => setFlatFee(event.target.value)} />
    </label>
    <label className="eyebrow flex items-center gap-2"><input type="checkbox" checked={shownEnabled} onChange={(event) => setPaymentEnabled(event.target.checked)} /> {t` Enable payment`}</label>
    <button className="desk-button-primary" type="button" onClick={() => { void save(); }} disabled={mutation.isPending || drop.checking}>{mutation.isPending ? t`Saving...` : t`Save pricing`}</button>
    {pricing.isLoading ? <p className="text-xs text-muted md:col-span-4">{t`Loading pricing...`}</p> : null}
    {pricing.error instanceof Error ? <p className="text-xs text-danger md:col-span-4">{pricing.error.message}</p> : null}
    {mutation.isSuccess ? <p className="text-xs text-success-ink md:col-span-4">{t`Pricing saved.`}</p> : null}
    {mutation.error instanceof Error ? <p className="text-xs text-danger md:col-span-4">{mutation.error.message}</p> : null}
    {drop.dialog}
  </div>;
}

function CustomTypeRow({ makerspaceId, machineType, canConfigure, currency, draft, onDraftChange, pricingDraft, onPricingChange }: {
  makerspaceId: number; machineType: MachineType; canConfigure: boolean; currency: string; draft: TypeDraft; onDraftChange: (value: TypeDraft) => void; pricingDraft: PricingDraft; onPricingChange: (value: PricingDraft) => void;
}) {
  const queryClient = useQueryClient();
  const { name, icon, config } = draft;
  const setName = (name: string) => onDraftChange({ ...draft, name });
  const setIcon = (icon: string) => onDraftChange({ ...draft, icon });
  const setConfig = (config: MachineTypeCapabilityConfig) => onDraftChange({ ...draft, config });
  const rename = useMutation({
    mutationFn: () => updateMachineType(makerspaceId, machineType.id, { name: name.trim(), icon: icon.trim(), capability_config: config }),
    onSuccess: async () => { await Promise.all([queryClient.invalidateQueries({ queryKey: machineKeys.types(makerspaceId) }), queryClient.invalidateQueries({ queryKey: machineKeys.list(makerspaceId) })]); },
  });
  return <div className="border-t border-line p-3 first:border-t-0">
    <form className="grid gap-2 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto] md:items-end" onSubmit={(event) => { event.preventDefault(); rename.mutate(); }}>
      <label className="eyebrow grid gap-1">{t`Name`}<input className="desk-input" value={name} disabled={!canConfigure} onChange={(event) => setName(event.target.value)} required /></label>
      <label className="eyebrow grid gap-1">{t`Icon`}<input className="desk-input" value={icon} disabled={!canConfigure} onChange={(event) => setIcon(event.target.value)} placeholder={t`Optional icon`} /></label>
      <label className="eyebrow grid gap-1">{t`Metering unit`}<select className="desk-input" value={config.metering_unit} disabled={!canConfigure} onChange={(event) => setConfig({ ...config, metering_unit: event.target.value as MeteringUnit })}>{meteringUnits.map((unit) => <option key={unit.value} value={unit.value}>{unit.label}</option>)}</select></label>
      {canConfigure ? <button className="desk-button-primary" type="submit" disabled={rename.isPending || !name.trim()}>{rename.isPending ? t`Saving...` : t`Save type`}</button> : null}
      <label className="eyebrow flex items-center gap-2 md:col-span-4"><input type="checkbox" checked={config.requires_booking} disabled={!canConfigure} onChange={(event) => setConfig({ ...config, requires_booking: event.target.checked })} /> {t` Requires booking (not yet enforced)`}</label>
      <div className="md:col-span-4"><CapabilityPresetEditors config={config} disabled={!canConfigure} onChange={setConfig} /></div>
      <p className="text-xs text-muted md:col-span-4">{t`Slug: ${machineType.slug} (fixed)`}</p>
      {rename.error instanceof Error ? <p className="text-sm text-danger md:col-span-4">{rename.error.message}</p> : null}
    </form>
    <PricingEditor makerspaceId={makerspaceId} machineType={machineType} currency={currency} canConfigure={canConfigure} draft={pricingDraft} onDraftChange={onPricingChange} />
  </div>;
}

export function MachineTypesPanel({ makerspaceId, canConfigureMachineTypes, visible = true }: { makerspaceId: number; canConfigureMachineTypes: boolean; visible?: boolean }) {
  const queryClient = useQueryClient();
  const [typeDrafts, setTypeDrafts] = useState<Record<number, TypeDraft>>({});
  const [priceDrafts, setPriceDrafts] = useState<Record<number, PricingDraft>>({});
  const priceFor = (id: number) => priceDrafts[id] ?? blankPricing();
  const changePrice = (id: number, value: PricingDraft) => setPriceDrafts(current => ({ ...current, [id]: value }));
  const [slug, setSlug] = useState("");
  const [name, setName] = useState("");
  const [icon, setIcon] = useState("");
  const [config, setConfig] = useState(defaultConfig);
  const machineTypes = useQuery({ queryKey: machineKeys.types(makerspaceId), queryFn: () => getMachineTypes(makerspaceId) });
  const pricing = useQuery({ queryKey: machineKeys.pricing(makerspaceId), queryFn: () => getMachineTypePricing(makerspaceId), enabled: canConfigureMachineTypes });
  const create = useMutation({
    mutationFn: () => createMachineType(makerspaceId, { slug: slug.trim(), name: name.trim(), icon: icon.trim(), capability_config: config }),
    onSuccess: async () => { setSlug(""); setName(""); setIcon(""); setConfig(defaultConfig); await queryClient.invalidateQueries({ queryKey: machineKeys.types(makerspaceId) }); },
  });
  const types = collectionResults(machineTypes.data);
  const currency = pricing.data?.currency ?? "Currency";
  const chargesOn = useStaffChargesOn("machines", makerspaceId);

  if (!visible) return null;
  return <details id="machine-type-settings" className="mb-4 overflow-hidden rounded-xl border border-line bg-panel">
    <summary className="min-h-11 cursor-pointer bg-surface px-4 py-3 text-sm font-semibold text-ink">{t`Machine types and pricing`}</summary>
    <div className="grid gap-3 p-3">
      <p className="text-sm text-muted">{t`Structural configuration is fixed for built-in types.`}{chargesOn ? t` Prices are makerspace-specific and use the default currency shown beside each amount.` : ""}</p>
      {chargesOn ? null : <p className="text-sm text-muted">{t`Machine charges are off in this space, so machine use is free.`}</p>}
      <p className="text-sm text-muted">{t`Machine time bookings are not available. The requires booking flag does not block service requests or job starts.`}</p>
      {canConfigureMachineTypes ? <form className="grid gap-2 rounded-xl border border-line bg-bg p-3 md:grid-cols-4 md:items-end" onSubmit={(event) => { event.preventDefault(); create.mutate(); }}>
        <label className="eyebrow grid gap-1">{t`Slug`}<input className="desk-input" value={slug} onChange={(event) => setSlug(event.target.value)} placeholder="laser-cutter" required /></label>
        <label className="eyebrow grid gap-1">{t`Name`}<input className="desk-input" value={name} onChange={(event) => setName(event.target.value)} placeholder={t`Laser cutter`} required /></label>
        <label className="eyebrow grid gap-1">{t`Icon`}<input className="desk-input" value={icon} onChange={(event) => setIcon(event.target.value)} placeholder={t`Optional icon`} /></label>
        <label className="eyebrow grid gap-1">{t`Metering unit`}<select className="desk-input" value={config.metering_unit} onChange={(event) => setConfig({ ...config, metering_unit: event.target.value as MeteringUnit })}>{meteringUnits.map((unit) => <option key={unit.value} value={unit.value}>{unit.label}</option>)}</select></label>
        <label className="eyebrow flex items-center gap-2"><input type="checkbox" checked={config.requires_booking} onChange={(event) => setConfig({ ...config, requires_booking: event.target.checked })} /> {t` Requires booking (not yet enforced)`}</label>
        <button className="desk-button-primary" type="submit" disabled={create.isPending || !slug.trim() || !name.trim()}>{create.isPending ? t`Creating...` : t`Create type`}</button>
        <div className="md:col-span-4"><CapabilityPresetEditors config={config} onChange={setConfig} /></div>
        {create.error instanceof Error ? <p className="text-sm text-danger md:col-span-4">{create.error.message}</p> : null}
      </form> : <p className="text-sm text-muted">{t`You have read-only access to machine types and pricing.`}</p>}
      {machineTypes.isLoading ? <Skeleton className="h-20 w-full" /> : null}
      {machineTypes.error instanceof Error ? <p className="text-sm text-danger">{machineTypes.error.message}</p> : null}
      {types.length ? <div className="overflow-hidden rounded-xl border border-line">{types.map((machineType) => machineType.is_builtin || machineType.makerspace === null ? <div key={machineType.id} className="grid gap-2 border-t border-line p-3 first:border-t-0"><div className="flex flex-wrap items-center justify-between gap-2"><span><strong className="block text-sm text-ink">{machineType.name}</strong><span className="text-xs text-muted">{machineType.icon || t`No icon`} · {machineType.slug} · {configFor(machineType).metering_unit} · {configFor(machineType).requires_booking ? t`booking flag on (not yet enforced)` : t`booking flag off`}</span></span><Badge tone="neutral">{t`Built-in · structural config read-only`}</Badge></div><PricingEditor makerspaceId={makerspaceId} machineType={machineType} currency={currency} canConfigure={canConfigureMachineTypes} draft={priceFor(machineType.id)} onDraftChange={value => changePrice(machineType.id, value)} /></div> : <CustomTypeRow key={machineType.id} makerspaceId={makerspaceId} machineType={machineType} canConfigure={canConfigureMachineTypes} currency={currency} draft={typeDrafts[machineType.id] ?? { name: machineType.name, icon: machineType.icon, config: configFor(machineType) }} onDraftChange={value => setTypeDrafts(current => ({ ...current, [machineType.id]: value }))} pricingDraft={priceFor(machineType.id)} onPricingChange={value => changePrice(machineType.id, value)} />)}</div> : null}
    </div>
  </details>;
}
