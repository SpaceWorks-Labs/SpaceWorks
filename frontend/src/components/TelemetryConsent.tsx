import { t } from "@lingui/core/macro";
import { useEffect, useId, useState } from "react";
import { consentStorageKey, deniedConsent, readConsent, saveConsent, type Consent } from "../lib/telemetry/policy";

export function TelemetryConsent({ scope, onChange }: { scope: string; onChange: (value: Consent) => void }) {
  const [value, setValue] = useState<Consent>(deniedConsent);
  const [error, setError] = useState(false);
  useEffect(() => { const next = readConsent(scope); setValue(next); onChange(next); }, [scope, onChange]);
  useEffect(() => {
    const changed = (event: StorageEvent) => { if (event.storageArea === localStorage && (event.key === consentStorageKey(scope) || event.key === null)) { const next = readConsent(scope); setValue(next); onChange(next); } };
    window.addEventListener("storage", changed); return () => window.removeEventListener("storage", changed);
  }, [scope, onChange]);
  const headingId = useId();
  function update(next: Consent) {
    if (!saveConsent(scope, next)) { setError(true); setValue(deniedConsent()); onChange(deniedConsent()); return; }
    setError(false); setValue(next); onChange(next);
  }
  return <section aria-labelledby={headingId} className="desk-panel grid gap-2 p-4">
    <h2 id={headingId} className="title-panel">{t`Privacy preferences`}</h2>
    {(["analytics", "replay", "diagnostics"] as const).map(purpose => <label key={purpose} className="flex min-h-11 items-center gap-3 text-sm text-ink">
      <input type="checkbox" checked={value[purpose]} onChange={event => update({ ...value, [purpose]: event.target.checked })} />
      {purpose === "analytics" ? t`Usage analytics` : purpose === "replay" ? t`Session replay` : t`Diagnostics and performance`}
    </label>)}
    <p className="text-sm text-muted">{t`Replay is limited to anonymous About visits; other pages stay excluded.`}</p>
    {error ? <p className="text-sm text-danger" role="alert">{t`Preferences could not be saved. Telemetry remains off.`}</p> : null}
  </section>;
}

