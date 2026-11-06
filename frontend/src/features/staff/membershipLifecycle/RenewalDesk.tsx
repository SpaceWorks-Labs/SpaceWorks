import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EmptyState, Field, ListRow, Modal, StatusPill } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { STANDING_LABELS, lifecycleApi, lifecycleKeys, standingTone, type WorklistRow } from "../membershipLifecycleApi";

const errorText = (error: unknown) => (error instanceof StructuredApiError ? error.message : t`That did not work. Try again.`);
const day = (value: string) => new Date(value).toLocaleDateString(formatLocale());

/** The renewal worklist (G16): who is due, a once-a-day nudge, and extend-by-hand (X17). */
export function RenewalDesk({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const worklist = useQuery({ queryKey: lifecycleKeys.worklist(makerspaceId), queryFn: () => lifecycleApi.worklist(makerspaceId) });
  const [selected, setSelected] = useState<number[]>([]);
  const [extending, setExtending] = useState<WorklistRow | null>(null);
  const [days, setDays] = useState("30");
  const [reason, setReason] = useState("");
  const refresh = () => client.invalidateQueries({ queryKey: lifecycleKeys.worklist(makerspaceId) });
  const remind = useMutation({ mutationFn: () => lifecycleApi.remind(makerspaceId, selected), onSuccess: () => { setSelected([]); void refresh(); } });
  const extend = useMutation({
    mutationFn: (row: WorklistRow) => lifecycleApi.extend(row.id, { reason: reason.trim(), days: Number(days) }),
    onSuccess: () => { setExtending(null); setReason(""); void refresh(); },
  });
  const toggle = (id: number) => setSelected((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);
  const rows = worklist.data ?? [];
  return <section aria-label={t`Renewal desk`} className="grid gap-3">
    <p className="text-sm text-muted">{t`Members whose term ends in the next 30 days, who are in grace, or who lapsed recently. A reminder goes out at most once a day per member.`}</p>
    <div className="flex flex-wrap items-center gap-2">
      <button className="desk-button-primary" type="button" disabled={!selected.length || remind.isPending} onClick={() => remind.mutate()}>
        {remind.isPending ? t`Sending…` : `Remind ${selected.length || ""} selected`.replace("  ", " ")}
      </button>
      {remind.data ? <p role="status" className="text-sm text-muted">{t`Sent ${remind.data.sent.length}; ${remind.data.skipped.length} already reminded today or not due.`}</p> : null}
    </div>
    {worklist.isLoading ? <p className="text-sm text-muted">{t`Loading the worklist…`}</p> : null}
    {worklist.isError ? <p role="alert" className="text-sm text-danger">{errorText(worklist.error)}</p> : null}
    {worklist.isSuccess && !rows.length ? <EmptyState message={t`Nobody is due for renewal right now.`} /> : null}
    {rows.map((row) => <ListRow key={row.id} title={row.name || row.email} identity={{ kind: "avatar", name: row.name || row.email, seed: String(row.id) }}
      meta={<>{t`${row.member_number ? `${row.member_number} · ` : ""}${row.desk.plan_name} · ends ${day(row.desk.ends_at)}`}</>}
      right={<div className="flex flex-wrap items-center gap-2">
        <StatusPill tone={standingTone(row.desk.standing)} label={STANDING_LABELS[row.desk.standing] ?? row.desk.standing} />
        {row.desk.reminded_today ? <StatusPill tone="neutral" label={t`Reminded today`} /> : null}
        <label className="flex min-h-11 items-center gap-2 text-sm">
          <input className="h-4 w-4" type="checkbox" checked={selected.includes(row.id)} disabled={row.desk.reminded_today}
            onChange={() => toggle(row.id)} aria-label={t`Select ${row.name || row.email} for a reminder`} />{t`Remind`}</label>
        <button className="desk-button" type="button" onClick={() => { extend.reset(); setExtending(row); }}>{t`Extend`}</button>
      </div>} />)}
    {remind.error ? <p role="alert" className="text-sm text-danger">{errorText(remind.error)}</p> : null}
    <Modal open={Boolean(extending)} onClose={() => { if (!extend.isPending) setExtending(null); }} title={t`Extend ${extending?.name || "membership"}`}
      footer={<div className="flex flex-wrap justify-end gap-2">
        <button className="desk-button" type="button" onClick={() => setExtending(null)} disabled={extend.isPending}>{t`Cancel`}</button>
        <button className="desk-button-primary" type="button" disabled={extend.isPending || !reason.trim() || !/^[1-9]\d*$/.test(days)}
          onClick={() => extending && extend.mutate(extending)}>{extend.isPending ? t`Saving…` : t`Extend`}</button>
      </div>}>
      <div className="grid gap-3">
        <Field label={t`Extend by (days)`}><input className="desk-input" inputMode="numeric" value={days} onChange={(event) => setDays(event.target.value)} /></Field>
        <Field label={t`Why?`} hint={t`Kept in the membership history and the audit log.`}>
          <textarea className="desk-input min-h-20" maxLength={500} value={reason} onChange={(event) => setReason(event.target.value)} />
        </Field>
        {extend.error ? <p role="alert" className="text-sm text-danger">{errorText(extend.error)}</p> : null}
      </div>
    </Modal>
  </section>;
}
