import { formatDate } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Field, StatusPill } from "../../components/ui";
import { StructuredApiError, memberRequest } from "../../lib/api";
import { MembershipTimeline } from "../staff/membershipLifecycle/MembershipTimeline";
import type { ConsentRow, TimelineEntry } from "../staff/membershipLifecycleApi";

type Ledger = { purposes: { key: string; label: string; description: string }[]; notice_version: string; consents: ConsentRow[] };
type Erasure = { id: number; status: string; member_note: string; decision_note: string; created_at: string; decided_at: string | null };
const erasureStatusLabel = (status: string) => {
  switch (status) {
    case "requested": return t`Requested`;
    case "approved": return t`Approved`;
    case "rejected": return t`Declined`;
    case "withdrawn": return t`Withdrawn`;
    default: return t`Unknown`;
  }
};
const base = (id: number) => `/member/makerspaces/${id}`;
const errorText = (error: unknown) => (error instanceof StructuredApiError ? error.message : t`That did not work. Try again.`);

/** X28: your membership history in words. */
export function MemberHistory({ makerspaceId }: { makerspaceId: number }) {
  const history = useQuery({ queryKey: ["member", "account", makerspaceId, "history"],
    queryFn: () => memberRequest<TimelineEntry[]>(`${base(makerspaceId)}/membership-history`) });
  if (history.isLoading) return <p className="text-sm text-muted">{t`Loading your history…`}</p>;
  if (history.isError) return <p role="alert" className="text-sm text-danger">{errorText(history.error)}</p>;
  return <MembershipTimeline entries={history.data ?? []} />;
}

function Consents({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const key = ["member", "account", makerspaceId, "consents"];
  const ledger = useQuery({ queryKey: key, queryFn: () => memberRequest<Ledger>(`${base(makerspaceId)}/consents`) });
  const change = useMutation({
    mutationFn: ({ purpose, give }: { purpose: string; give: boolean }) => memberRequest<Ledger>(`${base(makerspaceId)}/consents`,
      { method: give ? "POST" : "DELETE", body: JSON.stringify({ purpose }) }),
    onSuccess: (data) => client.setQueryData(key, data),
  });
  const data = ledger.data;
  if (!data?.purposes.length) return <p className="text-sm text-muted">{t`This space asks for no optional consents.`}</p>;
  const standing = (purpose: string) => data.consents.find((row) => row.purpose === purpose && !row.withdrawn_at);
  return <div className="grid gap-3">
    {data.notice_version ? <p className="text-sm text-muted">{t`Privacy notice version ${data.notice_version}`}</p> : null}
    {data.purposes.map((purpose) => <label key={purpose.key} className="flex min-h-11 items-start gap-3 text-sm">
      <input className="mt-1 h-4 w-4" type="checkbox" checked={Boolean(standing(purpose.key))} disabled={change.isPending}
        onChange={(event) => change.mutate({ purpose: purpose.key, give: event.target.checked })} />
      <span><span className="font-semibold text-ink">{purpose.label}</span>{purpose.description ? <span className="block text-muted">{purpose.description}</span> : null}</span>
    </label>)}
    {change.error ? <p role="alert" className="text-sm text-danger">{errorText(change.error)}</p> : null}
  </div>;
}

function ErasureRequest({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const key = ["member", "account", makerspaceId, "erasure"];
  const rows = useQuery({ queryKey: key, queryFn: () => memberRequest<Erasure[]>(`${base(makerspaceId)}/erasure-requests`) });
  const [note, setNote] = useState("");
  const ask = useMutation({ mutationFn: () => memberRequest<Erasure>(`${base(makerspaceId)}/erasure-requests`, { method: "POST", body: JSON.stringify({ note }) }),
    onSuccess: () => { setNote(""); void client.invalidateQueries({ queryKey: key }); } });
  const withdraw = useMutation({ mutationFn: (id: number) => memberRequest<Erasure>(`${base(makerspaceId)}/erasure-requests/${id}/withdraw`, { method: "POST", body: "{}" }),
    onSuccess: () => { void client.invalidateQueries({ queryKey: key }); } });
  const open = rows.data?.find((row) => row.status === "requested");
  return <div className="grid gap-3">
    <p className="text-sm text-muted">{t`Ask this space to erase what it holds about your membership. If staff approve, your membership here ends and your record, titles, profile and answers are erased. Payment records and the audit log are kept. Your account stays.`}</p>
    {rows.data?.map((row) => <p key={row.id} className="flex flex-wrap items-center gap-2 text-sm">
      <StatusPill tone={row.status === "approved" ? "success" : row.status === "rejected" ? "danger" : "warn"} label={erasureStatusLabel(row.status)} />
      {formatDate(row.created_at)}{row.decision_note ? ` · “${row.decision_note}”` : ""}
      {row.status === "requested" ? <button className="desk-button" type="button" disabled={withdraw.isPending} onClick={() => withdraw.mutate(row.id)}>{t`Withdraw`}</button> : null}
    </p>)}
    {!open ? <form className="grid gap-2" onSubmit={(event) => { event.preventDefault(); ask.mutate(); }}>
      <Field label={t`Anything staff should know? (optional)`}><textarea className="desk-input min-h-20" maxLength={1000} value={note} onChange={(event) => setNote(event.target.value)} /></Field>
      <div><button className="desk-button" type="submit" disabled={ask.isPending}>{ask.isPending ? t`Sending…` : t`Ask to erase my data`}</button></div>
    </form> : null}
    {ask.error ?? withdraw.error ? <p role="alert" className="text-sm text-danger">{errorText(ask.error ?? withdraw.error)}</p> : null}
  </div>;
}

/** X10 + X29: consents you gave and the per-space erasure request. */
export function MemberPrivacy({ makerspaceId, consentOn, erasureOn }: { makerspaceId: number; consentOn: boolean; erasureOn: boolean }) {
  return <div className="grid gap-8">
    {consentOn ? <section aria-label={t`Consents`}><h3 className="title-section mb-3">{t`Consents`}</h3><Consents makerspaceId={makerspaceId} /></section> : null}
    {erasureOn ? <section aria-label={t`Erase my data`}><h3 className="title-section mb-3">{t`Erase my data here`}</h3><ErasureRequest makerspaceId={makerspaceId} /></section> : null}
  </div>;
}
