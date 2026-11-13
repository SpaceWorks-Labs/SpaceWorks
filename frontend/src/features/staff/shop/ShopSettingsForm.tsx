import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { FormPageLayout } from "../../../components/layouts";
import { ErrorBlock, Field, SettingsSection } from "../../../components/ui";
import { DomainSettingsSection } from "../DomainSettingsSection";
import { SettingLock } from "../SettingLock";
import { effectiveKey, useEffectiveAuthority } from "../settingsAuthorityApi";
import { fetchSettings, saveSettings, staffShopError, staffShopKeys } from "./staffShopApi";
import { SHOP_NUMBER_FIELDS, SHOP_SETTING_DEFAULTS, shopSettingsPatch, shopSettingsProblem, type ShopSettingValues } from "./shopSettingsFields";
import { LogoLoader } from "../../../components/LogoLoader";

/** Shop policy and switches reuse the same per-key authority as every other module. */
export function ShopSettingsForm({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: staffShopKeys.settings(makerspaceId), queryFn: () => fetchSettings(makerspaceId), retry: false });
  const authority = useEffectiveAuthority(makerspaceId);
  const policy = authority.data?.modules.find(row => row.module === "shop");
  const permissions = new Map(policy?.keys.map(row => [row.key, row]));
  const editable = new Set(authority.error ? [] : policy?.keys.filter(row => row.editable).map(row => row.key));
  const [values, setValues] = useState<ShopSettingValues | null>(null);
  useEffect(() => { if (query.data) setValues({ ...SHOP_SETTING_DEFAULTS, ...query.data }); }, [query.data]);
  const patch = values && query.data ? shopSettingsPatch(values, query.data, editable) : {};
  const problem = values ? shopSettingsProblem(values) : "";
  const save = useMutation({ mutationFn: () => saveSettings(makerspaceId, patch),
    onSuccess: saved => client.setQueryData(staffShopKeys.settings(makerspaceId), saved),
    onError: () => { void client.invalidateQueries({ queryKey: effectiveKey(makerspaceId) }); } });
  const allowed = (key: keyof ShopSettingValues) => editable.has(`shop_${key}`);
  const set = (next: Partial<ShopSettingValues>) => setValues(current => current ? { ...current, ...next } : current);
  const value = <K extends keyof ShopSettingValues>(key: K) => allowed(key) ? values![key] : query.data?.[key] ?? values![key];
  const lock = (key: keyof ShopSettingValues, label: string) => <SettingLock makerspaceId={makerspaceId}
    settingKey={`shop_${key}`} label={label} locked={permissions.get(`shop_${key}`)?.locked ?? false} canLock={policy?.space_manager ?? false} />;
  const disabled = !policy || Boolean(authority.error) || !Object.keys(patch).length || Boolean(problem);
  return <FormPageLayout header={{ eyebrow: t`Shop`, title: t`Shop settings`, subtitle: t`Features, holds, reminders, returns and what buyers read before ordering.` }}
    state={query.error ? { status: "error", error: staffShopError(query.error), onRetry: () => { void query.refetch(); } }
      : !values ? { status: "loading" } : { status: "ready" }}
    submit={{ label: t`Save settings`, pending: save.isPending, pendingLabel: t`Saving…`, onClick: () => { if (!disabled) save.mutate(); },
      disabled, disabledReason: problem || (!policy || authority.error ? t`Settings access could not be confirmed.` : t`No editable settings have changed.`) }}
    form={values ? <div className="grid gap-6">
      <SettingsSection title={t`Shop features`}><DomainSettingsSection makerspaceId={makerspaceId} domain="shop" /></SettingsSection>
      {authority.isPending ? <LogoLoader label={t`Checking settings access…`} size={48} className="min-h-16 py-3" /> : null}
      {authority.error ? <ErrorBlock error={authority.error} onRetry={() => { void authority.refetch(); }} /> : null}
      {!authority.error && !policy ? <p role="status" className="text-sm text-muted">{t`Your role cannot change shop settings.`}</p> : null}
      {save.error ? <p role="alert" className="text-sm text-danger">{staffShopError(save.error)}</p> : null}
      {save.isSuccess ? <p role="status" className="text-sm text-muted">{t`Settings saved.`}</p> : null}
      {problem ? <p role="alert" className="text-sm text-danger">{problem}</p> : null}
      <fieldset className="grid gap-5">
        <legend className="sr-only">{t`Shop policy settings`}</legend>
        <div className="grid gap-4 sm:grid-cols-2">{SHOP_NUMBER_FIELDS.map(field => <div key={field.key} className="grid gap-1">
          <Field label={field.label} hint={field.hint}><input className="desk-input min-h-11 w-32 tabular-nums" type="number"
            min={field.min} max={field.max} step={1} disabled={!allowed(field.key) || save.isPending} value={value(field.key)}
            onChange={event => set({ [field.key]: Number(event.target.value) })} /></Field>{lock(field.key, field.label)}
        </div>)}</div>
        <div className="grid gap-1"><Field label={t`Pickup note`} hint={t`Shown to buyers before they order: where and when to collect.`}>
          <textarea className="desk-input" rows={3} maxLength={300} disabled={!allowed("pickup_note") || save.isPending} value={value("pickup_note")}
            onChange={event => set({ pickup_note: event.target.value })} /></Field>{lock("pickup_note", t`Pickup note`)}</div>
        <div className="grid gap-1"><Field label={t`Shop policy`} hint={t`Shown to buyers before they order and pay.`}>
          <textarea className="desk-input" rows={5} maxLength={2000} disabled={!allowed("policy_text") || save.isPending} value={value("policy_text")}
            onChange={event => set({ policy_text: event.target.value })} /></Field>{lock("policy_text", t`Shop policy`)}</div>
      </fieldset>
    </div> : null} />;
}
