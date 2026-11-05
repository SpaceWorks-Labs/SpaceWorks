import { Field } from "../../../components/ui";
import { deadlineText } from "../../events/stageTime";
import { CustomFieldsEditor } from "./CustomFieldsEditor";
import { cleanForMode, fromInput, modeAllows, toInput } from "./stageDraft";
import type { ContentMode, StageDraft, StagePlan } from "./types";

const MODES: Record<ContentMode, string> = { files_and_links: "Files and links", files_only: "Files only",
  links_only: "Links only", presentation: "Presentation (nothing to upload; a deck is optional)" };
const MB = 1024 * 1024;

type Props = { stage: StageDraft; index: number; last: boolean; plan: StagePlan; onChange: (next: StageDraft) => void };

/** One stage's window and requirements. Controls a mode cannot use are not shown (the server refuses them). */
export function StageFields({ stage, index, last, plan, onChange }: Props) {
  const set = (patch: Partial<StageDraft>) => onChange({ ...stage, ...patch });
  const allow = modeAllows(stage.content_mode);
  const label = stage.name || `stage ${index + 1}`;
  const number = (value: string) => (value.trim() === "" ? null : Number(value));
  return <div className="grid gap-4">
    <div className="grid gap-3 md:grid-cols-2">
      <Field label="Stage name"><input className="desk-input min-h-11" maxLength={120} required value={stage.name} onChange={e => set({ name: e.target.value })} /></Field>
      <Field label="What teams submit"><select className="desk-input min-h-11" value={stage.content_mode}
        onChange={e => onChange({ ...stage, ...cleanForMode({ ...stage, content_mode: e.target.value as ContentMode }) })}>
        {Object.entries(MODES).map(([key, text]) => <option key={key} value={key}>{text}</option>)}</select></Field>
    </div>
    <Field label="Description for teams"><textarea className="desk-input min-h-20" maxLength={2000} value={stage.description} onChange={e => set({ description: e.target.value })} /></Field>
    <fieldset className="grid gap-3 md:grid-cols-2"><legend className="font-semibold text-ink">Window</legend>
      {(["opens_at", "deadline"] as const).map(key => <Field key={key} label={key === "opens_at" ? "Opens (UTC)" : last ? "Deadline (UTC, empty = event end)" : "Deadline (UTC)"}
        hint={stage[key] ? deadlineText(stage[key]!, plan.timezone) : undefined}>
        <input className="desk-input min-h-11" type="datetime-local" value={toInput(stage[key])} onChange={e => set({ [key]: fromInput(e.target.value) })} /></Field>)}
      <Field label="Grace minutes"><input className="desk-input min-h-11" type="number" min={0} max={1440} value={stage.grace_minutes} onChange={e => set({ grace_minutes: Number(e.target.value) })} /></Field>
      <Field label="Late work"><select className="desk-input min-h-11" value={stage.late_policy} onChange={e => set({ late_policy: e.target.value as StageDraft["late_policy"] })}>
        <option value="reject">Refuse late submissions</option><option value="accept_flagged">Accept and flag late submissions</option></select></Field>
      <Field label="Resubmitting"><select className="desk-input min-h-11" value={stage.resubmission} onChange={e => set({ resubmission: e.target.value as StageDraft["resubmission"] })}>
        <option value="until_deadline">Teams may resubmit until the deadline</option><option value="once">The first submission is final</option></select></Field>
      {index > 0 ? <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={stage.requires_previous} onChange={e => set({ requires_previous: e.target.checked })} />Only teams that submitted the previous stage</label> : null}
    </fieldset>
    <fieldset className="grid gap-3 md:grid-cols-2"><legend className="font-semibold text-ink">Requirements</legend>
      {allow.minFiles ? <Field label="Fewest files"><input className="desk-input min-h-11" type="number" min={0} max={100} value={stage.min_files} onChange={e => set({ min_files: Number(e.target.value) })} /></Field> : null}
      {allow.files ? <Field label="Most files (empty = up to 100)"><input className="desk-input min-h-11" type="number" min={1} max={100} value={stage.max_files ?? ""} onChange={e => set({ max_files: number(e.target.value) })} /></Field> : null}
      {allow.files ? <Field label="Largest file in MB (empty = the type's limit)"><input className="desk-input min-h-11" type="number" min={1}
        value={stage.max_bytes_per_file ? Math.round(stage.max_bytes_per_file / MB) : ""} onChange={e => set({ max_bytes_per_file: e.target.value ? Number(e.target.value) * MB : null })} /></Field> : null}
      {allow.links ? <Field label="Most links (empty = up to 30)"><input className="desk-input min-h-11" type="number" min={1} max={30} value={stage.max_links ?? ""} onChange={e => set({ max_links: number(e.target.value) })} /></Field> : null}
    </fieldset>
    {allow.requiredKinds ? <Choices legend="Required link kinds" options={plan.link_kinds} value={stage.required_link_kinds} onChange={v => set({ required_link_kinds: v })} /> : null}
    {allow.files ? <Choices legend="Accepted file types (none ticked = every type)" options={plan.families} value={stage.accepted_families} onChange={v => set({ accepted_families: v })} /> : null}
    {allow.links ? <Choices legend="Allowed video hosts for video links (none ticked = any host)" options={plan.video_hosts} value={stage.video_hosts} onChange={v => set({ video_hosts: v })} /> : null}
    <CustomFieldsEditor label={label} value={stage.custom_fields} onChange={custom_fields => set({ custom_fields })} />
    {!last ? <div className="grid gap-3 md:grid-cols-2">
      <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={stage.shortlist_after} onChange={e => set({ shortlist_after: e.target.checked })} />End with a shortlist: only chosen teams continue</label>
      {stage.shortlist_after ? <Field label="Shortlist name"><input className="desk-input min-h-11" maxLength={60} placeholder="Shortlist" value={stage.shortlist_label} onChange={e => set({ shortlist_label: e.target.value })} /></Field> : null}
    </div> : null}
  </div>;
}

function Choices({ legend, options, value, onChange }: { legend: string; options: string[]; value: string[]; onChange: (next: string[]) => void }) {
  return <fieldset className="flex flex-wrap gap-x-5"><legend className="mb-1 w-full font-semibold text-ink">{legend}</legend>
    {options.map(option => <label key={option} className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={value.includes(option)}
      onChange={e => onChange(e.target.checked ? [...value, option] : value.filter(item => item !== option))} />{option.replace(/[-_]/g, " ")}</label>)}
  </fieldset>;
}
