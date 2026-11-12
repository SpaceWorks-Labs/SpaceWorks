import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Modal } from "../../components/ui";
import { memberRequest } from "../../lib/api";
import { uploadToStorage, type PrintUpload } from "../printing/publicApi";
import { BoxArt } from "../../components/BoxSpinner";

/** Where the report comes from: the member's own loan, booking, machine job or machine session (#103, 220(d)2). */
export type ReportSource = { makerspace_id?: number; makerspace_slug?: string }
  & ({ loan_id: number } | { booking_token: string } | { machine_job_id: number } | { machine_session_id: number });
type LoanItem = { product_id: number; asset_id: number | null; name: string };

async function uploadPhoto(source: ReportSource, file: File) {
  const space = { makerspace_id: source.makerspace_id, makerspace_slug: source.makerspace_slug };
  const staged = await memberRequest<{ photo_token: string; upload: PrintUpload; max_bytes: number }>("/member/issues/photos",
    { method: "POST", body: JSON.stringify({ ...space, content_type: file.type }) });
  if (file.size > staged.max_bytes) throw new Error(t`${file.name} is too large.`);
  await uploadToStorage({ ...staged.upload, fields: staged.upload.fields ?? {} }, file);
  return staged.photo_token;
}

/**
 * "Report a problem" on something the member used. The space's manager is told; the
 * member gets an email when it is fixed. Shown only while the area's issue reporting is on.
 */
export function ReportProblem({ source, label = t`Report a problem` }: { source: ReportSource; label?: string }) {
  const [open, setOpen] = useState(false);
  return <>
    <button type="button" className="desk-button-ghost min-h-11" onClick={() => setOpen(true)}>{label}</button>
    {open ? <ReportDialog source={source} onClose={() => setOpen(false)} /> : null}
  </>;
}

function ReportDialog({ source, onClose }: { source: ReportSource; onClose: () => void }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [item, setItem] = useState("");
  const [state, setState] = useState<{ busy: boolean; error: string; done: boolean }>({ busy: false, error: "", done: false });
  const loanId = "loan_id" in source ? source.loan_id : null;
  const items = useQuery({ queryKey: ["member", "issue-loan-items", loanId], enabled: loanId !== null,
    queryFn: () => memberRequest<LoanItem[]>(`/member/issues/loan-items?makerspace=${source.makerspace_id}&loan=${loanId}`) });
  const choices = items.data ?? [];
  async function submit() {
    setState({ busy: true, error: "", done: false });
    try {
      const photos = await Promise.all(files.map(file => uploadPhoto(source, file)));
      const chosen = choices.find(row => `${row.product_id}:${row.asset_id ?? ""}` === item) ?? (choices.length === 1 ? choices[0] : undefined);
      await memberRequest("/member/issues", { method: "POST", body: JSON.stringify({ ...source, title: title.trim(),
        description: description.trim(), photos, ...(chosen ? chosen.asset_id ? { asset_id: chosen.asset_id } : { product_id: chosen.product_id } : {}) }) });
      setState({ busy: false, error: "", done: true });
    } catch (problem) {
      setState({ busy: false, error: problem instanceof Error ? problem.message : t`Couldn't send the report. Try again.`, done: false });
    }
  }
  const ready = !!title.trim() && !!description.trim() && (choices.length <= 1 || !!item);
  return <Modal open title={t`Report a problem`} onClose={onClose}>
    {state.done ? <div className="grid gap-3"><p role="status">{t`Thanks. The space has your report and will email you when it is fixed.`}</p>
      <div className="flex justify-end"><button type="button" className="desk-button-primary" onClick={onClose}>{t`Done`}</button></div></div>
      : <form className="grid gap-3" onSubmit={event => { event.preventDefault(); if (ready) void submit(); }}>
        {choices.length > 1 ? <label className="eyebrow grid gap-1">{t`Which item`}<select className="desk-input" value={item}
          onChange={event => setItem(event.target.value)}><option value="">{t`Choose`}</option>
          {choices.map(row => <option key={`${row.product_id}:${row.asset_id ?? ""}`} value={`${row.product_id}:${row.asset_id ?? ""}`}>{row.name}</option>)}
        </select></label> : null}
        <label className="eyebrow grid gap-1">{t`What's wrong`}<input className="desk-input" maxLength={200} value={title}
          onChange={event => setTitle(event.target.value)} /></label>
        <label className="eyebrow grid gap-1">{t`Details`}<textarea className="desk-input min-h-24" maxLength={4000} value={description}
          onChange={event => setDescription(event.target.value)} /></label>
        <label className="eyebrow grid gap-1">{t`Photos (optional)`}<input className="desk-input" type="file" accept="image/jpeg,image/png,image/webp"
          multiple onChange={event => setFiles(Array.from(event.target.files ?? []).slice(0, 6))} /></label>
        {state.error ? <p role="alert" className="text-sm text-danger">{state.error}</p> : null}
        <div className="flex flex-wrap justify-end gap-2 border-t border-line pt-3">
          <button type="button" className="desk-button-ghost" onClick={onClose}>{t`Cancel`}</button>
          <button type="submit" className="desk-button-primary" disabled={!ready || state.busy}>{state.busy ? <><BoxArt size={16} mono />{t`Sending…`}</> : t`Send report`}</button>
        </div>
      </form>}
  </Modal>;
}
