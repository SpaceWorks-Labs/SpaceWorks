// The designer's footer actions: export and import a design file, print a test card with sample data
// (the server's own render of this exact design, so it matches every desk), and convert to a free canvas.
import { t } from "@lingui/core/macro";
import { useRef, useState } from "react";

import type { CardDesign, CardDocument } from "../../../components/card-designer/cardTypes";
import { previewBlob } from "../../../components/card-designer/designerApi";
import { ConfirmDialog } from "../../../components/ui";
import { useConvertBadge, useImportBadge } from "./badgeApi";
import { downloadBadgeFile, readBadgeFile, type BadgeFileProblem } from "./badgeFile";
import type { BadgeSettings } from "./badgeNormalize";

export type Notice = { tone: "danger" | "success"; text: string; unmatched?: string[] } | null;

function problemText(problem: BadgeFileProblem) {
  if (problem === "too_large") return t`That file is too large to be a badge design.`;
  if (problem === "newer") return t`This badge design file is from a newer version.`;
  return t`That file isn't a badge design. Choose a .json file exported from the badge designer.`;
}

export function BadgeFileActions({ eventId, design, settings, longNames, canEdit, flush, adopt, onNotice, onConverted }: {
  eventId: number; design: CardDesign; settings: BadgeSettings; longNames: boolean; canEdit: boolean;
  flush: () => Promise<void>; adopt: (design: CardDesign, record?: boolean) => void; onNotice: (notice: Notice) => void;
  onConverted: () => void;
}) {
  const fileInput = useRef<HTMLInputElement>(null);
  const importing = useImportBadge(eventId, design.id);
  const convert = useConvertBadge(eventId, design.id);
  const [confirming, setConfirming] = useState(false);
  const [printing, setPrinting] = useState(false);

  async function importFile(file: File) {
    const read = readBadgeFile(await file.text());
    if ("problem" in read) { onNotice({ tone: "danger", text: problemText(read.problem) }); return; }
    await flush();
    try {
      const result = await importing.mutateAsync(read.file);
      adopt(result.design, true);
      onNotice({ tone: "success", text: [t`Design imported.`, ...result.notes].join(" "), unmatched: result.unmatched_fields });
    } catch (failure) {
      onNotice({ tone: "danger", text: failure instanceof Error ? failure.message : t`The design couldn't be imported.` });
    }
  }

  async function testPrint() {
    setPrinting(true);
    onNotice(null);
    const tab = window.open("", "_blank");
    try {
      const document = { version: 2, source: { format: "badge_v1", settings } } as unknown as CardDocument;
      const url = URL.createObjectURL(await previewBlob(design.id, document, "front", "pdf", longNames));
      if (tab) tab.location.href = url;
      else onNotice({ tone: "danger", text: t`The print window was blocked. Allow pop-ups for this site and try again.` });
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch {
      tab?.close();
      onNotice({ tone: "danger", text: t`The test card couldn't be prepared. Try again.` });
    } finally {
      setPrinting(false);
    }
  }

  return <div className="flex flex-wrap items-center gap-2">
    <button type="button" className="desk-button-ghost min-h-11" title={t`Save this design as a file, to reuse it for another event`}
      onClick={() => downloadBadgeFile(settings)}>{t`Export design`}</button>
    {canEdit ? <>
      <button type="button" className="desk-button-ghost min-h-11" disabled={importing.isPending}
        onClick={() => fileInput.current?.click()}>{importing.isPending ? t`Importing…` : t`Import design`}</button>
      <input ref={fileInput} type="file" accept="application/json,.json" hidden aria-label={t`Badge design file`}
        onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ""; if (file) void importFile(file); }} />
    </> : null}
    <button type="button" className="desk-button min-h-11" disabled={printing} onClick={() => void testPrint()}>
      {printing ? t`Preparing…` : t`Print test card`}</button>
    {canEdit ? <button type="button" className="desk-button-ghost min-h-11" onClick={() => setConfirming(true)}>
      {t`Convert to free canvas…`}</button> : null}
    <ConfirmDialog open={confirming} tone="danger" pending={convert.isPending}
      title={t`Convert this badge to a free canvas?`}
      message={t`Its layers become freely editable in the card designer, and this badge designer can no longer open it. This can't be undone; to come back you start a new badge design.`}
      confirmLabel={t`Convert`} onCancel={() => setConfirming(false)}
      onConfirm={() => void flush().then(() => convert.mutateAsync()).then(() => { setConfirming(false); onConverted(); })
        .catch((failure: unknown) => { setConfirming(false);
          onNotice({ tone: "danger", text: failure instanceof Error ? failure.message : t`The badge couldn't be converted.` }); })} />
  </div>;
}
