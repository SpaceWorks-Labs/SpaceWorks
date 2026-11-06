import { t } from "@lingui/core/macro";
import { LayoutTemplate } from "lucide-react";
import type { UseQueryResult } from "@tanstack/react-query";
import type { BroadcastTemplate } from "./broadcastApi";

const AUDIENCE: Record<string, string> = { any: "", attended: "checked in", not_attended: "not checked in" };

export function audienceText(template: Pick<BroadcastTemplate, "statuses" | "attendance">) {
  const states = template.statuses.map(status => status.replace(/_/g, " ")).join(", ");
  return AUDIENCE[template.attendance] ? `${states} · ${AUDIENCE[template.attendance]}` : states;
}

/** Starter cards prefill subject, message, audience and design; nothing is sent from here. */
export function BroadcastTemplateGallery({ templates, onPick }: { templates: UseQueryResult<BroadcastTemplate[]>; onPick: (template: BroadcastTemplate) => void }) {
  // 404 while events.broadcast_templates is off: the gallery is simply not offered.
  if (templates.isLoading) return <p role="status" className="text-sm text-muted">{t`Loading starter templates…`}</p>;
  if (templates.error || !templates.data?.length) return null;
  return <section aria-labelledby="broadcast-templates-title" className="grid gap-3">
    <div className="flex items-center gap-2"><LayoutTemplate aria-hidden="true" className="size-5 text-brand" /><h4 id="broadcast-templates-title" className="font-accent text-lg text-ink">{t`Start from a template`}</h4></div>
    <p className="text-sm text-muted">{t`Each starter fills in the subject, message, audience and design. You still preview and confirm before anyone receives it.`}</p>
    <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{templates.data.map(template => <li key={template.key}>
      <button type="button" className="grid h-full w-full gap-1 rounded-2xl border border-line bg-panel p-4 text-left transition-colors hover:border-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand motion-reduce:transition-none" onClick={() => onPick(template)}>
        <span className="font-semibold text-ink">{template.label}</span>
        <span className="text-sm text-muted">{template.description}</span>
        <span className="mt-1 text-xs text-muted">{t`Audience: ${audienceText(template)}`}</span>
      </button>
    </li>)}</ul>
  </section>;
}
