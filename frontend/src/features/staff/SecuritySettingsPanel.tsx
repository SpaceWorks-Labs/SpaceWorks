import { useId, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { SettingsLayout } from "../../components/layouts";
import { ErrorText, SettingsRow, StatusPill } from "../../components/ui";
import {
  getSecuritySettings, lockSecuritySetting, securitySettingsKey, unlockSecuritySetting, updateSecuritySettings,
  type SecuritySetting, type SecuritySettings,
} from "../../lib/api/securitySettings";
import { adminQueryState } from "./adminPresentation";
import { PiiAccessBanner } from "./PiiAccessBanner";
import type { Makerspace } from "./panels/shared";

/**
 * Per-space security settings. The Space Manager and a platform superadmin change them;
 * a superadmin can also lock one so the space cannot loosen it. Every change asks for a
 * fresh identity check (the API client prompts for it) and lands in the audit log.
 */
export function SecuritySettingsPanel({ makerspace }: { makerspace: Makerspace }) {
  const queryClient = useQueryClient();
  const key = securitySettingsKey(makerspace.id);
  const query = useQuery({ queryKey: key, queryFn: () => getSecuritySettings(makerspace.id) });
  const settle = (data: SecuritySettings) => queryClient.setQueryData(key, data);
  const update = useMutation({ mutationFn: ({ setting, value }: { setting: string; value: unknown }) =>
    updateSecuritySettings(makerspace.id, { [setting]: value }), onSuccess: settle });
  const lock = useMutation({ mutationFn: ({ setting, note }: { setting: string; note: string }) =>
    lockSecuritySetting(makerspace.id, setting, true, note), onSuccess: settle });
  const unlock = useMutation({ mutationFn: (setting: string) => unlockSecuritySetting(makerspace.id, setting),
    onSuccess: settle });
  const data = query.data;
  const pending = update.isPending || lock.isPending || unlock.isPending;
  const error = update.error ?? lock.error ?? unlock.error;

  return <SettingsLayout
    header={{ title: "Security", subtitle: `Sign-in rules for staff at ${makerspace.name}. Changes need a fresh identity check and are recorded in the audit log.` }}
    state={adminQueryState(query, "security settings")}
    sections={[
      { id: "sign-in", title: "Sign-in requirements",
        description: data?.can_lock ? "You can lock a setting so this space cannot turn it off. Only a platform superadmin removes a lock."
          : "A setting locked by the platform cannot be loosened here.",
        rows: data ? <>
          {data.settings.map(setting => <SecurityRow key={setting.key} setting={setting} data={data} pending={pending}
            onChange={value => update.mutate({ setting: setting.key, value })}
            onLock={note => lock.mutate({ setting: setting.key, note })} onUnlock={() => unlock.mutate(setting.key)} />)}
          {error ? <ErrorText message={error.message} /> : null}
        </> : null },
      { id: "pii", title: "Platform access to personal data",
        description: "Platform administrators see members' personal details masked unless they open a short, recorded window.",
        rows: <PiiAccessBanner makerspaceId={makerspace.id} /> },
    ]} />;
}

type RowProps = { setting: SecuritySetting; data: SecuritySettings; pending: boolean;
  onChange: (value: unknown) => void; onLock: (note: string) => void; onUnlock: () => void };

function SecurityRow({ setting, data, pending, onChange, onLock, onUnlock }: RowProps) {
  const id = useId();
  const [note, setNote] = useState("");
  const forcedOn = setting.kind === "bool" && setting.lock?.floor === true;
  const on = setting.value === true;
  if (setting.kind !== "bool") {
    return <SettingsRow label={setting.label} helper={setting.description}><p className="text-sm text-ink">{String(setting.value)}</p></SettingsRow>;
  }
  return <SettingsRow label={setting.label} helper={setting.description} htmlFor={id}>
    <div className="grid gap-3">
      <label className="flex min-h-11 items-center gap-3 text-sm text-ink">
        <input id={id} className="h-4 w-4" type="checkbox" checked={on}
          disabled={!data.can_edit || pending || (forcedOn && on)} onChange={event => onChange(event.target.checked)} />
        <span>{on ? "Required" : "Not required"}</span>
      </label>
      {setting.lock ? <StatusPill tone="info" icon="Lock"
        label={`Locked by platform${setting.lock.note ? `: ${setting.lock.note}` : ""}`} /> : null}
      {data.can_lock ? (setting.lock
        ? <div><button className="desk-button" type="button" disabled={pending} onClick={onUnlock}>Remove platform lock</button></div>
        : <form className="flex flex-wrap items-end gap-2" onSubmit={event => { event.preventDefault(); onLock(note.trim()); setNote(""); }}>
          <label className="grid gap-1 text-sm text-ink">
            <span className="font-semibold">Note for the space (optional)</span>
            <input className="min-h-11 rounded-lg border border-line bg-panel px-3" value={note} maxLength={200}
              onChange={event => setNote(event.target.value)} />
          </label>
          <button className="desk-button" type="submit" disabled={pending}>Lock on</button>
        </form>) : null}
    </div>
  </SettingsRow>;
}
