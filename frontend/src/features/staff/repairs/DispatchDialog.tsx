import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Modal } from "../../../components/ui";
import { CHANNEL_LABELS, type Channel, type Technician } from "../technicians/techniciansApi";
import { useIssueStep, type IssueDetail } from "./repairsApi";

/**
 * Pick the technicians to send this issue to (#98); the area's defaults come pre-ticked.
 * Each goes out by email plus every chat channel they chose AND opted in to. Notify only:
 * nothing in the message asks them to click anything.
 */
export function DispatchDialog({ issue, technicians, onClose }: { issue: IssueDetail; technicians: Technician[]; onClose: () => void }) {
  const step = useIssueStep(issue.id);
  const live = technicians.filter(row => !row.is_archived);
  const [picked, setPicked] = useState<number[]>(issue.default_contact_ids.filter(id => live.some(row => row.id === id)));
  const [note, setNote] = useState("");
  const toggle = (id: number) => setPicked(current => current.includes(id) ? current.filter(row => row !== id) : [...current, id]);
  const reach = (row: Technician) => (row.channels as Channel[]).filter(channel => row.consent[channel]).map(channel => CHANNEL_LABELS[channel]);
  return <Modal open title={t`Send to technicians`} onClose={onClose}>
    <form className="grid gap-3" onSubmit={event => {
      event.preventDefault();
      if (picked.length) step.mutate({ step: "dispatch", body: { contact_ids: picked, note: note.trim() } }, { onSuccess: onClose });
    }}>
      {live.length ? <fieldset className="grid gap-2"><legend className="eyebrow mb-1">{t`Technicians`}</legend>
        {live.map(row => <label key={row.id} className="flex min-h-11 items-start gap-3 rounded-xl border border-line p-3 text-sm">
          <input type="checkbox" className="mt-1" checked={picked.includes(row.id)} onChange={() => toggle(row.id)} />
          <span><span className="font-semibold">{row.name}</span>
            <span className="block text-muted">{row.kind === "in_house" ? t`In-house` : t`Contractor`} · {reach(row).join(", ") || t`No channel yet`}</span></span>
        </label>)}
      </fieldset> : <p className="text-sm text-muted">{t`No technicians yet. Add them under Technicians.`}</p>}
      <label className="eyebrow grid gap-1">{t`Note for them (optional)`}<textarea className="desk-input min-h-20" maxLength={500}
        value={note} onChange={event => setNote(event.target.value)} /></label>
      <p className="text-sm text-muted">{t`Chat channels need the technician's one-time opt-in. Every send is recorded on this issue.`}</p>
      {step.error ? <p role="alert" className="text-sm text-danger">{step.error.message}</p> : null}
      <div className="flex flex-wrap justify-end gap-2 border-t border-line pt-3">
        <button type="button" className="desk-button-ghost" onClick={onClose}>{t`Cancel`}</button>
        <button type="submit" className="desk-button-primary" disabled={!picked.length || step.isPending}>
          {step.isPending ? t`Sending…` : `Send to ${picked.length || ""} technician${picked.length === 1 ? "" : "s"}`.replace("  ", " ")}</button>
      </div>
    </form>
  </Modal>;
}
