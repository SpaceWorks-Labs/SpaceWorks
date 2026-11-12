import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { adapterErrorMessage } from "./adapterCopy";
import { adapterKeys, adaptersApi, type Binding, type SafetyConfig } from "./adaptersApi";
import { BoxArt } from "../../../../../components/BoxSpinner";

type Minutes = "auto_off_idle_minutes" | "max_session_minutes";
type Flag = "require_area_clear" | "require_filter_ok";
const toMinutes = (value: string) => { const n = Number(value); return value.trim() !== "" && Number.isInteger(n) && n >= 1 && n <= 1440 ? n : undefined; };
const show = (value: unknown) => value === undefined ? t`not set` : typeof value === "boolean" ? (value ? t`yes` : t`no`) : String(value);

/**
 * One target's safety settings. The server says, per key, whether the value follows the machine type or is this target's own override
 * (`effective_config`), so each row starts in its real state. Saving sends only the overrides: a key left on "follows the machine type" is
 * not sent, which clears any override it had.
 */
export function AdapterConfig({ makerspaceId, binding, name, disabled }: { makerspaceId: number; binding: Binding; name: string; disabled: boolean }) {
  const client = useQueryClient();
  const own = binding.config ?? {};
  const effective = binding.effective_config ?? {};
  const [minutes, setMinutes] = useState<Partial<Record<Minutes, string | null>>>({});
  const [flags, setFlags] = useState<Partial<Record<Flag, boolean | null>>>({});
  const [auto, setAuto] = useState<boolean | null>(null);
  const minutesNow = (key: Minutes): string | null => key in minutes ? minutes[key] ?? null : own[key] !== undefined ? String(own[key]) : null;
  const flagNow = (key: Flag): boolean | null => key in flags ? flags[key] ?? null : own[key] ?? null;
  const autoNow = auto ?? own.auto_apply_terminal ?? false;
  const save = useMutation({ mutationFn: () => {
    // The save replaces the whole config, so the shelf-pointer caps (edited on the pointer screen) are carried over untouched.
    const config: SafetyConfig = { ...(own.laser_max_power_pct !== undefined ? { laser_max_power_pct: own.laser_max_power_pct } : {}), ...(own.max_on_seconds !== undefined ? { max_on_seconds: own.max_on_seconds } : {}) };
    (["auto_off_idle_minutes", "max_session_minutes"] as Minutes[]).forEach(key => { const value = minutesNow(key); if (value !== null && toMinutes(value)) config[key] = toMinutes(value); });
    (["require_area_clear", "require_filter_ok"] as Flag[]).forEach(key => { const value = flagNow(key); if (value !== null) config[key] = value; });
    if (autoNow || own.auto_apply_terminal !== undefined) config.auto_apply_terminal = autoNow;
    return adaptersApi.setConfig(binding.id, config);
  }, onSuccess: () => { setMinutes({}); setFlags({}); setAuto(null); void client.invalidateQueries({ queryKey: adapterKeys.root(makerspaceId) }); } });
  const bad = (key: Minutes) => { const value = minutesNow(key); return value !== null && toMinutes(value) === undefined; };
  const source = (key: string) => effective[key]?.source === "binding" ? t`overridden here` : t`follows the machine type`;
  const minutesField = (key: Minutes, label: string) => <fieldset className="grid gap-2 rounded-control border border-line p-3">
    <legend className="px-1 font-semibold">{label}</legend>
    <div className="flex flex-wrap items-center gap-2">
      <select className="desk-input w-auto" value={minutesNow(key) === null ? "inherit" : "override"} aria-label={t`Where the value for ${label} comes from`}
        onChange={event => setMinutes({ ...minutes, [key]: event.target.value === "inherit" ? null : String(effective[key]?.value ?? "") })}>
        <option value="inherit">{t`Follows the machine type (${show(effective[key]?.source === "type" ? effective[key]?.value : undefined)})`}</option><option value="override">{t`Override for this target`}</option></select>
      {minutesNow(key) !== null ? <input className="desk-input w-28" inputMode="numeric" aria-label={label} value={minutesNow(key) ?? ""} onChange={event => setMinutes({ ...minutes, [key]: event.target.value })} /> : null}
      <span className="text-xs text-muted">{t`Now: ${show(effective[key]?.value)}, ${source(key)}`}</span>
    </div>
    {bad(key) ? <p className="text-xs text-danger">{t`Use a whole number from 1 to 1440.`}</p> : null}</fieldset>;
  const flag = (key: Flag, label: string) => <div className="grid gap-1 rounded-control border border-line p-3">
    <span className="font-semibold">{label}</span>
    <div className="flex flex-wrap items-center gap-2">
      <select className="desk-input w-auto" value={flagNow(key) === null ? "inherit" : flagNow(key) ? "yes" : "no"} aria-label={label}
        onChange={event => setFlags({ ...flags, [key]: event.target.value === "inherit" ? null : event.target.value === "yes" })}>
        <option value="inherit">{t`Follows the machine type (${show(effective[key]?.source === "type" ? effective[key]?.value : undefined)})`}</option><option value="yes">{t`Override: yes`}</option><option value="no">{t`Override: no`}</option></select>
      <span className="text-xs text-muted">{t`Now: ${show(effective[key]?.value)}, ${source(key)}`}</span>
    </div></div>;
  return <details className="text-sm"><summary className="cursor-pointer font-semibold">{t`Safety settings`}</summary>
    <form className="mt-3 grid gap-3" aria-label={t`Safety settings for ${name}`} onSubmit={event => { event.preventDefault(); if (!bad("auto_off_idle_minutes") && !bad("max_session_minutes")) save.mutate(); }}>
      {minutesField("auto_off_idle_minutes", t`Switch off when idle for (minutes)`)}
      {minutesField("max_session_minutes", t`Longest session (minutes)`)}
      {flag("require_area_clear", t`Work area must be confirmed clear before it starts`)}
      {flag("require_filter_ok", t`Filter must be healthy before it starts`)}
      <label className="flex items-start gap-2 rounded-control border border-line p-3"><input type="checkbox" className="mt-1" checked={autoNow} onChange={event => setAuto(event.target.checked)} />
        <span><strong>{t`Apply clean results automatically`}</strong><span className="block text-muted">{t`Off by default. When on, a completed job report goes straight through the job workflow. A failed report is always held for staff to review. Changing this is recorded in the audit log.`}</span></span></label>
      <p className="text-muted">{t`Only the values you override are saved for this target. Anything set to follow the machine type uses the type's value.`}</p>
      {save.isError ? <p role="alert" className="text-danger">{adapterErrorMessage(save.error)}</p> : null}
      {save.isSuccess ? <p role="status" className="text-muted">{t`Saved.`}</p> : null}
      <button type="submit" className="desk-button justify-self-start" disabled={disabled || save.isPending}>{save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save safety settings`}</button>
    </form>
  </details>;
}
