import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ErrorText, KeyValueCard, RelativeTime, SegmentedControl } from "../../../components/ui";
import { ProviderForm } from "./ProviderForm";
import { ProviderTestAction } from "./ProviderTestAction";
import { useProviderSettings } from "./providersApi";
import { PROVIDERS, type ProviderSpec } from "./providerSpecs";
import { LogoLoader } from "../../../components/LogoLoader";

/** One provider's settings card: last change, the form, and its test when it has one. */
export function Provider({ spec }: { spec: ProviderSpec }) {
  const settings = useProviderSettings(spec.key);
  const data = settings.data;
  if (settings.isLoading) return <LogoLoader size={48} className="min-h-64 py-3" />;
  if (settings.isError || !data) return <ErrorText resource={`${spec.title} settings`} onRetry={() => { void settings.refetch(); }} />;
  const info = Object.entries(data.info);
  return <div className="grid gap-4">
    <p className="text-sm text-muted">{spec.summary}</p>
    <p className="text-xs text-muted">
      {data.last_changed.at ? <>{t`Last changed `}<RelativeTime date={data.last_changed.at} exact />{data.last_changed.by ? ` by ${data.last_changed.by}` : ""}.</> : t`Never changed.`}
    </p>
    {info.length ? <KeyValueCard title={t`For the Meta webhook setup`} items={info.map(([label, value]) => ({
      label: label === "callback_url" ? t`Callback URL` : t`Verify token`, value: <code className="break-all">{value || t`Saved after the first change`}</code> }))} /> : null}
    <ProviderForm key={`${spec.key}:${data.updated_at ?? "new"}:${data.secrets.map(row => row.set).join()}`} spec={spec} saved={data} />
    {data.test ? <ProviderTestAction provider={spec.key} kind={data.test} /> : null}
  </div>;
}

/** Platform SMS, push, WhatsApp and app attestation credentials: secrets are write-only (#190). */
export function ProvidersSection() {
  const [active, setActive] = useState(PROVIDERS[0].key);
  const spec = PROVIDERS.find(row => row.key === active) ?? PROVIDERS[0];
  return <div className="grid gap-4">
    <p className="text-sm text-muted">{t`Every change needs a fresh sign-in check and is recorded in the platform audit log, by field name only. Saved secrets are never shown again.`}</p>
    <SegmentedControl label={t`Provider`} value={spec.key} options={PROVIDERS.map(row => ({ value: row.key, label: row.title }))}
      onChange={value => setActive(value as ProviderSpec["key"])} />
    <Provider key={spec.key} spec={spec} />
  </div>;
}
