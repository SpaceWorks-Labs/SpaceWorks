import { ExternalLink, Plus, Trash2 } from "lucide-react";
import { Field } from "../../../components/ui";
import type { ProjectLink } from "./types";

const kinds: ProjectLink["kind"][] = ["repo", "demo", "video", "slides", "cad", "pcb", "firmware", "other"];
export function LinkEditor({ value, onChange, disabled = false }: {
  value: ProjectLink[]; onChange: (value: ProjectLink[]) => void; disabled?: boolean;
}) {
  const update = (index: number, patch: Partial<ProjectLink>) => onChange(value.map((link, i) => i === index ? { ...link, ...patch } : link));
  return <fieldset className="grid gap-4" disabled={disabled}>
    <legend className="text-lg font-semibold text-ink">Project links</legend>
    <p className="text-sm text-muted">Add HTTPS links to your code, demonstration or maker files. Each stays private unless you choose to share it.</p>
    {value.map((link, index) => <div key={index} className="grid gap-3 rounded-xl border border-line p-4">
      <Field label={`Link ${index + 1} type`}><select className="desk-input min-h-11" value={link.kind}
        onChange={event => update(index, { kind: event.target.value as ProjectLink["kind"] })}>
        {kinds.map(kind => <option key={kind} value={kind}>{kind}</option>)}</select></Field>
      <Field label={`Link ${index + 1} URL`} hint="HTTPS only. Links open in a new tab."><input className="desk-input min-h-11" type="url"
        maxLength={2048} value={link.url} onChange={event => update(index, { url: event.target.value })} /></Field>
      <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={link.public_requested}
        onChange={event => update(index, { public_requested: event.target.checked })} />Allow this link in the published project gallery</label>
      <div className="flex flex-wrap gap-3">
        {/^https:\/\//.test(link.url) && !/[\s\\]/.test(link.url) ? <a className="desk-button min-h-11 gap-2" href={link.url}
          target="_blank" rel="noopener noreferrer"><ExternalLink aria-hidden size={20} />Open link {index + 1}</a> : null}
        <button type="button" className="desk-button min-h-11 gap-2" onClick={() => onChange(value.filter((_, i) => i !== index))}>
          <Trash2 aria-hidden size={20} />Remove link {index + 1}</button>
      </div>
    </div>)}
    <button type="button" className="desk-button min-h-11 gap-2 justify-self-start" disabled={value.length >= 30}
      onClick={() => onChange([...value, { kind: "repo", url: "", public_requested: false }])}>
      <Plus aria-hidden size={20} />Add a link</button>
  </fieldset>;
}
