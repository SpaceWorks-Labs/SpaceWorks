import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ConfirmDialog, SettingsActions, StatusPill } from "../../../components/ui";
import { DetailLayout } from "../../../components/layouts";
import { useSearchParams } from "react-router-dom";
import { DefaultReference, MergeFields, PreviewPane, TemplateHeader } from "./EmailTemplateEditorParts";
import { staffRequest } from "../../../lib/api";
import { EmailTemplateTypeSelector, type MachineTypeOption } from "./EmailTemplateTypeSelector";
export type TemplateSummary = {
  stream: string;
  audience: string;
  key: string;
  label: string;
  is_active: boolean;
  is_overridden: boolean;
  can_edit_space_default: boolean;
  overridable_types: MachineTypeOption[];
};
export type SelectedTemplate = Pick<TemplateSummary, "stream" | "audience" | "key"> & {
  machineType: MachineTypeOption | null;
  canEditSpaceDefault: boolean;
  overridableTypes: MachineTypeOption[];
};
export type TemplateDetail = TemplateSummary & {
  description: string;
  fields: { name: string; description: string }[];
  subject: string;
  text_body: string;
  html_body: string;
  default_subject: string;
  default_text: string;
  default_html: string;
};
type Draft = { subject: string; text_body: string; html_body: string; is_active: boolean };
type FocusedField = "subject" | "text_body" | "html_body";
export type Preview = Pick<Draft, "subject" | "text_body" | "html_body">;
const emptyDraft: Draft = { subject: "", text_body: "", html_body: "", is_active: true };

