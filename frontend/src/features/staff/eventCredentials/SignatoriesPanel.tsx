import { useEffect, useState } from "react";
import { CheckCircle2, Clock, PenLine, Trash2, Upload } from "lucide-react";
import { eventErrorText } from "../eventUi";
import { CERTIFICATE_KINDS } from "./designer/samples";
import { useSignatories, useSignatoryCandidates, useUploadSignature, type Signatory, type SignatoryInput } from "./signatoryApi";

function SignatoryForm({ eventId, slot, row, approvalRequired, onSave, onRemove, busy }: { eventId: number; slot: number;
  row?: Signatory; approvalRequired: boolean; onSave: (input: SignatoryInput) => void; onRemove: () => void; busy: boolean }) {
  const [draft, setDraft] = useState<SignatoryInput>({ slot, name: "", title: "", member_id: null, signature_artwork_id: null });
  const [account, setAccount] = useState<string | null>(null);
  const [term, setTerm] = useState("");
  const candidates = useSignatoryCandidates(eventId, term);
  const upload = useUploadSignature(eventId);
  useEffect(() => {
    setDraft({ slot, name: row?.name ?? "", title: row?.title ?? "", member_id: row?.member_id ?? null, signature_artwork_id: row?.signature_artwork_id ?? null });
    setAccount(row?.member_name ?? null);
  }, [row, slot]);
  const id = `signatory-${slot}`;
  return <fieldset className="grid gap-3 rounded-control border border-line p-3" aria-labelledby={`${id}-legend`}>
    <legend id={`${id}-legend`} className="px-1 font-semibold text-ink">Signatory {slot}</legend>
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="grid gap-1 text-sm">Printed name<input className="desk-input" maxLength={120} value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
      <label className="grid gap-1 text-sm">Title<input className="desk-input" maxLength={120} value={draft.title} placeholder="Director" onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label>
    </div>
    <div className="grid gap-2">
      <span className="text-sm">Approving account{approvalRequired ? " (required while approval is on)" : " (optional)"}</span>
      {account ? <div className="flex flex-wrap items-center gap-2"><span className="font-semibold text-ink">{account}</span>
        <button type="button" className="desk-button min-h-11" onClick={() => { setAccount(null); setDraft({ ...draft, member_id: null }); }}>Change account</button></div>
        : <><input className="desk-input" type="search" aria-label={`Find the account for signatory ${slot}`} placeholder="Name of a member or staff" value={term} onChange={(event) => setTerm(event.target.value)} />
          {candidates.data?.length ? <ul className="grid gap-1" aria-label="Matching accounts">{candidates.data.map((person) => <li key={person.id}>
            <button type="button" className="desk-button min-h-11 w-full justify-start" onClick={() => { setAccount(person.name); setDraft({ ...draft, member_id: person.id }); setTerm(""); }}>{person.name}</button></li>)}</ul>
            : term.trim().length >= 2 && candidates.isSuccess ? <p className="text-sm text-muted">No active account of this space matches.</p> : null}</>}
    </div>
    <label className="grid gap-1 text-sm"><span className="inline-flex items-center gap-2"><Upload size={16} aria-hidden="true" />Signature image (PNG, JPEG or WebP, up to 2 MB; a transparent PNG prints best)</span>
      <input className="desk-input" type="file" accept="image/png,image/jpeg,image/webp" disabled={upload.isPending} onChange={(event) => {
        const file = event.target.files?.[0]; event.target.value = "";
        if (file) upload.mutate(file, { onSuccess: (art) => setDraft((current) => ({ ...current, signature_artwork_id: art.id })) });
      }} /></label>
    {draft.signature_artwork_id ? <p className="text-sm text-success-ink">Signature image ready{row?.signature_artwork_id === draft.signature_artwork_id ? "" : " (save to use it)"}.</p> : <p className="text-sm text-muted">No signature image: the name and title print above a signing line.</p>}
    {upload.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(upload.error)}</p> : null}
    <div className="flex flex-wrap gap-2">
      <button type="button" className="desk-button-primary" disabled={busy || !draft.name.trim() || upload.isPending} onClick={() => onSave(draft)}>Save signatory {slot}</button>
      {row ? <button type="button" className="desk-button-danger" disabled={busy} onClick={onRemove}><Trash2 size={16} aria-hidden="true" />Remove</button> : null}
    </div>
  </fieldset>;
}

/** Up to three signatories, and the optional rule that each must approve a design before it is issued. */
export function SignatoriesPanel({ eventId }: { eventId: number }) {
  const { query, save, remove, policy } = useSignatories(eventId);
  const busy = save.isPending || remove.isPending || policy.isPending;
  const error = query.error || save.error || remove.error || policy.error;
  const state = query.data;
  const kindLabel = (kind: string) => kind ? CERTIFICATE_KINDS.find((row) => row.value === kind)?.label ?? kind : "Default design";
  return <details className="rounded-control border border-line p-3">
    <summary className="min-h-11 cursor-pointer font-semibold text-ink"><span className="inline-flex items-center gap-2"><PenLine size={18} aria-hidden="true" />Signatories</span></summary>
    <div className="mt-3 grid gap-4">
      <p className="text-sm text-muted">Add up to three people whose signature prints on certificates, then place a signature layer in the design. Their name, title and signature are fixed into each certificate when it is issued.</p>
      {state ? <label className="flex min-h-11 items-start gap-3 text-sm">
        <input type="checkbox" className="mt-1 h-5 w-5" checked={state.approval_required} disabled={busy} onChange={(event) => policy.mutate(event.target.checked)} />
        <span><span className="font-semibold text-ink">Signatories must approve the design.</span> Certificates that print a signature wait until that signatory approves the design they appear on. Each signatory gets a notice and approves from their member area.</span></label> : null}
      {[1, 2, 3].map((slot) => <SignatoryForm key={slot} eventId={eventId} slot={slot} row={state?.signatories.find((row) => row.slot === slot)}
        approvalRequired={Boolean(state?.approval_required)} busy={busy} onSave={(input) => save.mutate(input)} onRemove={() => remove.mutate(slot)} />)}
      {state?.approval_required && state.designs.length ? <section aria-label="Design approvals" className="grid gap-2">
        <h4 className="font-semibold text-ink">Approvals</h4>
        <ul className="grid gap-2">{state.designs.map((design) => <li key={design.template_revision_id} className="rounded-control border border-line p-3 text-sm">
          <p className="font-semibold text-ink">{kindLabel(design.certificate_kind)} · revision {design.template_revision_id}</p>
          <ul className="mt-1 flex flex-wrap gap-3">{design.slots.map((slot) => <li key={slot.slot} className={`inline-flex items-center gap-1 ${slot.approved ? "text-success-ink" : "text-warn-ink"}`}>
            {slot.approved ? <CheckCircle2 size={16} aria-hidden="true" /> : <Clock size={16} aria-hidden="true" />}Signatory {slot.slot}: {slot.approved ? "approved" : "waiting"}</li>)}</ul>
        </li>)}</ul></section> : null}
      {error ? <p role="alert" className="text-sm text-danger">{eventErrorText(error)}</p> : null}
    </div>
  </details>;
}
