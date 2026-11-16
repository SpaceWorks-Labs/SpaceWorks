// Side-by-side version compare (decision 345(d)): two saved versions of a design, front or back, drawn next to each
// other with what changed outlined (removed and changed on the older one, added and changed on the newer one), and
// the list of changed layers in words. Read-only: restoring stays in the History panel.
import { t } from "@lingui/core/macro";
import { useMemo, useState } from "react";

import { ErrorBlock } from "../ui/ErrorBlock";
import { Modal } from "../ui/Modal";
import { SegmentedControl } from "../ui/SegmentedControl";
import { LogoLoader } from "../LogoLoader";
import type { CardDocument, Layer, SideName } from "./cardTypes";
import { fitInside } from "./canvasMath";
import { CardThumbnail } from "./CardThumbnail";
import { layerName } from "./designDocument";
import { useRevision } from "./designerHistoryApi";
import { changeLabel, diffDocuments, isUnchanged, type SideDiff } from "./documentDiff";

const COLOURS = { added: "#15803D", removed: "#BE123C", changed: "#C2410C" } as const;
type Mark = { layer: Layer; tone: keyof typeof COLOURS };

function Marked({ document, side, marks, designId, values, label }: {
  document: CardDocument; side: SideName; marks: Mark[]; designId: number; values: Record<string, string>; label: string;
}) {
  const page = document[side];
  const width = fitInside(300, 220, page.page_width_mm, page.page_height_mm);
  const px = width / page.page_width_mm;
  return <figure className="grid justify-items-center gap-1">
    <div className="relative">
      <CardThumbnail side={page} designId={designId} values={values} mono={document.mono} watermark={document.watermark}
        width={width} label={label} />
      {marks.map(({ layer, tone }) => <span key={`${tone}-${layer.id}`} aria-hidden="true" className="pointer-events-none absolute border-2"
        style={{ left: layer.x_mm * px - 2, top: layer.y_mm * px - 2, width: layer.w_mm * px + 4, height: layer.h_mm * px + 4,
          borderColor: COLOURS[tone], borderStyle: tone === "removed" ? "dashed" : "solid" }} />)}
    </div>
    <figcaption className="text-xs font-semibold text-muted">{label}</figcaption>
  </figure>;
}

function ChangeList({ diff }: { diff: SideDiff }) {
  const rows = [
    ...diff.added.map((layer) => ({ key: `a${layer.id}`, tone: "added" as const, text: t`Added: ${layerName(layer)}` })),
    ...diff.removed.map((layer) => ({ key: `r${layer.id}`, tone: "removed" as const, text: t`Removed: ${layerName(layer)}` })),
    ...diff.changed.map((change) => ({ key: `c${change.id}`, tone: "changed" as const,
      text: t`Changed: ${change.name} (${change.kinds.map(changeLabel).join(", ")})` })),
  ];
  return <ul className="grid gap-1 text-sm" aria-label={t`Changed layers`}>
    {diff.background ? <li className="text-ink">{t`The background changed.`}</li> : null}
    {diff.overlay ? <li className="text-ink">{t`The overlay changed.`}</li> : null}
    {diff.reordered ? <li className="text-ink">{t`The stacking order changed.`}</li> : null}
    {rows.map((row) => <li key={row.key} className="flex items-start gap-2 text-ink">
      <span aria-hidden="true" className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ background: COLOURS[row.tone] }} />{row.text}</li>)}
  </ul>;
}

export function VersionCompare({ designId, older, newer, values, onClose }: {
  designId: number; older: number; newer: number; values: Record<string, string>; onClose: () => void;
}) {
  const [side, setSide] = useState<SideName>("front");
  const a = useRevision(designId, older);
  const b = useRevision(designId, newer);
  const diff = useMemo(() => (a.data && b.data ? diffDocuments(a.data.document, b.data.document) : null), [a.data, b.data]);
  const sideDiff = diff?.[side];
  const twoSided = Boolean(a.data?.document.back_enabled || b.data?.document.back_enabled);
  const card = diff?.card.map((key) => ({ stock: t`The card size changed.`, two_sided: t`Two-sided printing changed.`,
    mono: t`Black and white printing changed.`, watermark: t`The watermark changed.` })[key]) ?? [];
  return <Modal open onClose={onClose} title={t`Compare version ${older} with version ${newer}`} size="xl"
    footer={<div className="flex justify-end"><button type="button" className="desk-button min-h-11" onClick={onClose}>{t`Close`}</button></div>}>
    {a.isLoading || b.isLoading ? <LogoLoader size={48} className="min-h-40 py-3" /> : null}
    {a.isError || b.isError ? <ErrorBlock error={a.error ?? b.error} resource={t`these versions`} /> : null}
    {a.data && b.data && diff && sideDiff ? <div className="grid gap-4">
      {twoSided ? <SegmentedControl label={t`Side`} value={side} onChange={(value) => setSide(value as SideName)}
        options={[{ value: "front", label: t`Front` }, { value: "back", label: t`Back` }]} /> : null}
      <div className="grid gap-4 sm:grid-cols-2">
        <Marked document={a.data.document} side={side} designId={designId} values={values} label={t`Version ${older}`}
          marks={[...sideDiff.removed.map((layer) => ({ layer, tone: "removed" as const })),
            ...a.data.document[side].layers.filter((layer) => sideDiff.changed.some((c) => c.id === layer.id)).map((layer) => ({ layer, tone: "changed" as const }))]} />
        <Marked document={b.data.document} side={side} designId={designId} values={values} label={t`Version ${newer}`}
          marks={[...sideDiff.added.map((layer) => ({ layer, tone: "added" as const })),
            ...b.data.document[side].layers.filter((layer) => sideDiff.changed.some((c) => c.id === layer.id)).map((layer) => ({ layer, tone: "changed" as const }))]} />
      </div>
      <p className="text-xs text-muted">{t`Green: added. Red, dashed: removed. Orange: changed.`}</p>
      {isUnchanged(diff) ? <p className="text-sm text-muted">{t`These two versions are the same.`}</p> : <>
        {card.length ? <ul className="grid gap-1 text-sm text-ink">{card.map((text) => <li key={text}>{text}</li>)}</ul> : null}
        <ChangeList diff={sideDiff} />
      </>}
    </div> : null}
  </Modal>;
}
