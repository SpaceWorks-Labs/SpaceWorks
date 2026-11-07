import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Field, StatusPill } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { lifecycleApi, lifecycleKeys } from "../membershipLifecycleApi";
import { MembershipTimeline } from "./MembershipTimeline";

const errorText = (error: unknown) => (error instanceof StructuredApiError ? error.message : t`That did not work.`);
const on = (features: string[], key: string) => features.includes(`membership.${key}`);

function RecordForm({ membershipId }: { membershipId: number }) {
  const client = useQueryClient();
  const record = useQuery({ queryKey: lifecycleKeys.member(membershipId, "record"), queryFn: () => lifecycleApi.record(membershipId) });
  const [form, setForm] = useState({ state_code: "", gstin: "", staff_notes: "" });
  useEffect(() => { if (record.data && !record.data.pii_masked) setForm({ state_code: record.data.state_code, gstin: record.data.gstin, staff_notes: record.data.staff_notes }); }, [record.data]);
  const save = useMutation({ mutationFn: () => lifecycleApi.saveRecord(membershipId, form),
    onSuccess: (data) => client.setQueryData(lifecycleKeys.member(membershipId, "record"), data) });
  const set = (key: keyof typeof form, value: string) => setForm((current) => ({ ...current, [key]: value }));
  return <form className="grid gap-2 sm:grid-cols-2" aria-label={t`Member record`} onSubmit={(event) => { event.preventDefault(); save.mutate(); }}>
    <p className="text-sm text-muted sm:col-span-2">{t`Member number ${record.data?.member_number || "—"} · joined via ${record.data?.source || "unknown"}`}</p>
    <Field label={t`State code`} hint={t`Two digits, e.g. 29.`}><input className="desk-input" maxLength={2} inputMode="numeric" value={form.state_code} onChange={(event) => set("state_code", event.target.value)} /></Field>
    <Field label={t`GSTIN`}><input className="desk-input" maxLength={15} value={form.gstin} onChange={(event) => set("gstin", event.target.value.toUpperCase())} /></Field>
    <Field label={t`Staff notes`} hint={t`Staff only; never shown to the member.`} className="sm:col-span-2">
      <textarea className="desk-input min-h-20" maxLength={4000} value={form.staff_notes} onChange={(event) => set("staff_notes", event.target.value)} />
    </Field>
    <div><button className="desk-button-primary" type="submit" disabled={save.isPending || Boolean(record.data?.pii_masked)}>{save.isPending ? t`Saving…` : t`Save record`}</button></div>
    {save.error ?? record.error ? <p role="alert" className="text-sm text-danger sm:col-span-2">{errorText(save.error ?? record.error)}</p> : null}
  </form>;
}

function TitleChips({ membershipId, makerspaceId }: { membershipId: number; makerspaceId: number }) {
  const client = useQueryClient();
  const key = lifecycleKeys.member(membershipId, "titles");
  const assigned = useQuery({ queryKey: key, queryFn: () => lifecycleApi.memberTitles(membershipId) });
  const titles = useQuery({ queryKey: lifecycleKeys.titles(makerspaceId), queryFn: () => lifecycleApi.titles(makerspaceId) });
  const [titleId, setTitleId] = useState("");
  const assign = useMutation({ mutationFn: () => lifecycleApi.assignTitle(membershipId, Number(titleId), !(assigned.data ?? []).length),
    onSuccess: (data) => { setTitleId(""); client.setQueryData(key, data); } });
  const remove = useMutation({ mutationFn: (id: number) => lifecycleApi.unassignTitle(membershipId, id), onSuccess: (data) => client.setQueryData(key, data) });
  const free = (titles.data ?? []).filter((title) => !title.archived_at && !(assigned.data ?? []).some((row) => row.title.id === title.id));
  return <div className="grid gap-2">
    <div className="flex flex-wrap gap-2">{(assigned.data ?? []).map((row) => <span key={row.id} className="flex items-center gap-1">
      <StatusPill tone={row.is_primary ? "accent" : "neutral"} label={`${row.title.name}${row.is_primary ? " (on card)" : ""}`} />
      <button className="desk-button" type="button" aria-label={t`Remove ${row.title.name}`} onClick={() => remove.mutate(row.title.id)}>{t`Remove`}</button>
    </span>)}</div>
    {free.length ? <div className="flex flex-wrap items-end gap-2">
      <Field label={t`Add title`}><select className="desk-input max-w-full" value={titleId} onChange={(event) => setTitleId(event.target.value)}>
        <option value="">{t`Choose…`}</option>{free.map((title) => <option key={title.id} value={title.id}>{title.name}</option>)}</select></Field>
      <button className="desk-button" type="button" disabled={!titleId || assign.isPending} onClick={() => assign.mutate()}>{t`Add`}</button>
    </div> : null}
    {assign.error ?? remove.error ? <p role="alert" className="text-sm text-danger">{errorText(assign.error ?? remove.error)}</p> : null}
  </div>;
}

function ConsentList({ membershipId }: { membershipId: number }) {
  const consents = useQuery({ queryKey: lifecycleKeys.member(membershipId, "consents"), queryFn: () => lifecycleApi.consents(membershipId) });
  if (!consents.data?.length) return <p className="text-sm text-muted">{t`No consents recorded.`}</p>;
  return <ul className="grid gap-1 text-sm">{consents.data.map((row) => <li key={row.id}>
    {t`${row.purpose}: given ${new Date(row.given_at).toLocaleDateString(formatLocale())}`}{row.withdrawn_at ? t`, withdrawn ${new Date(row.withdrawn_at).toLocaleDateString(formatLocale())}` : ""}
    {row.notice_version ? t` (notice ${row.notice_version})` : ""}</li>)}</ul>;
}

/** X13, X16, X10, X28 for one member, each section only while its switch is on. */
export function MemberLifecycleDetails({ membershipId, makerspaceId, features }: { membershipId: number; makerspaceId: number; features: string[] }) {
  const history = useQuery({ queryKey: lifecycleKeys.member(membershipId, "history"), queryFn: () => lifecycleApi.history(membershipId),
    enabled: on(features, "history") });
  return <div className="mt-6 grid gap-6">
    {on(features, "records") ? <section aria-label={t`Record`}><h3 className="title-section mb-2">{t`Record`}</h3><RecordForm membershipId={membershipId} /></section> : null}
    {on(features, "titles") ? <section aria-label={t`Titles`}><h3 className="title-section mb-2">{t`Titles`}</h3><TitleChips membershipId={membershipId} makerspaceId={makerspaceId} /></section> : null}
    {on(features, "consent") ? <section aria-label={t`Consents`}><h3 className="title-section mb-2">{t`Consents`}</h3><ConsentList membershipId={membershipId} /></section> : null}
    {on(features, "history") ? <section aria-label={t`History`}><h3 className="title-section mb-2">{t`History`}</h3><MembershipTimeline entries={history.data ?? []} /></section> : null}
  </div>;
}
