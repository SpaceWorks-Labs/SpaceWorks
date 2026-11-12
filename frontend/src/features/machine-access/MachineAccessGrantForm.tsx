import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { accessKeys, findCandidates, grantAccess, type Candidate } from "./api";
import { BoxArt } from "../../components/BoxSpinner";

export type AccessTarget = { machines: { id: number; name: string; machine_type: number }[]; types: { id: number; name: string }[] };

/** Give one or many members access to one machine or one machine type; optional expiry and note. */
export function MachineAccessGrantForm({ makerspaceId, targets, fixed, preselected = [], onDone }: {
  makerspaceId: number; targets: AccessTarget;
  /** Lock the target (a type page or a machine drawer): `type:ID` or `machine:ID`. */
  fixed?: string; preselected?: Candidate[]; onDone?: () => void;
}) {
  const client = useQueryClient();
  const [target, setTarget] = useState(fixed ?? "");
  const [search, setSearch] = useState("");
  const [chosen, setChosen] = useState<Candidate[]>(preselected);
  const [expires, setExpires] = useState("");
  const [note, setNote] = useState("");
  const candidates = useQuery({ queryKey: accessKeys.candidates(makerspaceId, search), queryFn: () => findCandidates(makerspaceId, search), enabled: search.trim().length > 0 });
  const save = useMutation({
    mutationFn: () => {
      const [kind, id] = target.split(":");
      return grantAccess(makerspaceId, { member_ids: chosen.map(row => row.user_id), expires_at: expires ? new Date(expires).toISOString() : null, note,
        ...(kind === "machine" ? { machine_id: Number(id) } : { machine_type_id: Number(id) }) });
    },
    onSuccess: async (result) => {
      await client.invalidateQueries({ queryKey: accessKeys.all(makerspaceId) });
      const failed = new Set(result.failed.map(row => row.member_id));
      setChosen(chosen.filter(row => failed.has(row.user_id)));
      if (!failed.size) { setNote(""); setExpires(""); onDone?.(); }
    },
  });
  const add = (row: Candidate) => { if (!chosen.some(item => item.user_id === row.user_id)) setChosen([...chosen, row]); setSearch(""); };
  return <form className="grid gap-3 rounded-xl border border-line bg-panel p-3" aria-label={t`Give machine access`}
    onSubmit={event => { event.preventDefault(); save.mutate(); }}>
    <h3 className="title-panel">{t`Give machine access`}</h3>
    {fixed ? null : <label className="grid gap-1 text-sm">{t`Machine or machine type`}
      <select className="desk-input" required value={target} onChange={event => setTarget(event.target.value)}>
        <option value="">{t`Choose a machine or a type`}</option>
        <optgroup label={t`Every machine of a type`}>{targets.types.map(row => <option key={`t${row.id}`} value={`type:${row.id}`}>{row.name}</option>)}</optgroup>
        <optgroup label={t`One machine`}>{targets.machines.map(row => <option key={`m${row.id}`} value={`machine:${row.id}`}>{row.name}</option>)}</optgroup>
      </select></label>}
    <label className="grid gap-1 text-sm">{t`Find members`}
      <input className="desk-input" value={search} onChange={event => setSearch(event.target.value)} placeholder={t`Search by name`} /></label>
    {search.trim() && candidates.data ? <ul className="flex flex-wrap gap-2" aria-label={t`Matching members`}>{candidates.data.results.map(row =>
      <li key={row.user_id}><button type="button" className="desk-button-ghost min-h-11" onClick={() => add(row)}>{t`Add ${row.name}`}</button></li>)}</ul> : null}
    {chosen.length ? <ul className="flex flex-wrap gap-2" aria-label={t`Members to give access`}>{chosen.map(row =>
      <li key={row.user_id} className="flex items-center gap-1 rounded-full border border-line px-3 py-1 text-sm">{row.name}
        <button type="button" className="min-h-11 px-1 text-muted" aria-label={t`Remove ${row.name}`} onClick={() => setChosen(chosen.filter(item => item.user_id !== row.user_id))}>×</button></li>)}</ul> : null}
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="grid gap-1 text-sm">{t`Access ends (optional)`}<input className="desk-input" type="date" value={expires} onChange={event => setExpires(event.target.value)} /></label>
      <label className="grid gap-1 text-sm">{t`Note (optional)`}<input className="desk-input" maxLength={1000} value={note} onChange={event => setNote(event.target.value)} /></label>
    </div>
    <button className="desk-button-primary w-fit" disabled={!target || !chosen.length || save.isPending}>{save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Give access`}</button>
    {save.data?.failed.length ? <p role="alert" className="text-sm text-danger">{t`Some members could not be given access: ${save.data.failed.map(row => row.detail).join(" ")}`}</p> : null}
    {save.error instanceof Error ? <p role="alert" className="text-sm text-danger">{save.error.message}</p> : null}
  </form>;
}
