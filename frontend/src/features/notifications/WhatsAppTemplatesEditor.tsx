import { StatusPill } from "../../components/ui";
import type { WhatsAppTemplate } from "./channelsApi";

const AUDIENCES: { key: WhatsAppTemplate["audience"]; label: string }[] = [
  { key: "member", label: "Members" }, { key: "requester", label: "Requesters" }, { key: "staff", label: "Staff" },
];
const blank: WhatsAppTemplate = { event: "", audience: "member", locale: "en", template_name: "", variables: [] };

/**
 * Event -> approved template bindings, shared by the Twilio and Meta providers. Outside the
 * 24-hour reply window WhatsApp only delivers approved templates, so an event with no
 * binding is not sent there. Approval is set by the provider, never by this form.
 */
export function WhatsAppTemplatesEditor({ templates, disabled, onChange }: {
  templates: WhatsAppTemplate[]; disabled: boolean; onChange: (next: WhatsAppTemplate[]) => void;
}) {
  const update = (index: number, patch: Partial<WhatsAppTemplate>) =>
    onChange(templates.map((row, at) => at === index ? { ...row, ...patch, approved: undefined } : row));
  return <fieldset className="grid min-w-0 gap-3 rounded-lg border border-line p-3">
    <legend className="px-1 text-sm font-semibold text-ink">Message templates</legend>
    <p className="text-sm text-muted">Bind each notification event to a template your provider approved. Variables are filled in order.</p>
    {templates.length ? null : <p className="text-sm text-muted">No templates yet.</p>}
    {templates.map((row, index) => <div key={index} role="group" aria-label={`Template ${index + 1}`}
      className="grid min-w-0 gap-2 rounded-md border border-line p-3 sm:grid-cols-2">
      <label className="grid gap-1 text-sm">Event<input className="desk-input" value={row.event} maxLength={64} disabled={disabled}
        placeholder="request_accepted" onChange={event => update(index, { event: event.target.value })} /></label>
      <label className="grid gap-1 text-sm">Audience<select className="desk-input" value={row.audience} disabled={disabled}
        onChange={event => update(index, { audience: event.target.value as WhatsAppTemplate["audience"] })}>
        {AUDIENCES.map(item => <option key={item.key} value={item.key}>{item.label}</option>)}</select></label>
      <label className="grid gap-1 text-sm">Template name<input className="desk-input" value={row.template_name} maxLength={255} disabled={disabled}
        onChange={event => update(index, { template_name: event.target.value })} /></label>
      <label className="grid gap-1 text-sm">Language<input className="desk-input" value={row.locale} maxLength={16} disabled={disabled}
        onChange={event => update(index, { locale: event.target.value })} /></label>
      <label className="grid gap-1 text-sm sm:col-span-2">Variables (comma separated)<input className="desk-input" value={row.variables.join(", ")} disabled={disabled}
        onChange={event => update(index, { variables: event.target.value.split(",").map(part => part.trim()).filter(Boolean) })} /></label>
      <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
        <StatusPill label={row.approved ? "Approved" : "Not approved yet"} tone={row.approved ? "success" : "neutral"} />
        <button type="button" className="desk-button" disabled={disabled}
          onClick={() => onChange(templates.filter((_, at) => at !== index))}>Remove template</button>
      </div>
    </div>)}
    <div><button type="button" className="desk-button" disabled={disabled || templates.length >= 100}
      onClick={() => onChange([...templates, { ...blank }])}>Add template</button></div>
  </fieldset>;
}
