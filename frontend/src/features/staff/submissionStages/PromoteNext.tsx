import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ConfirmDialog, ErrorText, Field } from "../../../components/ui";
import { usePromoteNext } from "./api";
import { stageErrorMessage } from "./stageDraft";
import type { Shortlist } from "./types";

/** S12: a shortlisted team withdrew; add the next ranked team(s) from the source round (ties together). */
export function PromoteNext({ eventId, stageId, shortlist }: { eventId: number; stageId: number; shortlist: Shortlist }) {
  const promote = usePromoteNext(eventId, stageId);
  const live = new Set(shortlist.stage_entries.map(row => row.submission_id));
  const gone = (shortlist.current?.entries ?? []).filter(entry => !live.has(entry.submission_id));
  const [chosen, setChosen] = useState(""); const [confirm, setConfirm] = useState(false);
  if (!gone.length) return <p className="text-sm text-muted">{t`If a shortlisted team withdraws, you can promote the next ranked team here.`}</p>;
  return <div className="grid gap-3 rounded-2xl border border-line p-3">
    <Field label={t`Withdrawn shortlisted team`} hint={t`The next ranked team from the same judging round takes the place; tied teams come in together.`}>
      <select className="desk-input min-h-11" value={chosen} onChange={e => setChosen(e.target.value)}><option value="">{t`Choose a team…`}</option>
        {gone.map(entry => <option key={entry.submission_id} value={entry.submission_id}>{entry.title || t`Team ${entry.team_id}`}</option>)}</select></Field>
    <button type="button" className="desk-button min-h-11 justify-self-start" disabled={!chosen || promote.isPending} onClick={() => setConfirm(true)}>{t`Promote next team`}</button>
    <ConfirmDialog open={confirm} title={t`Promote the next team?`} confirmLabel={t`Promote and publish`} pending={promote.isPending}
      message={t`The next ranked team (or every team tied at that rank) joins the list, which is published at once. Teams already on it keep their place.`}
      onCancel={() => setConfirm(false)} onConfirm={() => promote.mutate(Number(chosen), { onSuccess: () => { setConfirm(false); setChosen(""); } })} />
    {promote.error ? <ErrorText message={stageErrorMessage(promote.error)} /> : null}
  </div>;
}
