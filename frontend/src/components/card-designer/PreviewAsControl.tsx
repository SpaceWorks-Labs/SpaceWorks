// "Preview as": draw the card for a short or long sample name, or for one real holder of a
// card this design prints (searchable). "Exact preview" asks the server for the printed PNG.
import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { Eye, UserSearch } from "lucide-react";

import { ErrorBlock } from "../ui/ErrorBlock";
import { Modal } from "../ui/Modal";
import type { CardDesign, CardDocument } from "./cardTypes";
import { exactPreview, useHolders } from "./designerHistoryApi";
import { filterHolders, isLongPerson, previewLabel, SAMPLE_PEOPLE, type PreviewPerson } from "./previewPerson";
import { Toggle } from "./inspectorFields";
import { LogoLoader } from "../LogoLoader";

const option = (on: boolean) => `flex min-h-11 w-full items-center gap-3 rounded-control border px-2 py-2 text-left text-sm text-ink focus-visible:outline-2 focus-visible:outline-focus ${on ? "border-accent-ink bg-accent-soft" : "border-transparent hover:bg-hover"}`;
const mark = (on: boolean) => <span aria-hidden="true" className={`grid h-5 w-5 shrink-0 place-items-center rounded-full border-2 ${on ? "border-accent-ink" : "border-line"}`}>
  {on ? <span className="h-2.5 w-2.5 rounded-full bg-accent-ink" /> : null}</span>;

export function PreviewAsControl({ design, document, person, onPerson }: {
  design: CardDesign; document: CardDocument; person: PreviewPerson; onPerson: (person: PreviewPerson) => void;
}) {
  const [picking, setPicking] = useState(false);
  const [exact, setExact] = useState(false);
  const [search, setSearch] = useState("");
  const holders = useHolders(design.id, picking);
  const rows = filterHolders(holders.data ?? [], search);
  const choose = (next: PreviewPerson) => { onPerson(next); setPicking(false); };
  const selectedHolder = person.kind === "holder" ? person.holder.id : null;
  return <>
    <button type="button" className="desk-button min-h-11 max-w-[13rem]" onClick={() => setPicking(true)}>
      <UserSearch size={16} aria-hidden="true" /><span className="truncate">{t`Preview as: ${previewLabel(person)}`}</span></button>
    <button type="button" className="desk-button-ghost min-h-11" onClick={() => setExact(true)}>
      <Eye size={16} aria-hidden="true" /> {t` Exact preview`}</button>
    <Modal open={picking} onClose={() => setPicking(false)} title={t`Preview as`}>
      <div className="grid gap-4">
        <div role="group" aria-labelledby="preview-as-samples" className="grid gap-1">
          <h3 id="preview-as-samples" className="mb-1 text-xs font-semibold text-muted">{t`Sample people`}</h3>
          {(["short", "long"] as const).map((kind) => <button key={kind} type="button" aria-pressed={person.kind === kind}
            className={option(person.kind === kind)} onClick={() => choose({ kind })}>
            {mark(person.kind === kind)}{previewLabel({ kind })}</button>)}
          {SAMPLE_PEOPLE.map((sample) => {
            const on = person.kind === "sample" && person.id === sample.id;
            return <button key={sample.id} type="button" aria-pressed={on} className={option(on)}
              onClick={() => choose({ kind: "sample", id: sample.id, long: person.kind === "sample" ? person.long : false })}>
              {mark(on)}{sample.label}</button>;
          })}
          {person.kind === "sample" ? <Toggle label={t`Long form of the name`} checked={person.long}
            onChange={(long) => onPerson({ ...person, long })} /> : null}
        </div>
        <div role="group" aria-labelledby="preview-as-people" className="grid gap-2">
          <h3 id="preview-as-people" className="mb-1 text-xs font-semibold text-muted">{t`People with a card from this design`}</h3>
          <input className="desk-input min-h-11" type="search" value={search} aria-label={t`Search by name or number`}
            placeholder={t`Search by name or number`} onChange={(event) => setSearch(event.target.value)} />
          {holders.isLoading ? <LogoLoader size={48} className="min-h-24 py-3" /> : null}
          {holders.isError ? <ErrorBlock error={holders.error} resource={t`card holders`} onRetry={() => void holders.refetch()} /> : null}
          {holders.data && !holders.data.length ? <p className="text-sm text-muted">{t`No live cards use this design yet.`}</p> : null}
          {holders.data?.length && !rows.length ? <p className="text-sm text-muted">{t`No one matches “${search}”.`}</p> : null}
          <div className="grid max-h-72 gap-1 overflow-y-auto overscroll-contain">
            {rows.map((holder) => <button key={`${holder.kind}-${holder.id}`} type="button" aria-pressed={selectedHolder === holder.id}
              className={option(selectedHolder === holder.id)} onClick={() => choose({ kind: "holder", holder })}>
              {mark(selectedHolder === holder.id)}
              <span className="min-w-0"><span className="block truncate">{holder.name || t`Name hidden`}
                {holder.pii_masked ? <span className="text-muted"> (hidden)</span> : null}</span>
                <span className="block truncate text-xs text-muted">{[holder.number, holder.label].filter(Boolean).join(" · ")}</span></span>
            </button>)}
          </div>
          <p className="text-xs text-muted">{t`The card shows their name and number; every other field stays a sample.`}</p>
        </div>
      </div>
    </Modal>
    {exact ? <ExactPreview design={design} document={document} person={person} onClose={() => setExact(false)} /> : null}
  </>;
}

