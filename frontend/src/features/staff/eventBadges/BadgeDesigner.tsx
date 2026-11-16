// The event badge designer (a native port of SpaceWorks-Events' IdCardDesigner): settings on the left, the
// badge drawn to scale in the middle (from the same layers the server prints), the selected item's
// properties on the right. Saves as you go; every check-in desk prints the published design.
import { t } from "@lingui/core/macro";
import { useMemo, useState } from "react";

import type { CardDesign } from "../../../components/card-designer/cardTypes";
import { SegmentedControl } from "../../../components/ui";
import type { BadgeDesigns } from "./badgeApi";
import { BadgeAnswerFields } from "./BadgeAnswerFields";
import { BadgeCanvas, SAFE_MARGIN_MM } from "./BadgeCanvas";
import { FitArea } from "./badgeControls";
import { BadgeFileActions, type Notice } from "./BadgeFileActions";
import { elementBoxHeight, layoutForPaper, type BadgeElement, type Flags } from "./badgeGeometry";
import { BadgeInspector } from "./BadgeInspector";
import { saveStatusLabels } from "./badgeLabels";
import { GRID_SIZES, isDefaultLayout, layoutFlags } from "./badgeNormalize";
import { BadgePublish } from "./BadgePublish";
import { SAMPLE_QR_VALUE, sampleValues, type Sample } from "./badgeSample";
import { ColourSection, PaperSection, StyleSection, TextSection } from "./BadgeSections";
import { LogosSection, ShowSection } from "./BadgeShowSection";
import { BadgeWatermarkSection } from "./BadgeWatermarkSection";
import { useBadgeDesign } from "./useBadgeDesign";

const STATUS_TONE = { saved: "text-success", pending: "text-muted", saving: "text-muted", local: "text-warn-ink", error: "text-danger" };

