// The template gallery: built-in templates, this space's own, and import/export of template files.
// Applying a space template keeps the design's data-field bindings (fields the template does not place are
// appended small at the bottom, and listed so nothing is lost silently).
import { t } from "@lingui/core/macro";
import { useMemo, useRef, useState } from "react";
import { Download, LayoutTemplate, Upload } from "lucide-react";

import { ConfirmDialog } from "../ui/ConfirmDialog";
import { ErrorBlock } from "../ui/ErrorBlock";
import { Modal } from "../ui/Modal";
import { SegmentedControl } from "../ui/SegmentedControl";
import type { CardDesign, CardTemplate } from "./cardTypes";
import { fitInside } from "./canvasMath";
import { CardThumbnail } from "./CardThumbnail";
import { useResetDesign, useTemplates } from "./designerApi";
import { saveBlob } from "./designerHistoryApi";
import { exportTemplate, templateName, useApplyTemplate, useDeleteTemplate, useDuplicateTemplate, useImportTemplate,
  useSaveAsTemplate, useStudioTemplates, useTemplateDocument, type StudioTemplate } from "./templateApi";
import { useCardFonts } from "./useCardFonts";
import { Toggle } from "./inspectorFields";
import { LogoLoader } from "../LogoLoader";

type Tab = "builtin" | "space";

function SpaceCard({ item, design, values, busy, onUse, onDuplicate, onDelete, onExport }: {
  item: StudioTemplate; design: CardDesign; values: Record<string, string>; busy: boolean;
  onUse: () => void; onDuplicate: () => void; onDelete: () => void; onExport: () => void;
}) {
  const detail = useTemplateDocument(item.id, true);
  const document = detail.data?.document;
  useCardFonts(design.id, useMemo(() => (document ? [document] : []), [document]));
  const name = templateName(item);
  return <li className="grid gap-3 rounded-card border border-line bg-surface p-3">
    <div className="flex min-h-24 flex-wrap items-start justify-center gap-2">
      {document ? <CardThumbnail side={document.front} designId={design.id} values={values} mono={document.mono}
        width={fitInside(170, 130, document.front.page_width_mm, document.front.page_height_mm)} label={t`${name}, front`} />
        : <LogoLoader size={48} className="min-h-24 py-3 max-w-32" />}
    </div>
    <div className="grid gap-2">
      <span className="text-sm font-semibold text-ink">{name}
        {item.description ? <span className="block text-xs font-normal text-muted">{item.description}</span> : null}</span>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="desk-button-primary min-h-11" disabled={busy} onClick={onUse}>{t`Use ${name}`}</button>
        <button type="button" className="desk-button-ghost min-h-11" disabled={busy} onClick={onDuplicate}>{t`Duplicate`}</button>
        <button type="button" className="desk-button-ghost min-h-11" aria-label={t`Download ${name} as a file`} onClick={onExport}>
          <Download size={16} aria-hidden="true" /></button>
        <button type="button" className="desk-button-danger-outline min-h-11" disabled={busy} onClick={onDelete}>{t`Delete`}</button>
      </div>
    </div>
  </li>;
}

