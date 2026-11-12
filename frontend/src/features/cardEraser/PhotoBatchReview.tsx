import { t } from "@lingui/core/macro";

import { StatusPill } from "../../components/ui";
import { eraserErrorText, type Batch, type BatchItem } from "./api";

type Choose = (item: BatchItem, body: { holder_id?: number | null; decision?: BatchItem["decision"] }) => void;

const statusLabel = (status: BatchItem["status"]) => status === "matched" ? t`Matched` : status === "ambiguous" ? t`Pick one`
  : status === "has_photo" ? t`Has a photo` : t`No match`;
const tone = (status: BatchItem["status"]) => status === "matched" ? "success" : status === "unmatched" ? "danger" : "warn";
const problem = (code: string) => code === "duplicate_file" ? t`Another photo already goes to this person.`
  : code === "unreadable_image" ? t`This file isn't a readable photo.` : code ? eraserErrorText(code) : "";

/** The review table: each file, who it matched, and what will happen. Nothing is applied until staff confirm. */
export function PhotoBatchReview({ batch, disabled, onChoose }: { batch: Batch; disabled: boolean; onChoose: Choose }) {
  return <div className="overflow-x-auto"><table className="w-full min-w-[40rem] text-left text-sm">
    <caption className="sr-only">{t`Photos and the people they match`}</caption>
    <thead><tr className="border-b border-line text-muted">
      <th scope="col" className="py-2 pr-3">{t`Photo`}</th><th scope="col" className="pr-3">{t`File`}</th>
      <th scope="col" className="pr-3">{t`Match`}</th><th scope="col">{t`Action`}</th></tr></thead>
    <tbody>{batch.items.map((item) => <tr key={item.id} className="border-b border-line align-top">
      <td className="py-2 pr-3">{item.thumbnail_url
        ? <img src={item.thumbnail_url} alt="" className="h-14 w-11 rounded-control border border-line object-cover" /> : null}</td>
      <td className="pr-3 [overflow-wrap:anywhere]">{item.filename}
        {problem(item.error_code) ? <p className="text-xs text-muted">{problem(item.error_code)}</p> : null}</td>
      <td className="pr-3"><StatusPill tone={tone(item.status)} label={statusLabel(item.status)} />
        {item.holder_name ? <p className="mt-1">{item.holder_name}</p> : null}</td>
      <td><Row item={item} holders={batch.holders} disabled={disabled} onChoose={onChoose} /></td></tr>)}</tbody>
  </table></div>;
}

function Row({ item, holders, disabled, onChoose }: { item: BatchItem; holders: Batch["holders"]; disabled: boolean; onChoose: Choose }) {
  const choices = item.status === "ambiguous" ? item.candidates : holders;
  const label = (person: Batch["holders"][number]) => person.number ? `${person.name} (${person.number})` : person.name;
  const select = (item.status === "ambiguous" || item.status === "unmatched") && item.error_code !== "unreadable_image"
    ? <select className="desk-input min-h-11" aria-label={t`Choose the person for ${item.filename}`} disabled={disabled}
      value={item.holder_id ?? ""} onChange={(event) => onChoose(item, { holder_id: event.target.value ? Number(event.target.value) : null })}>
      <option value="">{t`Skip this photo`}</option>
      {choices.map((person) => <option key={person.id} value={person.id}>{label(person)}</option>)}</select> : null;
  const decide = item.holder_id && item.error_code !== "duplicate_file"
    ? <select className="desk-input min-h-11" aria-label={t`What to do with ${item.filename}`} disabled={disabled}
      value={item.decision === "apply" ? (item.status === "has_photo" ? "replace" : "apply") : item.decision}
      onChange={(event) => onChoose(item, { decision: event.target.value as BatchItem["decision"] })}>
      {item.status === "has_photo" ? <><option value="keep">{t`Keep their current photo`}</option><option value="replace">{t`Replace it`}</option></>
        : <option value="apply">{t`Use this photo`}</option>}
      <option value="skip">{t`Skip`}</option></select> : null;
  return <div className="grid gap-2">{select}{decide}</div>;
}
