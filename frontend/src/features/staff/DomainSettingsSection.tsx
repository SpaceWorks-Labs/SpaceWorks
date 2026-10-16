import { useState } from "react";

import { ErrorBlock, SettingsRow } from "../../components/ui";
import { DomainSettingsFields } from "./DomainSettingsFields";
import {
  DOMAIN_TITLES,
  type SettingsDomain,
  useDomainSettings,
  useUpdateDomainSettings,
} from "./domainSettingsApi";

type Props = { makerspaceId: number; domain: SettingsDomain };

const LOCKED_NOTE =
  "These settings apply to every machine in this space, so only a Space Manager or a Machine Manager "
  + "whose machine types cover every machine here can change them.";

/**
 * One domain's feature switches and settings, saved through the domain-settings endpoint so
 * the domain's own manager can change them without holding manage_makerspace.
 */
export function DomainSettingsSection({ makerspaceId, domain }: Props) {
  const query = useDomainSettings(makerspaceId, domain);
  // Separate mutations so a failed toggle and a failed settings save report in their own place.
  const toggle = useUpdateDomainSettings(makerspaceId, domain);
  const save = useUpdateDomainSettings(makerspaceId, domain);
  if (query.isLoading) return <p className="text-sm text-muted">Loading settings…</p>;
  if (!query.data) {
    return <ErrorBlock error={query.error ?? new Error("Couldn't load these settings.")}
      onRetry={() => { void query.refetch(); }} />;
  }
  const { editable, features, settings } = query.data;
  const busy = toggle.isPending || save.isPending;
  return <div className="grid min-w-0 gap-2">
    {!editable ? <p role="note" className="text-sm text-muted">{LOCKED_NOTE}</p> : null}
    {features.length ? <SettingsRow label="Features"
      helper="Optional features for this area. Modules are installed by the platform administrator.">
      <fieldset className="grid min-w-0 gap-2">
        <legend className="sr-only">{DOMAIN_TITLES[domain]} features</legend>
        {features.map((feature) => <label key={feature.key} className="min-h-11 flex items-start gap-3 text-sm text-ink">
          <input className="mt-1 h-4 w-4" type="checkbox" checked={feature.enabled}
            // An enabled switch whose module went away can still be turned off.
            disabled={!editable || busy || (!feature.available && !feature.enabled)}
            onChange={(event) => toggle.mutate({ features: { [feature.key]: event.target.checked } })} />
          <span className="grid min-w-0 gap-0.5">
            <span>{feature.label}</span>
            {feature.description ? <span className="text-muted">{feature.description}</span> : null}
            {!feature.available ? <span className="text-muted">Needs a module that is not installed here.</span> : null}
          </span>
        </label>)}
        {toggle.error ? <p role="alert" className="text-sm text-danger">{toggle.error.message}</p> : null}
        {toggle.isSuccess ? <p role="status" className="text-sm text-muted">Features updated.</p> : null}
      </fieldset>
    </SettingsRow> : null}
    {Object.keys(settings).length ? <DomainSettingsFields key={JSON.stringify(settings)} values={settings}
      disabled={!editable || busy} pending={save.isPending} error={save.error?.message}
      onSave={(patch) => save.mutate({ settings: patch })} /> : null}
    {save.isSuccess ? <p role="status" className="text-sm text-muted">Settings saved.</p> : null}
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