export function StudioTemplates({ design, makerspaceId, values, flush, revision, onAdopt, onError, kind = "card", open: controlled, onClose }: {
  design: CardDesign; makerspaceId?: number; values: Record<string, string>; flush: () => Promise<void>;
  revision: () => number; onAdopt: (design: CardDesign) => void; onError: (error: unknown) => void; kind?: "card" | "certificate";
  /** Controlled mode (opened from the rail): no trigger button is drawn. */ open?: boolean; onClose?: () => void;
}) {
  const [own, setOwn] = useState(false);
  const open = controlled ?? own;
  const setOpen = (next: boolean) => { if (controlled === undefined) setOwn(next); else if (!next) onClose?.(); };
  const [tab, setTab] = useState<Tab>("builtin");
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [keep, setKeep] = useState(true);
  const [name, setName] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<StudioTemplate | null>(null);
  const file = useRef<HTMLInputElement>(null);
  const builtins = useTemplates(design.id, open);
  const space = useStudioTemplates(makerspaceId, { kind }, open && tab === "space");
  const reset = useResetDesign(design.id);
  const apply = useApplyTemplate(design.id);
  const save = useSaveAsTemplate(makerspaceId ?? 0);
  const importer = useImportTemplate(makerspaceId ?? 0);
  const duplicate = useDuplicateTemplate(makerspaceId ?? 0);
  const remove = useDeleteTemplate(makerspaceId ?? 0);
  const shown = useMemo(() => (builtins.data ?? []).filter((item) => item.theme === theme), [builtins.data, theme]);
  useCardFonts(design.id, useMemo(() => shown.map((item) => item.document), [shown]));
  const busy = [reset, apply, save, importer, duplicate, remove].some((mutation) => mutation.isPending);

  const done = (saved: CardDesign & { unplaced_fields?: string[] }) => {
    onAdopt(saved);
    setNote(saved.unplaced_fields?.length ? t`Applied. These fields were not in the template and were added small at the bottom: ${saved.unplaced_fields.join(", ")}.` : null);
    if (!saved.unplaced_fields?.length) setOpen(false);
  };
  const chooseBuiltin = async (item: CardTemplate) => { await flush(); reset.mutateAsync({ template: item.key, theme: item.theme }).then(done).catch(onError); };
  const chooseSpace = async (item: StudioTemplate) => {
    await flush();
    apply.mutateAsync({ template: item.id, expected_revision: revision(), keep_fields: keep }).then(done).catch(onError);
  };
  const saveCurrent = async () => {
    await flush();
    save.mutateAsync({ design_id: design.id, name: name.trim(), description: "" })
      .then(() => { setName(""); setNote(t`Saved as a template for this space.`); }).catch(onError);
  };
  const importFile = async (chosen: File) => {
    let parsed: unknown;
    try { parsed = JSON.parse(await chosen.text()); } catch { onError(new Error(t`That file isn't a template.`)); return; }
    importer.mutateAsync(parsed).then(() => { setTab("space"); setNote(t`Template imported.`); }).catch(onError);
  };
  const download = (item: StudioTemplate) => exportTemplate(item.id)
    .then((body) => saveBlob(new Blob([JSON.stringify(body, null, 2)], { type: "application/json" }), `card-template-${item.id}.json`)).catch(onError);

  return <>
    {controlled === undefined ? <button type="button" className="desk-button min-h-11" onClick={() => setOpen(true)}>
      <LayoutTemplate size={16} aria-hidden="true" /> {t` Templates`}</button> : null}
    <Modal open={open} onClose={() => setOpen(false)} title={t`Templates`} size="xl">
      <div className="grid gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <SegmentedControl label={t`Template source`} value={tab} onChange={(value) => setTab(value as Tab)}
            options={[{ value: "builtin", label: t`Built-in` }, { value: "space", label: t`This space` }]} />
          {tab === "builtin" ? <SegmentedControl label={t`Template colours`} value={theme} onChange={(value) => setTheme(value as "light" | "dark")}
            options={[{ value: "light", label: t`Light` }, { value: "dark", label: t`Dark` }]} /> : null}
        </div>
        {note ? <p role="status" className="text-sm text-muted">{note}</p> : null}
        {tab === "builtin" ? <>
          <p className="text-sm text-muted">{t`Shown with ${values.name}. Choosing one replaces the draft; every template stays fully editable.`}</p>
          {builtins.isError ? <ErrorBlock error={builtins.error} resource={t`templates`} onRetry={() => void builtins.refetch()} /> : null}
          <ul className="grid gap-3 sm:grid-cols-2" aria-label={t`Built-in templates`}>
            {shown.map((item) => {
              const { front, mono } = item.document;
              return <li key={`${item.key}-${item.theme}`} className="grid gap-3 rounded-card border border-line bg-surface p-3">
                <div className="flex justify-center"><CardThumbnail side={front} designId={design.id} values={values} mono={mono}
                  width={fitInside(190, 140, front.page_width_mm, front.page_height_mm)} label={t`${item.label}, ${item.theme}, front`} /></div>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-ink">{item.label}</span>
                  <button type="button" className="desk-button-primary min-h-11" disabled={busy} onClick={() => void chooseBuiltin(item)}>{t`Use ${item.label}`}</button>
                </div>
              </li>;
            })}
          </ul>
        </> : <>
          {makerspaceId === undefined ? <p className="text-sm text-muted">{t`Space templates need to know which space this design belongs to.`}</p> : <>
            <Toggle label={t`Keep my data fields (name, number, ...) when applying`} checked={keep} onChange={setKeep} />
            <div className="flex flex-wrap items-end gap-2">
              <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Save this design as a template`}</span>
                <input className="desk-input min-h-11" maxLength={80} value={name} onChange={(event) => setName(event.target.value)} placeholder={t`Template name`} /></label>
              <button type="button" className="desk-button min-h-11" disabled={busy || name.trim().length < 2} onClick={() => void saveCurrent()}>{t`Save as template`}</button>
              <button type="button" className="desk-button-ghost min-h-11" onClick={() => file.current?.click()}>
                <Upload size={16} aria-hidden="true" /> {t` Import a template file`}</button>
              <input ref={file} type="file" accept="application/json,.json" className="sr-only" tabIndex={-1} aria-hidden="true"
                onChange={(event) => { const chosen = event.target.files?.[0]; event.target.value = ""; if (chosen) void importFile(chosen); }} />
            </div>
            {space.isLoading ? <LogoLoader size={48} className="min-h-40 py-3" /> : null}
            {space.isError ? <ErrorBlock error={space.error} resource={t`templates`} onRetry={() => void space.refetch()} /> : null}
            {space.data && !space.data.filter((item) => item.source === "space").length
              ? <p className="text-sm text-muted">{t`No templates saved for this space yet.`}</p> : null}
            <ul className="grid gap-3 sm:grid-cols-2" aria-label={t`This space's templates`}>
              {(space.data ?? []).filter((item) => item.source === "space").map((item) => <SpaceCard key={item.id} item={item} design={design}
                values={values} busy={busy} onUse={() => void chooseSpace(item)} onExport={() => void download(item)}
                onDuplicate={() => duplicate.mutate(item.id, { onError })} onDelete={() => setDeleting(item)} />)}
            </ul>
          </>}
        </>}
      </div>
    </Modal>
    <ConfirmDialog open={deleting !== null} title={t`Delete this template?`} confirmLabel={t`Delete the template`} pending={remove.isPending}
      message={t`${deleting ? templateName(deleting) : ""} is removed from this space. Designs that already used it are not changed.`}
      onCancel={() => setDeleting(null)} onConfirm={() => { if (deleting) remove.mutate(deleting.id, { onError, onSettled: () => setDeleting(null) }); }} />
  </>;
}
