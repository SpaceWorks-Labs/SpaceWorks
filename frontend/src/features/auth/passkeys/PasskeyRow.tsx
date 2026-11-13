import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Fingerprint } from "lucide-react";
import type { Passkey } from "../../../generated/api";
import { ListRow, RelativeTime } from "../../../components/ui";

const date = (value: string) => new Date(value).toLocaleDateString(formatLocale(), { day: "numeric", month: "short", year: "numeric" });

/** One passkey: its name, when it was added and last used, and Rename / Remove. */
export function PasskeyRow({ passkey, busy, onRename, onRemove }: {
  passkey: Passkey; busy: boolean; onRename: (name: string) => void; onRemove: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(passkey.name);
  const title = passkey.name || "Passkey";
  const meta = <>
    {t`Added ${date(passkey.created_at)} · `}{passkey.last_used_at ? <>{t`Last used `}<RelativeTime date={passkey.last_used_at} /></> : t`Not used yet`}
    {passkey.backed_up ? t` · Synced across your devices` : ""}
    {passkey.usable_here ? "" : t` · Works only on ${passkey.rp_id}`}
  </>;
  const icon = <span aria-hidden="true" className="grid h-11 w-11 shrink-0 place-items-center rounded-full border border-line bg-surface text-accent-ink">
    <Fingerprint size={20} /></span>;
  if (editing) {
    return <form className="grid gap-3 rounded-2xl border border-line bg-panel p-4" onSubmit={event => {
      event.preventDefault(); onRename(name.trim()); setEditing(false);
    }}>
      <label className="grid gap-2 text-sm font-semibold text-ink" htmlFor={`passkey-name-${passkey.id}`}>{t`Passkey name`}<input id={`passkey-name-${passkey.id}`} className="desk-input w-full" value={name} maxLength={64} autoFocus
          onChange={event => setName(event.target.value)} /></label>
      <div className="flex flex-wrap gap-2">
        <button type="submit" className="desk-button-primary min-h-11" disabled={busy}>{t`Save name`}</button>
        <button type="button" className="desk-button min-h-11" onClick={() => { setName(passkey.name); setEditing(false); }}>{t`Cancel`}</button>
      </div>
    </form>;
  }
  return <ListRow title={title} identityContent={icon} meta={meta} right={<div className="flex flex-wrap gap-2">
    <button type="button" className="desk-button min-h-11" disabled={busy} aria-label={t`Rename ${title}`} onClick={() => setEditing(true)}>{t`Rename`}</button>
    <button type="button" className="desk-button-danger-outline min-h-11" disabled={busy} aria-label={t`Remove ${title}`} onClick={onRemove}>{t`Remove`}</button>
  </div>} />;
}
