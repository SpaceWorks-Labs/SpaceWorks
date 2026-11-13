import { t } from "@lingui/core/macro";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ListLayout } from "../../../components/layouts";
import { ListRow, StatusPill } from "../../../components/ui";
import { useSearchParams } from "react-router-dom";
import { staffRequest } from "../../../lib/api";
import { EmailTemplateEditor, type SelectedTemplate, type TemplateSummary } from "./EmailTemplateEditor";
import { type Makerspace } from "./shared";
type GroupedTemplates = {
  stream: string;
  audiences: { audience: string; templates: TemplateSummary[] }[];
}[];

export function EmailTemplatesPanel({ makerspace }: { makerspace: Makerspace }) {
  const [search, setSearch] = useSearchParams();
  const requestedTemplate = search.get("template");
  const streamFilter = search.get("template_stream") ?? "all";
  const [selected, setSelected] = useState<SelectedTemplate | null>(null);
  const list = useQuery({
    queryKey: ["email-templates", makerspace.id],
    queryFn: () =>
      staffRequest<TemplateSummary[]>(`/admin/makerspace/${makerspace.id}/email-templates`),
  });
  const rows = useMemo(() => list.data ?? [], [list.data]);
  useEffect(() => {
    if (!rows.length) {
      setSelected(null);
      return;
    }
    const requested = rows.find(row => `${row.stream}:${row.audience}:${row.key}` === requestedTemplate);
    if (requested && `${selected?.stream}:${selected?.audience}:${selected?.key}` !== requestedTemplate) {
      setSelected(selectTemplate(requested));
      return;
    }
    const current = selected
      ? rows.find(
          (row) =>
            row.stream === selected.stream &&
            row.audience === selected.audience &&
            row.key === selected.key,
        )
      : undefined;
    if (!current || !selected || !selectedAxisIsVisible(current, selected)) {
      const first = rows[0];
      setSelected(selectTemplate(first));
      return;
    }
    const currentType = selected.machineType
      ? current.overridable_types.find((item) => item.id === selected.machineType?.id) ?? null
      : null;
    if (
      selected.canEditSpaceDefault !== current.can_edit_space_default ||
      selected.overridableTypes !== current.overridable_types ||
      selected.machineType !== currentType
    ) {
      setSelected({
        ...selected,
        machineType: currentType,
        canEditSpaceDefault: current.can_edit_space_default,
        overridableTypes: current.overridable_types,
      });
    }
  }, [rows, selected, requestedTemplate]);
  const grouped = useMemo(() => groupTemplates(rows), [rows]);
  const href = (stream: string) => { const next = new URLSearchParams(search); next.set("template_stream", stream); next.delete("template"); return `?${next}`; };
  if (requestedTemplate && selected) return <EmailTemplateEditor makerspaceId={makerspace.id} selected={selected}
    onSelectMachineType={machineType => setSelected({ ...selected, machineType })}
    onBack={() => { const next = new URLSearchParams(search); next.delete("template"); setSearch(next); }} />;
  return <ListLayout header={{ title: t`Email templates`, subtitle: t`What people receive from ${makerspace.name}, in your words.` }}
    state={{ status: list.isLoading ? "loading" : list.error ? "error" : "ready", error: t`Couldn't load email templates. Try again.`, onRetry: () => { void list.refetch(); } }}
    isEmpty={!rows.length} empty={{ message: t`No editable templates here.` }}
    tabs={[{ key: "all", label: t`All templates`, href: href("all"), count: rows.length }, ...grouped.map(group => ({ key: group.stream, label: formatLabel(group.stream), href: href(group.stream), count: group.audiences.reduce((count, audience) => count + audience.templates.length, 0) }))]}
    activeTab={streamFilter} body={{ kind: "rows", rows: grouped.filter(group => streamFilter === "all" || group.stream === streamFilter).map(group =>
      <div key={group.stream} className="grid gap-5">{group.audiences.map(audience => <section key={audience.audience} className="grid gap-3">
        <h2 className="title-section">{t`To ${formatLabel(audience.audience)}`}</h2>
        {audience.templates.map(template => <ListRow key={`${template.stream}:${template.audience}:${template.key}`} title={template.label}
          meta={`Sent when ${formatLabel(template.key)} · ${formatLabel(group.stream)}`}
          right={<StatusPill label={template.is_overridden || template.overridable_types.some(type => type.is_overridden) ? t`Edited` : t`Default`} tone={template.is_overridden ? "warn" : "neutral"} />}
          onClick={() => { setSelected(selectTemplate(template)); const next = new URLSearchParams(search); next.set("template", `${template.stream}:${template.audience}:${template.key}`); setSearch(next); }} />)}
      </section>)}</div>) }} />;
}

function groupTemplates(rows: TemplateSummary[]): GroupedTemplates {
  const streams = new Map<string, Map<string, TemplateSummary[]>>();
  rows.forEach((row) => {
    if (!streams.has(row.stream)) streams.set(row.stream, new Map());
    const audiences = streams.get(row.stream)!;
    if (!audiences.has(row.audience)) audiences.set(row.audience, []);
    audiences.get(row.audience)!.push(row);
  });
  return Array.from(streams, ([stream, audiences]) => ({
    stream,
    audiences: Array.from(audiences, ([audience, templates]) => ({ audience, templates })),
  }));
}

function selectTemplate(template: TemplateSummary): SelectedTemplate {
  return {
    stream: template.stream,
    audience: template.audience,
    key: template.key,
    machineType: template.can_edit_space_default ? null : template.overridable_types[0] ?? null,
    canEditSpaceDefault: template.can_edit_space_default,
    overridableTypes: template.overridable_types,
  };
}

function selectedAxisIsVisible(template: TemplateSummary, selected: SelectedTemplate) {
  if (selected.machineType === null) return template.can_edit_space_default;
  return template.overridable_types.some((item) => item.id === selected.machineType?.id);
}

function formatLabel(value: string) {
  return value.replace(/_/g, " ");
}
