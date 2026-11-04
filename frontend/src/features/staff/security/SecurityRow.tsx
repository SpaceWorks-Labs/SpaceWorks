import { useId, useState } from "react";
import { SettingsRow, StatusPill } from "../../../components/ui";
import type { SecuritySetting, SecuritySettings } from "../../../lib/api/securitySettings";
import { SecurityValueControl } from "./SecurityValueControl";
import { describeFloor, describeValue } from "./securityRules";

type RowProps = { setting: SecuritySetting; data: SecuritySettings; pending: boolean;
  onChange: (value: unknown) => void; onLock: (floor: unknown, note: string) => void; onUnlock: () => void };

/**
 * One security setting: its editor, the lock-floor badge when the platform locked it, and for
 * a superadmin the lock controls. A boolean lock forces the stricter value; any other lock keeps
 * the current value as the floor, so the space may only choose values at least that strict.
 */
export function SecurityRow({ setting, data, pending, onChange, onLock, onUnlock }: RowProps) {
  const id = useId();
  const [note, setNote] = useState("");
  const bool = setting.kind === "bool";
  const strict = setting.strict_value ?? true;
  const floor = bool ? strict : setting.value;
  const lockNote = setting.lock?.note ? `: ${setting.lock.note}` : "";
  return <SettingsRow label={setting.label} helper={setting.description} htmlFor={id}>
    <div className="grid gap-3">
      <SecurityValueControl key={JSON.stringify(setting.value)} setting={setting} id={id} disabled={!data.can_edit || pending} onChange={onChange} />
      {!bool ? <p className="text-sm text-muted">Now: {describeValue(setting, setting.value)}</p> : null}
      {setting.lock ? <div><StatusPill tone="info" icon="Lock"
        label={bool ? `Locked by platform${lockNote}` : `Locked by platform, allows ${describeFloor(setting, setting.lock.floor)}${lockNote}`} /></div> : null}
      {data.can_lock ? (setting.lock
        ? <div><button className="desk-button min-h-11" type="button" disabled={pending} onClick={onUnlock}>Remove platform lock</button></div>
        : <form className="flex flex-wrap items-end gap-2" onSubmit={event => { event.preventDefault(); onLock(floor, note.trim()); setNote(""); }}>
          <label className="grid gap-1 text-sm text-ink">
            <span className="font-semibold">Note for the space (optional)</span>
            <input className="desk-input min-h-11" value={note} maxLength={200} onChange={event => setNote(event.target.value)} />
          </label>
          <button className="desk-button min-h-11" type="submit" disabled={pending}>
            {bool ? (strict ? "Lock on" : "Lock off") : "Lock at current value"}</button>
        </form>) : null}
    </div>
  </SettingsRow>;
}