export function EmailTemplateEditor({
  makerspaceId,
  selected,
  onSelectMachineType,
  onBack,
}: {
  makerspaceId: number;
  onBack?: () => void;
  selected: SelectedTemplate;
  onSelectMachineType: (machineType: MachineTypeOption | null) => void;
}) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [debouncedDraft, setDebouncedDraft] = useState<Draft>(emptyDraft);
  const [search, setSearch] = useSearchParams();
  const tab = search.get("template_view") ?? "edit";
  const setTab = (value: string) => { const next = new URLSearchParams(search); next.set("template_view", value); setSearch(next); };
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [lastFocused, setLastFocused] = useState<FocusedField>("text_body");
  const subjectRef = useRef<HTMLInputElement>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);
  const htmlRef = useRef<HTMLTextAreaElement>(null);
  const detailKey = [
    "email-template",
    makerspaceId,
    selected.stream,
    selected.audience,
    selected.key,
    selected.machineType?.id ?? "space",
  ];
  const path = templatePath(makerspaceId, selected);
  const detail = useQuery({
    queryKey: detailKey,
    queryFn: () => staffRequest<TemplateDetail>(path),
  });
  useEffect(() => {
    if (detail.data) {
      const next = detailToDraft(detail.data);
      setDraft(next);
      setDebouncedDraft(next);
    }
  }, [detail.data]);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedDraft(draft), 400);
    return () => window.clearTimeout(timer);
  }, [draft]);
  const preview = useQuery({
    queryKey: [
      "email-template-preview",
      makerspaceId,
      selected.stream,
      selected.audience,
      selected.key,
      selected.machineType?.id ?? "space",
      debouncedDraft,
    ],
    queryFn: () =>
      staffRequest<Preview>(`/admin/makerspace/${makerspaceId}/email-templates/preview`, {
        method: "POST",
        body: JSON.stringify({
          stream: selected.stream,
          audience: selected.audience,
          key: selected.key,
          ...(selected.machineType ? { machine_type_id: selected.machineType.id } : {}),
          subject: debouncedDraft.subject,
          text_body: debouncedDraft.text_body,
          html_body: debouncedDraft.html_body,
        }),
      }),
    enabled: Boolean(detail.data),
  });
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["email-templates", makerspaceId] });
    queryClient.invalidateQueries({ queryKey: detailKey });
  };
  const save = useMutation({
    mutationFn: () =>
      staffRequest<TemplateDetail>(path, { method: "PATCH", body: JSON.stringify(draft) }),
    onSuccess: (updated) => {
      const next = detailToDraft(updated);
      setDraft(next);
      setDebouncedDraft(next);
      setResetDialogOpen(false);
      invalidate();
    },
  });
  const reset = useMutation({
    mutationFn: () => staffRequest<TemplateDetail>(`${path}/reset`, { method: "POST" }),
    onSuccess: (updated) => {
      const next = detailToDraft(updated);
      setDraft(next);
      setDebouncedDraft(next);
      invalidate();
    },
  });
  const insertField = (name: string) => {
    const token = `{{ ${name} }}`;
    const target = { subject: subjectRef, text_body: textRef, html_body: htmlRef }[lastFocused].current;
    const start = target?.selectionStart ?? draft[lastFocused].length;
    const end = target?.selectionEnd ?? start;
    setDraft((current) => ({
      ...current,
      [lastFocused]: `${current[lastFocused].slice(0, start)}${token}${current[lastFocused].slice(end)}`,
    }));
    window.requestAnimationFrame(() => {
      target?.focus();
      target?.setSelectionRange(start + token.length, start + token.length);
    });
  };
  const dirty = Boolean(detail.data && JSON.stringify(draft) !== JSON.stringify(detailToDraft(detail.data)));
  const edit = <div className="grid gap-4">
    {detail.data ? <TemplateHeader detail={detail.data} active={draft.is_active} typeOverride={Boolean(selected.machineType)} onActive={is_active => setDraft({ ...draft, is_active })} /> : null}
    <label className="grid gap-2 text-sm font-semibold">Subject
      <input ref={subjectRef} className="desk-input" value={draft.subject} onFocus={() => setLastFocused("subject")} onChange={event => setDraft({ ...draft, subject: event.target.value })} /></label>
    <label className="grid gap-2 text-sm font-semibold">Plain text body
      <textarea ref={textRef} className="desk-input min-h-48 text-base md:text-sm" value={draft.text_body} onFocus={() => setLastFocused("text_body")} onChange={event => setDraft({ ...draft, text_body: event.target.value })} /></label>
    <label className="grid gap-2 text-sm font-semibold">HTML body
      <textarea ref={htmlRef} className="desk-input min-h-56 text-base md:text-sm" value={draft.html_body} onFocus={() => setLastFocused("html_body")} onChange={event => setDraft({ ...draft, html_body: event.target.value })} /></label>
  </div>;
  return <>
    <DetailLayout title={detail.data?.label ?? "Email template"} back={onBack ? { label: "All templates", onClick: onBack } : undefined}
      status={<StatusPill label={detail.data?.is_overridden ? "Edited" : "Default"} tone={detail.data?.is_overridden ? "warn" : "neutral"} />}
      meta={[`${selected.stream} · to ${selected.audience}`]}
      state={{ status: detail.isLoading ? "loading" : detail.error ? "error" : "ready", error: "Couldn't load the template. Try again.", onRetry: () => { void detail.refetch(); } }}
      actions={{ primary: { label: "Save", pending: save.isPending, onClick: () => save.mutate(),
        // Never save before the template has loaded: an empty draft would overwrite it.
        disabled: !detail.data, disabledReason: !detail.data ? "Wait for the template to load." : undefined },
        secondary: { label: "Preview", onClick: () => setTab("preview") },
        overflow: [{ label: selected.machineType ? "Fall back to space default" : "Reset to built-in default", onClick: () => setResetDialogOpen(true), confirms: true, disabled: reset.isPending }] }}
      tabs={["edit", "preview", "default"].map(value => { const next = new URLSearchParams(search); next.set("template_view", value); return { key: value, label: value[0].toUpperCase() + value.slice(1), href: `?${next}` }; })} activeTab={tab}
      main={<div className="grid gap-6">
        <EmailTemplateTypeSelector canEditSpaceDefault={selected.canEditSpaceDefault} types={selected.overridableTypes} selectedTypeId={selected.machineType?.id ?? null} onSelect={onSelectMachineType} />
        {tab === "edit" ? edit : tab === "preview" ? <PreviewPane preview={preview.data} loading={preview.isFetching} error={preview.error} onRetry={() => { void preview.refetch(); }} /> : detail.data ? <DefaultReference detail={detail.data} typeOverride={Boolean(selected.machineType)} /> : null}
        {save.error || reset.error ? <p className="text-sm text-danger" role="alert">{(save.error ?? reset.error)?.message}</p> : null}
        {dirty && detail.data ? <><p className="text-sm text-muted">Unsaved changes</p><SettingsActions pending={save.isPending} onSave={() => save.mutate()} onDiscard={() => { if (detail.data) setDraft(detailToDraft(detail.data)); }} /></> : null}
      </div>} aside={detail.data && tab === "edit" ? <MergeFields detail={detail.data} onInsert={insertField} /> : undefined} />
    <ConfirmDialog open={resetDialogOpen} title="Reset email template?" message={selected.machineType ? "Reset this override to the space default?" : "Reset this email template to the built-in default?"}
      confirmLabel="Reset template" tone="danger" pending={reset.isPending} onConfirm={() => reset.mutate()} onCancel={() => setResetDialogOpen(false)} />
  </>;
}

function templatePath(makerspaceId: number, selected: SelectedTemplate) {
  const base = `/admin/makerspace/${makerspaceId}/email-templates/${[selected.stream, selected.audience, selected.key].map(encodeURIComponent).join("/")}`;
  return selected.machineType ? `${base}/types/${selected.machineType.id}` : base;
}

function detailToDraft(detail: TemplateDetail): Draft {
  return {
    subject: detail.subject,
    text_body: detail.text_body,
    html_body: detail.html_body,
    is_active: detail.is_active,
  };
}
