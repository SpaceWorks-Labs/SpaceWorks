import { t } from "@lingui/core/macro";
import { ErrorBlock, Field, ListRow, RelativeTime, SettingsRow, StatusPill } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { SettingsLayout } from "../../../components/layouts";
import { inventoryQueryState } from "./inventoryPresentation";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { Pagination } from "../../../components/ui/Pagination";
import { usePaginatedQuery } from "../../../lib/usePaginatedQuery";
import { BoxArt } from "../../../components/BoxSpinner";

type Policy = { blind_default: boolean; variance_threshold: number | null };
type Schedule = { id: number; name: string; next_due: string; interval_days: number; blind: boolean; is_active: boolean };

export function StocktakeDiscipline({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const base = `/admin/makerspace/${makerspaceId}`;
  const policy = useQuery({ queryKey: ["stocktake-policy", makerspaceId], queryFn: () => staffRequest<Policy>(`${base}/stocktake-policy`) });
  const schedules = usePaginatedQuery<Schedule>({ key: ["stocktake-schedules", makerspaceId], path: `${base}/stocktake-schedules`, resetKey: String(makerspaceId) });
  const [draft, setDraft] = useState<Policy>({ blind_default: false, variance_threshold: null });
  const [name, setName] = useState("Cycle count");
  const [days, setDays] = useState(30);
  const [due, setDue] = useState("");
  useEffect(() => { if (policy.data) setDraft(policy.data); }, [policy.data]);
  const save = useMutation({ mutationFn: () => staffRequest(`${base}/stocktake-policy`, { method: "PUT", body: JSON.stringify(draft) }), onSuccess: () => { toast(t`Count policy saved.`); client.invalidateQueries({ queryKey: ["stocktake-policy", makerspaceId] }); } });
  const create = useMutation({ mutationFn: () => staffRequest(`${base}/stocktake-schedules`, { method: "POST", body: JSON.stringify({ name, interval_days: days, next_due: due, blind: draft.blind_default }) }), onSuccess: () => { toast(t`Count schedule updated.`); client.invalidateQueries({ queryKey: ["stocktake-schedules", makerspaceId] }); } });
  const toggle = useMutation({ mutationFn: (row: Schedule) => staffRequest(`${base}/stocktake-schedules/${row.id}`, { method: "PATCH", body: JSON.stringify({ is_active: !row.is_active }) }), onSuccess: () => { toast(t`Count schedule updated.`); client.invalidateQueries({ queryKey: ["stocktake-schedules", makerspaceId] }); } });
  return <SettingsLayout header={{ title: t`Count policy and schedule`, subtitle: t`Choose how counts are checked and when the next one is due.` }} state={inventoryQueryState(policy, "count policy")}
    sections={[{ id: "policy", title: t`Count policy`, rows: <>
      <SettingsRow label={t`Blind counts by default`} helper={t`Counters enter what they find without seeing expected quantities.`}><label className="flex min-h-11 items-center gap-2"><input type="checkbox" checked={draft.blind_default} onChange={event => setDraft({ ...draft, blind_default: event.target.checked })} />{t`Blind counts by default`}</label></SettingsRow>
      <SettingsRow label={t`Variance threshold`} helper={t`Leave blank to require approval for every count.`}><Field label={t`Variance units allowed without approval`}><input className="desk-input" type="number" min={0} value={draft.variance_threshold ?? ""} onChange={event => setDraft({ ...draft, variance_threshold: event.target.value === "" ? null : Number(event.target.value) })} /></Field></SettingsRow>
    </>, save: { dirty: JSON.stringify(draft) !== JSON.stringify(policy.data), pending: save.isPending, disabled: !policy.data, onSave: () => save.mutate(), onDiscard: () => { if (policy.data) setDraft(policy.data); }, error: save.error?.message } },
    { id: "schedules", title: t`Schedules`, rows: <div className="grid gap-6">
      <form className="grid gap-4" onSubmit={event => { event.preventDefault(); create.mutate(); }}>
        <SettingsRow label={t`Next count`}><Field label={t`Count name`}><input required className="desk-input" value={name} onChange={event => setName(event.target.value)} /></Field></SettingsRow>
        <SettingsRow label={t`Repeat interval`}><Field label={t`Every days`}><input required type="number" min={1} className="desk-input" value={days} onChange={event => setDays(Number(event.target.value))} /></Field></SettingsRow>
        <SettingsRow label={t`Start date`}><Field label={t`First count due`}><input required type="date" className="desk-input" value={due} onChange={event => setDue(event.target.value)} /></Field></SettingsRow>
        <button className="desk-button" disabled={create.isPending}>{create.isPending ? <><BoxArt size={16} mono />{t`Scheduling…`}</> : t`Schedule count`}</button>
        {create.error ? <ErrorBlock error={create.error} /> : null}
      </form>
      {schedules.results.map(row => <ListRow key={row.id} title={row.name} meta={<>{t`Due `}<RelativeTime date={row.next_due} /> {t` · Every ${row.interval_days} days`}</>}
        right={<div className="flex flex-wrap items-center gap-2"><StatusPill label={row.is_active ? t`Active` : t`Paused`} tone={row.is_active ? "success" : "neutral"} /><button className="desk-button-ghost" disabled={toggle.isPending} onClick={() => toggle.mutate(row)}>{toggle.isPending && toggle.variables?.id === row.id ? t`Updating…` : row.is_active ? t`Pause schedule` : t`Enable schedule`}</button></div>} />)}
      <Pagination page={schedules.page} totalPages={schedules.totalPages} count={schedules.count} pageSize={schedules.pageSize} onChange={schedules.setPage} />
      {schedules.error ? <ErrorBlock error={schedules.error} resource={t`schedules`} onRetry={() => { void schedules.refetch(); }} /> : null}{toggle.error ? <ErrorBlock error={toggle.error} /> : null}
    </div> }]} />;
}
