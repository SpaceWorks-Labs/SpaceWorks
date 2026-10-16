import { useEffect, useState } from "react";
import { ErrorText, Field, SettingsSection, Skeleton } from "../../components/ui";
import { PositionedLayoutEditor } from "../../components/print-layout/PositionedLayoutEditor";
import { layoutFits, syncElements, type PositionedElement } from "../../components/print-layout/positionedLayout";
import { downloadPass, useBookingPassDesigner, type BookingPassTemplate } from "./bookingPassApi";

const FIELDS = { name: "Display name", resource: "Resource", booking_window: "Booking window", reference: "Booking reference" };
const DESCRIPTION = "Passes show only display name, resource, booking window and an optional booking reference. Sample preview uses fictional data. Staff print a pass after recording arrival.";

export function BookingPassDesigner({ makerspaceId, spaceId }: { makerspaceId: number; spaceId: number }) {
  const { query, save, preview } = useBookingPassDesigner(makerspaceId, spaceId);
  const [draft, setDraft] = useState<BookingPassTemplate | null>(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => { if (query.data) setDraft(query.data); }, [query.data]);
  const error = query.error ?? save.error ?? preview.error;
  const busy = save.isPending || preview.isPending;
  function change(value: BookingPassTemplate) { setDraft(value); setSaved(false); }
  if (query.isPending) return <div role="status" aria-label="Loading pass layout..." className="grid gap-3"><span className="sr-only">Loading pass layout...</span><Skeleton className="h-24 w-full" /><Skeleton className="h-48 w-full" /></div>;
  if (query.error || !draft) return <ErrorText message={query.error?.message ?? "Unable to load pass layout."} />;
  const width = draft.card_width_mm ?? 90;
  const height = draft.card_height_mm ?? 60;
  const elements = draft.elements as PositionedElement[];
  const valid = layoutFits(elements, width, height) && elements.length > 0;
  return <section aria-label="Booking pass designer" className="grid gap-4">
    <SettingsSection title="Printable passes" description={DESCRIPTION}>
      <div className="grid gap-4 py-5">
        {error ? <ErrorText message={error.message} /> : null}
        {saved ? <p role="status" className="text-sm text-success-ink">Pass layout saved.</p> : null}
        <fieldset disabled={busy} className="grid min-w-0 gap-4">
          <legend className="title-section mb-2">Page and card</legend>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Paper"><select className="desk-input w-full" value={draft.paper_size} onChange={(e) => change({ ...draft, paper_size: e.target.value as BookingPassTemplate["paper_size"] })}>
              <option value="A4">A4</option><option value="LETTER">Letter</option><option value="custom">Custom</option>
            </select></Field>
            <Field label="Orientation"><select className="desk-input w-full" value={draft.orientation} onChange={(e) => change({ ...draft, orientation: e.target.value as BookingPassTemplate["orientation"] })}>
              <option value="portrait">Portrait</option><option value="landscape">Landscape</option>
            </select></Field>
            {draft.paper_size === "custom" ? (["page_width_mm", "page_height_mm"] as const).map((key) => <Field key={key} label={key === "page_width_mm" ? "Page width (mm)" : "Page height (mm)"}>
              <input className="desk-input w-full" type="number" min="100" max="500" value={draft[key] ?? ""} onChange={(e) => change({ ...draft, [key]: Number(e.target.value) })} /></Field>) : null}
            {([["card_width_mm", "Card width", 40, 150], ["card_height_mm", "Card height", 30, 120],
              ["margin_mm", "Page margin", 0, 40], ["gap_mm", "Card gap", 0, 30]] as const).map(([key, label, min, max]) =>
              <Field key={key} label={`${label} (mm)`}><input className="desk-input w-full" type="number" min={min} max={max} step="1" value={draft[key] ?? min} onChange={(e) => {
                const value = Number(e.target.value); if (Number.isFinite(value) && value >= min && value <= max) change({ ...draft, [key]: value });
              }} /></Field>)}
          </div>
          <fieldset className="grid gap-1"><legend className="mb-1 text-sm font-semibold text-ink">Fields on the pass</legend>
            <div className="flex flex-wrap gap-x-6">{Object.entries(FIELDS).map(([field, label]) => <label key={field} className="flex min-h-11 items-center gap-2 text-sm text-ink">
              <input type="checkbox" checked={elements.some((item) => item.field === field)} onChange={() => {
                const fields = elements.map((item) => item.field);
                const next = fields.includes(field) ? fields.filter((item) => item !== field) : [...fields, field];
                if (next.length) change({ ...draft, elements: syncElements(next, elements, width, height) as BookingPassTemplate["elements"] });
              }} />{label}
            </label>)}</div>
          </fieldset>
        </fieldset>
      </div>
      <div className="min-w-0 py-5">
        <PositionedLayoutEditor widthMm={width} heightMm={height} gridMm={draft.grid_mm ?? 1} elements={elements}
          labels={FIELDS} disabled={busy} onGridChange={(grid_mm) => change({ ...draft, grid_mm })}
          onChange={(next) => change({ ...draft, elements: next as BookingPassTemplate["elements"] })} />
      </div>
      <div className="flex flex-wrap justify-end gap-2 pt-5">
        <button type="button" className="desk-button" disabled={busy || !valid} onClick={() => preview.mutate(draft, { onSuccess: downloadPass })}>{preview.isPending ? "Rendering..." : "Download sample PDF"}</button>
        <button type="button" className="desk-button-primary" disabled={busy || !valid} onClick={() => save.mutate(draft, { onSuccess: () => setSaved(true) })}>{save.isPending ? "Saving..." : "Save pass layout"}</button>
      </div>
    </SettingsSection>
  </section>;
}
