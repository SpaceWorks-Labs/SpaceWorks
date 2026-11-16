import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Field } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { lifecycleApi } from "../membershipLifecycleApi";

type Row = { id: number; kind: string; state: string; invite_email?: string; user: { display_name?: string; username?: string } | null };
const errorText = (error: unknown) => (error instanceof StructuredApiError ? error.message : t`That did not work.`);

/** X11: approve or reject many join requests at once; each one is decided on its own. */
export function BulkDecideBar({ makerspaceId, rows, onDone }: { makerspaceId: number; rows: Row[]; onDone: () => void }) {
  const open = rows.filter((row) => row.kind === "request" && ["requested", "awaiting_vouches"].includes(row.state));
  const [selected, setSelected] = useState<number[]>([]);
  const [reason, setReason] = useState("");
  const decide = useMutation({
    mutationFn: (decision: "approve" | "reject") => lifecycleApi.bulkDecide(makerspaceId, selected, decision, reason.trim()),
    onSuccess: () => { setSelected([]); setReason(""); onDone(); },
  });
  if (!open.length) return null;
  const refused = decide.data?.filter((item) => !item.ok) ?? [];
  const toggle = (id: number) => setSelected((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);
  return <fieldset className="my-3 grid gap-2 rounded-xl border border-line p-3">
    <legend className="title-section px-1">{t`Decide several requests`}</legend>
    <div className="flex flex-wrap gap-3">{open.map((row) => <label key={row.id} className="flex min-h-11 items-center gap-2 text-sm">
      <input className="h-4 w-4" type="checkbox" checked={selected.includes(row.id)} onChange={() => toggle(row.id)} />
      {row.user?.display_name || row.user?.username || row.invite_email || t`Request #${row.id}`}
    </label>)}</div>
    <Field label={t`Reason for rejections (shown to the applicant)`}>
      <input className="desk-input" maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} />
    </Field>
    <div className="flex flex-wrap gap-2">
      <button className="desk-button-primary" type="button" disabled={!selected.length || decide.isPending} onClick={() => decide.mutate("approve")}>
        {t`Approve ${selected.length || ""}`}</button>
      <button className="desk-button" type="button" disabled={!selected.length || decide.isPending} onClick={() => decide.mutate("reject")}>
        {t`Reject ${selected.length || ""}`}</button>
    </div>
    {decide.data ? <p role="status" className="text-sm text-muted">
      {t`Done: ${decide.data.length - refused.length}. `}{refused.length ? t`Not changed: ${refused.length} (${[...new Set(refused.map((item) => item.code))].join(", ")}).` : ""}</p> : null}
    {decide.error ? <p role="alert" className="text-sm text-danger">{errorText(decide.error)}</p> : null}
  </fieldset>;
}