export function BadgeDesigner({ eventId, design, info, roleLabel, onConverted }: { eventId: number; design: CardDesign;
  info: BadgeDesigns; roleLabel: string; onConverted: () => void }) {
  const canEdit = design.can_edit;
  const working = useBadgeDesign(design, { canEdit, eventTitle: info.event_title, organisationName: info.organisation_name });
  const { settings, update } = working;
  const [selected, setSelected] = useState<BadgeElement>("name");
  const [sample, setSample] = useState<Sample>("short");
  const [guides, setGuides] = useState(true);
  const [notice, setNotice] = useState<Notice>(null);
  const values = useMemo(() => sampleValues(info.fields, sample), [info.fields, sample]);
  const branding = info.branding;
  const images = useMemo(() => ({ absent: [...(branding.has_organisation_logo ? [] : ["organisation"]),
    ...(branding.has_event_logo ? [] : ["event"]),
    ...Array.from({ length: 6 }, (_v, index) => `sponsor_${index + 1}`).slice(branding.sponsor_count)] }), [branding]);
  const flags = layoutFlags(settings);
  const statusLabels = saveStatusLabels();

  const move = (element: BadgeElement, xMm: number, yMm: number) => {
    const grid = settings.gridSizeMm;
    const size = settings.elementSizes[element];
    const height = elementBoxHeight(element, settings.elementSizes, settings.widthMm, settings.heightMm);
    const snap = (value: number) => Math.round(value / grid) * grid;
    const next = { xMm: Math.min(Math.max(0, settings.widthMm - size - SAFE_MARGIN_MM), Math.max(0, snap(xMm))),
      yMm: Math.min(Math.max(0, settings.heightMm - height - SAFE_MARGIN_MM), Math.max(0, snap(yMm))) };
    const current = settings.elementPositions[element];
    if (current.xMm === next.xMm && current.yMm === next.yMm) return;
    update({ elementPositions: { ...settings.elementPositions, [element]: next } }, false);
  };
  const setPaper = (widthMm: number, heightMm: number) =>
    update({ widthMm, heightMm, ...layoutForPaper(settings.template, widthMm, heightMm, flags) });
  const toggleItem = (flag: keyof Flags, on: boolean, element: BadgeElement) => {
    if (isDefaultLayout(settings, flags)) {
      update({ [flag]: on, ...layoutForPaper(settings.template, settings.widthMm, settings.heightMm, { ...flags, [flag]: on }) });
    } else {
      update({ [flag]: on });
    }
    if (on) setSelected(element);
  };
  const removeKeys = (gone: string[]) => update({ printFieldKeys: settings.printFieldKeys.filter((key) => !gone.includes(key)) });

  return <section aria-labelledby="badge-designer-title" className="grid overflow-hidden rounded-xl border border-line bg-panel">
    <header className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3">
      <div className="min-w-0 flex-1">
        <h3 id="badge-designer-title" className="text-lg font-semibold text-ink">{t`Badge designer`}</h3>
        <p className="truncate text-xs text-muted">{t`${info.event_title} · ${roleLabel} badge · every check-in desk prints the published design`}</p>
      </div>
      <span aria-live="polite" className={`text-sm font-semibold ${STATUS_TONE[working.status]}`}>{statusLabels[working.status]}</span>
      {working.status === "error" && !working.conflict ? <button type="button" className="desk-button min-h-11" onClick={() => void working.retry()}>{t`Try again`}</button> : null}
      <button type="button" className="desk-button-ghost min-h-11" disabled={!working.canUndo} onClick={working.undo}>{t`Undo`}</button>
      <button type="button" className="desk-button-ghost min-h-11" disabled={!working.canRedo} onClick={working.redo}>{t`Redo`}</button>
    </header>
    <div className="grid gap-2 empty:hidden [&:not(:empty)]:px-4 [&:not(:empty)]:pt-3">
      {working.device ? <div role="status" className="flex flex-wrap items-center gap-2 rounded-control border border-line bg-surface p-3 text-sm text-ink">
        <span className="flex-1">{t`This device kept changes that weren't saved.`}</span>
        <button type="button" className="desk-button-primary min-h-11" onClick={working.restoreDevice}>{t`Restore them`}</button>
        <button type="button" className="desk-button-ghost min-h-11" onClick={working.discardDevice}>{t`Discard`}</button>
      </div> : null}
      {working.conflict ? <div role="alert" className="flex flex-wrap items-center gap-2 rounded-control border border-line bg-surface p-3 text-sm text-ink">
        <span className="flex-1">{t`Someone else saved this badge while you were editing.`}</span>
        <button type="button" className="desk-button min-h-11" onClick={() => void working.loadTheirs()}>{t`Load their version`}</button>
        <button type="button" className="desk-button-primary min-h-11" onClick={() => void working.keepMine()}>{t`Keep mine`}</button>
      </div> : null}
      {working.status === "error" && working.error ? <p role="alert" className="text-sm text-danger">{working.error} {t`Your changes are kept on this device.`}</p> : null}
      {notice ? <div role={notice.tone === "danger" ? "alert" : "status"}
        className={`flex flex-wrap items-center gap-2 rounded-control border border-line p-3 text-sm ${notice.tone === "danger" ? "text-danger" : "text-ink"}`}>
        <span className="flex-1">{notice.text}</span>
        {notice.unmatched?.length ? <button type="button" className="desk-button min-h-11"
          onClick={() => { removeKeys(notice.unmatched ?? []); setNotice(null); }}>
          {t`Remove ${notice.unmatched.length} answers this event doesn't have`}</button> : null}
        <button type="button" className="desk-button-ghost min-h-11" onClick={() => setNotice(null)}>{t`Dismiss`}</button>
      </div> : null}
    </div>
    <div className="grid min-w-0 lg:grid-cols-[300px_minmax(0,1fr)_272px]">
      <aside aria-label={t`Badge settings`} className="order-2 grid content-start gap-6 border-line p-4 lg:order-none lg:max-h-[78vh] lg:overflow-y-auto lg:border-r">
        <StyleSection settings={settings} flags={flags} update={update} />
        <ColourSection settings={settings} update={update} />
        <PaperSection settings={settings} presets={info.presets} onPaper={setPaper} update={update} />
        <TextSection settings={settings} update={update} />
        <LogosSection settings={settings} branding={branding} sponsorMax={info.sponsor_limit_max} update={update} toggleItem={toggleItem} />
        <ShowSection settings={settings} update={update} toggleItem={toggleItem} />
        <BadgeAnswerFields settings={settings} fields={info.fields} max={info.max_print_fields} update={update} />
        <BadgeWatermarkSection settings={settings} update={update} />
      </aside>
      <div className="order-1 flex min-w-0 flex-col lg:order-none">
        <div className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2">
          <SegmentedControl label={t`Preview with`} value={sample} onChange={(value) => setSample(value as Sample)}
            options={[{ value: "short", label: t`Short name` }, { value: "long", label: t`Long name` }]} />
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <button type="button" className={guides ? "desk-button min-h-11" : "desk-button-ghost min-h-11"} aria-pressed={guides}
              onClick={() => setGuides(!guides)}>{guides ? t`Hide guides` : t`Show guides`}</button>
            <label className="flex min-h-11 items-center gap-2 text-sm text-ink">
              <input type="checkbox" className="h-5 w-5 accent-accent" checked={settings.showGrid} disabled={!guides}
                onChange={(event) => update({ showGrid: event.target.checked }, false)} />{t`Grid`}</label>
            <select aria-label={t`Snap to`} className="desk-input min-h-11 w-32" value={settings.gridSizeMm}
              onChange={(event) => update({ gridSizeMm: Number(event.target.value) as typeof settings.gridSizeMm }, false)}>
              {GRID_SIZES.map((size) => <option key={size} value={size}>{t`Snap ${size} mm`}</option>)}
            </select>
          </div>
        </div>
        <FitArea widthMm={settings.widthMm} heightMm={settings.heightMm}>
          {(pxPerMm) => <BadgeCanvas settings={settings} values={values} pxPerMm={pxPerMm} designId={design.id} images={images}
            qrValue={SAMPLE_QR_VALUE} interaction={guides && canEdit ? { selected, onSelect: setSelected, onBeginChange: working.checkpoint,
              onMove: move, showGrid: settings.showGrid } : undefined} />}
        </FitArea>
        <p className="border-t border-line px-4 py-2 text-xs text-muted">{guides
          ? t`Click an item to edit it. Drag, or use the arrow keys (Shift for bigger steps).` : t`This is how the badge prints. Guides never print.`}</p>
      </div>
      <aside aria-label={t`Selected item`} className="order-1 border-line p-4 lg:order-none lg:max-h-[78vh] lg:overflow-y-auto lg:border-l">
        <BadgeInspector settings={settings} branding={branding} selected={selected} onSelect={setSelected} update={update} />
      </aside>
    </div>
    <footer className="grid gap-3 border-t border-line px-4 py-3">
      <BadgeFileActions eventId={eventId} design={design} settings={settings} longNames={sample === "long"} canEdit={canEdit}
        flush={working.flush} adopt={working.adopt} onNotice={setNotice} onConverted={onConverted} />
      <BadgePublish design={design} canEdit={canEdit} flush={working.flush} blocked={working.conflict} />
    </footer>
  </section>;
}