function ExactPreview({ design, document, person, onClose }: {
  design: CardDesign; document: CardDocument; person: PreviewPerson; onClose: () => void;
}) {
  const [state, setState] = useState<{ urls: { side: "front" | "back"; url: string }[]; error: unknown; loading: boolean }>(
    { urls: [], error: null, loading: true });
  const holderId = person.kind === "holder" ? person.holder.id : null;
  useEffect(() => {
    let live = true;
    const made: string[] = [];
    const sides: ("front" | "back")[] = document.back_enabled ? ["front", "back"] : ["front"];
    Promise.all(sides.map((side) => exactPreview(design.id, document, side,
      { format: "png", longNames: isLongPerson(person), holderId })
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        if (live) made.push(url); else URL.revokeObjectURL(url);
        return { side, url };
      })))
      .then((urls) => { if (live) setState({ urls, error: null, loading: false }); })
      .catch((error) => { if (live) setState({ urls: [], error, loading: false }); });
    return () => { live = false; made.forEach((url) => URL.revokeObjectURL(url)); };
    // One render per opening: the dialog shows the design as it was when it was opened.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- the render inputs are deliberately read once at mount (see the comment above)
  }, []);
  return <Modal open onClose={onClose} title={t`Exact preview`} size="xl"
    footer={<div className="flex justify-end"><button type="button" className="desk-button min-h-11" onClick={onClose}>{t`Close`}</button></div>}>
    <div className="grid gap-3">
      <p className="text-sm text-muted">{t`Drawn by the print engine for ${previewLabel(person)}, marked PREVIEW. Sensitive extras are never shown.`}</p>
      {state.loading ? <LogoLoader size={48} className="min-h-56 py-3" /> : null}
      {state.error ? <ErrorBlock error={state.error} resource={t`preview`} /> : null}
      <div className="grid gap-3 md:grid-cols-2">
        {state.urls.map(({ side, url }) => <figure key={side} className="grid gap-1">
          <img src={url} className="w-full rounded-control border border-line bg-white"
            alt={t`The ${side} of the card as it will print for ${previewLabel(person)}`} />
          <figcaption className="text-xs text-muted">{side === "front" ? t`Front` : t`Back`}</figcaption>
        </figure>)}
      </div>
    </div>
  </Modal>;
}
