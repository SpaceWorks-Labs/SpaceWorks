// Search the card font library (the full Google Fonts catalogue, served by this app). A family
// that is not on the server yet is fetched there first; the browser never calls Google.
import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import type { CardFont } from "./cardTypes";
import { prepareFont, useFonts } from "./designerApi";
import { loadCardFont } from "./fontLoader";
import { LogoLoader } from "../LogoLoader";

const SCRIPTS = [
  { value: "", label: t`Any script` }, { value: "latin", label: t`Latin` }, { value: "devanagari", label: t`Devanagari` },
  { value: "malayalam", label: t`Malayalam` }, { value: "tamil", label: t`Tamil` }, { value: "arabic", label: t`Arabic` },
  { value: "cyrillic", label: t`Cyrillic` }, { value: "greek", label: t`Greek` }, { value: "japanese", label: t`Japanese` },
];

const STATE_LABELS: Record<CardFont["state"], string> = {
  bundled: t`Built in`, ready: t`Ready`, preparing: t`Preparing…`, unavailable: t`Unavailable`, not_fetched: t`Not on the server yet`,
};

export function FontPicker({ designId, family, weight, onChange, disabled }: {
  designId: number; family: string; weight: number; onChange: (family: string, weight: number) => void; disabled?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [script, setScript] = useState("");
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const client = useQueryClient();
  const fonts = useFonts(designId, debounced, script);
  const current = fonts.data?.results.find((font) => font.family === family);
  useEffect(() => { const timer = window.setTimeout(() => setDebounced(query), 250); return () => window.clearTimeout(timer); }, [query]);
  useEffect(() => { void loadCardFont(designId, family, weight); }, [designId, family, weight]);

  async function choose(font: CardFont) {
    setFailure(null);
    if (font.state === "not_fetched" || font.state === "unavailable") {
      setBusy(font.family);
      try {
        const result = await prepareFont(designId, font.family);
        await client.invalidateQueries({ queryKey: ["card-fonts", designId] });
        if (result.state !== "ready" && result.state !== "bundled") {
          setFailure(result.state === "preparing" ? `${font.family} is being fetched. Pick it again in a moment.`
            : `${font.family} couldn't be fetched to the server.`);
          return;
        }
      } catch (error) {
        setFailure(error instanceof Error ? error.message : "The font couldn't be prepared.");
        return;
      } finally {
        setBusy(null);
      }
    }
    const nextWeight = font.weights.includes(weight) ? weight : font.weights.includes(400) ? 400 : font.weights[0];
    onChange(font.family, nextWeight);
    setOpen(false);
  }

  return <div className="grid gap-2">
    <div className="grid grid-cols-[1fr_auto] gap-2">
      <button type="button" className="desk-input min-h-11 truncate text-left" aria-expanded={open} disabled={disabled}
        onClick={() => setOpen((value) => !value)}>{family}</button>
      <select className="desk-input min-h-11" aria-label={t`Weight`} value={weight} disabled={disabled}
        onChange={(event) => onChange(family, Number(event.target.value))}>
        {(current?.weights ?? [weight]).map((value) => <option key={value} value={value}>{value}</option>)}
      </select>
    </div>
    {open ? <div className="grid gap-2 rounded-control border border-line bg-panel p-2">
      <div className="grid grid-cols-[1fr_auto] gap-2">
        <input className="desk-input min-h-11" type="search" placeholder={t`Search fonts`} aria-label={t`Search fonts`}
          value={query} onChange={(event) => setQuery(event.target.value)} />
        <select className="desk-input min-h-11" aria-label={t`Script`} value={script} onChange={(event) => setScript(event.target.value)}>
          {SCRIPTS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
        </select>
      </div>
      {fonts.isLoading ? <LogoLoader label={t`Loading fonts…`} size={48} className="min-h-16 py-3" /> : null}
      {fonts.isError ? <p className="text-sm text-danger">{t`The font list couldn't load.`}</p> : null}
      <ul className="max-h-64 overflow-y-auto" aria-label={t`Fonts`}>
        {fonts.data?.results.map((font) => <li key={font.family}>
          <button type="button" disabled={busy !== null}
            className={`flex min-h-11 w-full items-center justify-between gap-2 rounded-control px-2 text-left text-sm hover:bg-surface ${font.family === family ? "bg-accent-soft text-ink" : "text-ink"}`}
            onClick={() => void choose(font)}>
            <span className="truncate">{font.family}</span>
            <span className="shrink-0 text-xs text-muted">{busy === font.family ? t`Fetching…` : STATE_LABELS[font.state]}</span>
          </button>
        </li>)}
      </ul>
      {fonts.data && fonts.data.count > fonts.data.results.length
        ? <p className="text-xs text-muted">{t`Showing ${fonts.data.results.length} of ${fonts.data.count}. Search to narrow.`}</p> : null}
      {failure ? <p role="alert" className="text-sm text-danger">{failure}</p> : null}
    </div> : null}
  </div>;
}
