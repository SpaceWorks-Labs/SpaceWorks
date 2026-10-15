
import { SettingsLayout } from "../../../../components/layouts";
import { type Tab } from "../../../../components/ui";
import { opsQueryState } from "../../opsPresentation";
import { useCardTemplateDraft } from "./useCardTemplateDraft";
import { CARD_FRONT_FIELDS, type CardTemplate } from "./types";

const PAGES: CardTemplate["page"][] = ["a4", "letter", "cr80"];
const ORIENTATIONS: CardTemplate["orientation"][] = ["portrait", "landscape"];
const MM_FIELDS = [
  ["card_width_mm", "Card width (mm)"],
  ["card_height_mm", "Card height (mm)"],
  ["margin_mm", "Page margin (mm)"],
  ["gap_mm", "Gap between cards (mm)"],
  ["name_font_size_pt", "Name font size (pt)"],
  ["font_size_pt", "Other text size (pt)"],
] as const;

const TOGGLES = [
  ["include_photo", "Print the member photo"],
  ["include_qr", "Print the card QR code"],
  ["crop_marks", "Print crop marks"],
] as const;

/** The print template. Collapsed by default: it is set once per makerspace and then left
 *  alone, so it must not push the card list and the scan box below the fold. */
export function CardTemplateForm({ editor, tabs, activeTab }: {
  editor: ReturnType<typeof useCardTemplateDraft>; tabs?: Tab[]; activeTab?: string;
}) {
  const { template, save, draft, setDraft, dirty, setDirty, patch, toggleField } = editor;
  return <SettingsLayout header={{ title: "Member cards", subtitle: "Choose what appears on your printed cards." }}
    tabs={tabs} activeTab={activeTab} state={opsQueryState(template, "the card layout")} subnav={false}
    sections={draft ? [
      { id: "paper", title: "Paper and size", rows: [
        { label: "Page", children: <select className="desk-input" aria-label="Page" value={draft.page}
          onChange={event => patch({ page: event.target.value as CardTemplate["page"] })}>
          {PAGES.map(value => <option key={value} value={value}>{value.toUpperCase()}</option>)}</select> },
        { label: "Orientation", children: <select className="desk-input" aria-label="Orientation" value={draft.orientation}
          onChange={event => patch({ orientation: event.target.value as CardTemplate["orientation"] })}>
          {ORIENTATIONS.map(value => <option key={value} value={value}>{value}</option>)}</select> },
        ...MM_FIELDS.map(([key, label]) => ({ label, children: <input className="desk-input" aria-label={label} type="number"
          min={0} step="0.5" value={draft[key]} onChange={event => patch({ [key]: Number(event.target.value) } as Partial<CardTemplate>)} /> })),
      ] },
      { id: "content", title: "Card content", rows: [
        { label: "Fields printed on the front", children: <div className="grid gap-2">{CARD_FRONT_FIELDS.map(field =>
          <label key={field} className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={draft.front_fields.includes(field)}
            onChange={event => toggleField(field, event.target.checked)} />{field.replace(/_/g, " ")}</label>)}</div> },
        { label: "Back-of-card text", children: <textarea className="desk-input w-full" aria-label="Back-of-card text" rows={3}
          value={draft.back_text} onChange={event => patch({ back_text: event.target.value })} /> },
        ...TOGGLES.map(([key, label]) => ({ label, children: <label className="flex min-h-11 items-center gap-2 text-sm">
          <input type="checkbox" aria-label={label} checked={draft[key]} onChange={event => patch({ [key]: event.target.checked } as Partial<CardTemplate>)} />{label}</label> })),
      ] },
    ] : []}
    actions={{ dirty, pending: save.isPending, error: save.error instanceof Error ? save.error.message : undefined,
      onDiscard: () => { setDraft(template.data ?? null); setDirty(false); },
      onSave: () => { if (draft) save.mutate(draft, { onSuccess: () => setDirty(false) }); } }} />;
}
