import { t } from "@lingui/core/macro";
import { useState } from "react";

import { ErrorBlock, SettingsRow } from "../../components/ui";
import { DomainSettingsFields } from "./DomainSettingsFields";
import { SettingLock } from "./SettingLock";
import { useEffectiveAuthority } from "./settingsAuthorityApi";
import {
  DOMAIN_TITLES,
  type SettingsDomain,
  useDomainSettings,
  useUpdateDomainSettings,
} from "./domainSettingsApi";

type Props = { makerspaceId: number; domain: SettingsDomain };

const READ_ONLY_NOTE: Record<SettingsDomain, string> = {
  events: "You can see these settings. The Space Manager decides who can change them.",
  bookings: "You can see these settings. The Space Manager decides who can change them.",
  machines: "You can see these settings. Changing them needs the Space Manager's go-ahead, and your "
    + "machine types must cover every machine here, because they apply to all of them.",
  inventory: "You can change loan length and renewals. The Space Manager decides who can change the rest.",
};

/**
 * One domain's feature switches and settings, saved through the domain-settings endpoint so
 * the domain's own manager can change them without holding manage_makerspace.
 */
export function DomainSettingsSection({ makerspaceId, domain }: Props) {
  const query = useDomainSettings(makerspaceId, domain);
  const authority = useEffectiveAuthority(makerspaceId);
  // Separate mutations so a failed toggle and a failed settings save report in their own place.
  const toggle = useUpdateDomainSettings(makerspaceId, domain);
  const save = useUpdateDomainSettings(makerspaceId, domain);
  if (query.isLoading) return <p className="text-sm text-muted">{t`Loading settings…`}</p>;
  if (!query.data) {
    return <ErrorBlock error={query.error ?? new Error(t`Couldn't load these settings.`)}
      onRetry={() => { void query.refetch(); }} />;
  }
  const { editable, features, settings } = query.data;
  const permissions = query.data.setting_permissions ?? {};
  const busy = toggle.isPending || save.isPending;
  // Only the Space Manager manages locks; everyone else sees which settings are locked.
  const canLock = authority.data?.modules?.some(row => row.module === domain && row.space_manager) ?? false;
  const lockedFields = new Set(Object.entries(permissions).filter(([, value]) => !value.editable).map(([key]) => key));
  return <div className="grid min-w-0 gap-2">
    {!editable ? <p role="note" className="text-sm text-muted">{READ_ONLY_NOTE[domain]}</p> : null}
    {features.length ? <SettingsRow label={t`Features`}
      helper="Optional features for this area. Each has its own switch; turning one off keeps its data.">
      <fieldset className="grid min-w-0 gap-2">
        <legend className="sr-only">{DOMAIN_TITLES[domain]} features</legend>
        {features.map((feature) => <div key={feature.key} className="grid min-w-0 gap-1">
        <label className="min-h-11 flex items-start gap-3 text-sm text-ink">
          <input className="mt-1 h-4 w-4" type="checkbox" checked={feature.enabled}
            // An enabled switch whose module went away can still be turned off.
            disabled={!feature.editable || busy || (!feature.available && !feature.enabled)}
            onChange={(event) => toggle.mutate({ features: { [feature.key]: event.target.checked } })} />
          <span className="grid min-w-0 gap-0.5">
            <span>{feature.label}</span>
            {feature.description ? <span className="text-muted">{feature.description}</span> : null}
            {!feature.available ? <span className="text-muted">{t`Needs a module that is not installed here.`}</span> : null}
          </span>
        </label>
        <SettingLock makerspaceId={makerspaceId} settingKey={feature.key} label={feature.label}
          locked={feature.locked} canLock={canLock} />
        </div>)}
        {toggle.error ? <p role="alert" className="text-sm text-danger">{toggle.error.message}</p> : null}
        {toggle.isSuccess ? <p role="status" className="text-sm text-muted">{t`Features updated.`}</p> : null}
      </fieldset>
    </SettingsRow> : null}
    {Object.keys(settings).length ? <DomainSettingsFields key={JSON.stringify(settings)} values={settings}
      disabled={busy || Object.keys(settings).every(field => lockedFields.has(field))}
      lockedFields={lockedFields}
      renderLock={field => <SettingLock makerspaceId={makerspaceId} settingKey={field} label={field}
        locked={permissions[field]?.locked ?? false} canLock={canLock} />}
      pending={save.isPending} error={save.error?.message}
      onSave={(patch) => save.mutate({ settings: patch })} /> : null}
    {save.isSuccess ? <p role="status" className="text-sm text-muted">{t`Settings saved.`}</p> : null}
  </div>;
}

/** Collapsible inline variant for consoles that list their settings on the page (Machines). */
export function DomainSettingsDisclosure({ makerspaceId, domain }: Props) {
  const [open, setOpen] = useState(false);
  return <details className="mb-4 overflow-hidden rounded-xl border border-line bg-panel"
    onToggle={(event) => setOpen(event.currentTarget.open)}>
    <summary className="min-h-11 cursor-pointer bg-surface px-4 py-3 text-sm font-semibold text-ink">{DOMAIN_TITLES[domain]}</summary>
    {/* Mounted only while open, so the console does not fetch settings nobody asked to see. */}
    {open ? <div className="p-3"><DomainSettingsSection makerspaceId={makerspaceId} domain={domain} /></div> : null}
  </details>;
}
