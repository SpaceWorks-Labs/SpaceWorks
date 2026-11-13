import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Field } from "../../../../../components/ui";
import { collectionResults, getMachineTypes, machineKeys } from "../../../machinesApi";
import { adapterErrorMessage } from "./adapterCopy";
import { adapterKeys, adaptersApi } from "./adaptersApi";
import { LogoLoader } from "../../../../../components/LogoLoader";
import { BoxArt } from "../../../../../components/BoxSpinner";

const toMinutes = (value: string) => { const n = Number(value); return value.trim() !== "" && Number.isInteger(n) && n >= 1 && n <= 1440 ? n : undefined; };

function ProfileForm({ makerspaceId, typeId, name }: { makerspaceId: number; typeId: number; name: string }) {
  const client = useQueryClient();
  const profile = useQuery({ queryKey: adapterKeys.profile(makerspaceId, typeId), queryFn: () => adaptersApi.profile(makerspaceId, typeId) });
  const [draft, setDraft] = useState<{ idle: string; longest: string; clear: boolean; filter: boolean } | null>(null);
  const saved = profile.data?.config ?? {};
  const form = draft ?? { idle: saved.auto_off_idle_minutes ? String(saved.auto_off_idle_minutes) : "", longest: saved.max_session_minutes ? String(saved.max_session_minutes) : "",
    clear: saved.require_area_clear ?? false, filter: saved.require_filter_ok ?? false };
  const bad = (value: string) => value.trim() !== "" && toMinutes(value) === undefined;
  const save = useMutation({ mutationFn: () => adaptersApi.setProfile(makerspaceId, typeId, {
    ...(toMinutes(form.idle) ? { auto_off_idle_minutes: toMinutes(form.idle) } : {}), ...(toMinutes(form.longest) ? { max_session_minutes: toMinutes(form.longest) } : {}),
    require_area_clear: form.clear, require_filter_ok: form.filter }),
  onSuccess: () => { setDraft(null); void client.invalidateQueries({ queryKey: adapterKeys.profile(makerspaceId, typeId) }); } });
  if (profile.isLoading) return <LogoLoader label={t`Loading…`} size={48} className="min-h-16 py-3" />;
  return <form className="grid gap-3" aria-label={t`Safety defaults for ${name}`} onSubmit={event => { event.preventDefault(); if (!bad(form.idle) && !bad(form.longest)) save.mutate(); }}>
    <div className="grid gap-3 sm:grid-cols-2">
      <Field label={t`Switch off when idle for (minutes)`} hint={t`Empty means no automatic switch-off.`} error={bad(form.idle) ? t`Use a whole number from 1 to 1440.` : undefined}>
        <input className="desk-input" inputMode="numeric" value={form.idle} onChange={event => setDraft({ ...form, idle: event.target.value })} /></Field>
      <Field label={t`Longest session (minutes)`} hint={t`Empty means no limit.`} error={bad(form.longest) ? t`Use a whole number from 1 to 1440.` : undefined}>
        <input className="desk-input" inputMode="numeric" value={form.longest} onChange={event => setDraft({ ...form, longest: event.target.value })} /></Field>
    </div>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.clear} onChange={event => setDraft({ ...form, clear: event.target.checked })} />{t`Work area must be confirmed clear before it starts`}</label>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.filter} onChange={event => setDraft({ ...form, filter: event.target.checked })} />{t`Filter must be healthy before it starts`}</label>
    <p className="text-sm text-muted">{t`These apply to every adapter target on machines of this type. A single target can override them in its own safety settings.`}</p>
    {save.isError || profile.isError ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(save.error ?? profile.error)}</p> : null}
    {save.isSuccess && !draft ? <p role="status" className="text-sm text-muted">{t`Saved.`}</p> : null}
    <button type="submit" className="desk-button-primary justify-self-start" disabled={save.isPending}>{save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save defaults`}</button>
  </form>;
}

/** Safety defaults per machine type, in the adapters area ("Machine types" tab): every adapter target on that type's machines inherits them. */
export function AdapterTypeProfiles({ makerspaceId }: { makerspaceId: number }) {
  const types = useQuery({ queryKey: machineKeys.types(makerspaceId), queryFn: () => getMachineTypes(makerspaceId) });
  const rows = collectionResults(types.data);
  return <div className="grid gap-3">
    <p className="text-sm text-muted">{t`Set safety defaults once per kind of machine. Each adapter target on a machine of that type follows them unless it overrides a value.`}</p>
    {types.isLoading ? <LogoLoader label={t`Loading…`} size={48} className="min-h-16 py-3" /> : null}
    {!types.isLoading && !rows.length ? <p className="text-sm text-muted">{t`No machine types yet.`}</p> : null}
    {rows.map(row => <details key={row.id} className="rounded-2xl border border-line bg-panel p-4"><summary className="cursor-pointer font-semibold">{row.name}</summary>
      <div className="mt-3"><ProfileForm makerspaceId={makerspaceId} typeId={row.id} name={row.name} /></div></details>)}
  </div>;
}
