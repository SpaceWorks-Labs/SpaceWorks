import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Modal } from "../../../components/ui";
import { useOpenIssue, type SubjectType } from "./repairsApi";
import { useSubjectOptions } from "./subjectsApi";

const KINDS: { value: SubjectType; label: string }[] = [
  { value: "machine", label: t`Machine` }, { value: "inventory_product", label: t`Inventory item` },
  { value: "bookable_space", label: t`Room` },
];

/** Staff open a repair job themselves (#102): it starts triaged, with its work order. */
export function OpenIssueDialog({ makerspaceId, onClose, onOpened }: {
  makerspaceId: number; onClose: () => void; onOpened: (id: number) => void;
}) {
  const open = useOpenIssue(makerspaceId);
  const [kind, setKind] = useState<SubjectType>("machine");
  const [subject, setSubject] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const { options, loading } = useSubjectOptions(makerspaceId, kind);
  const ready = !!subject && !!title.trim();
  return <Modal open title={t`New repair job`} onClose={onClose}>
    <form className="grid gap-3" onSubmit={event => {
      event.preventDefault();
      if (!ready) return;
      open.mutate({ subject_type: kind, subject_id: Number(subject), title: title.trim(), description: description.trim() },
        { onSuccess: issue => { onOpened(issue.id); onClose(); } });
    }}>
      <label className="eyebrow grid gap-1">{t`What needs repair`}<select className="desk-input" value={kind}
        onChange={event => { setKind(event.target.value as SubjectType); setSubject(""); }}>
        {KINDS.map(row => <option key={row.value} value={row.value}>{row.label}</option>)}</select></label>
      <label className="eyebrow grid gap-1">{t`Which one`}<select className="desk-input" value={subject} onChange={event => setSubject(event.target.value)}>
        <option value="">{loading ? t`Loading…` : t`Choose`}</option>
        {options.map(row => <option key={row.id} value={row.id}>{row.label}</option>)}</select></label>
      <label className="eyebrow grid gap-1">{t`Problem`}<input className="desk-input" maxLength={200} value={title}
        onChange={event => setTitle(event.target.value)} /></label>
      <label className="eyebrow grid gap-1">{t`Details (optional)`}<textarea className="desk-input min-h-24" value={description}
        onChange={event => setDescription(event.target.value)} /></label>
      {open.error ? <p role="alert" className="text-sm text-danger">{open.error.message}</p> : null}
      <div className="flex flex-wrap justify-end gap-2 border-t border-line pt-3">
        <button type="button" className="desk-button-ghost" onClick={onClose}>{t`Cancel`}</button>
        <button type="submit" className="desk-button-primary" disabled={!ready || open.isPending}>{open.isPending ? t`Opening…` : t`Open repair job`}</button>
      </div>
    </form>
  </Modal>;
}
