import { t } from "@lingui/core/macro";
import { CornerDownLeft, FileText, Hash, SquareTerminal } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { SearchField, searchItemStyle } from "../../components/ui/SearchField";
import { useTransitionNavigate } from "../../lib/motion";
import { searchDocs } from "./docsIndex";
import type { DocsSearchHit } from "./docsTypes";

const ICONS = { page: FileText, heading: Hash, operation: SquareTerminal } as const;

/** API operations come from their own lazily loaded index; doc pages and headings are searched at once. */
function useApiHits(query: string) {
  const [hits, setHits] = useState<DocsSearchHit[]>([]);
  useEffect(() => {
    if (query.trim().length < 2) { setHits([]); return; }
    let live = true;
    const timer = window.setTimeout(() => {
      void import("./apiReference/apiSearch").then(m => m.searchApiOperations(query, 6)).then(found => { if (live) setHits(found); })
        .catch(() => { if (live) setHits([]); });
    }, 120);
    return () => { live = false; window.clearTimeout(timer); };
  }, [query]);
  return hits;
}

/** Ctrl/⌘+K palette over titles, headings, summaries and API operations; a keyboard-first combobox. */
export function DocsSearchPalette({ open, initialQuery = "", onClose }: { open: boolean; initialQuery?: string; onClose: () => void }) {
  const navigate = useTransitionNavigate();
  const [query, setQuery] = useState(initialQuery);
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const dialog = useRef<HTMLDivElement>(null);
  const listId = useId();
  const docs = useMemo(() => searchDocs(query, 12), [query]);
  const api = useApiHits(query);
  const results = useMemo(() => [...docs, ...api], [docs, api]);
  useEffect(() => { if (open) { setQuery(initialQuery); setActive(0); } }, [open, initialQuery]);
  useEffect(() => { setActive(0); }, [query]);
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    input.current?.focus();
    return () => previous?.focus?.();
  }, [open]);
  if (!open) return null;
  const go = (hit: DocsSearchHit | undefined) => { if (!hit) return; onClose(); navigate(hit.href); };
  const optionId = (index: number) => `${listId}-option-${index}`;
  return <div className="sw-doc-palette-scrim" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
    <div ref={dialog} role="dialog" aria-modal="true" aria-label={t`Search the documentation`} className="sw-doc-palette"
      onKeyDown={event => {
        if (event.key === "Escape") { event.preventDefault(); onClose(); }
        if (event.key === "Tab") { event.preventDefault(); input.current?.focus(); }
      }}>
      <div className="sw-doc-palette-input">
        <SearchField bare clearOnEscape={false} ref={input} role="combobox" aria-expanded={results.length > 0} aria-controls={listId} aria-autocomplete="list"
          aria-activedescendant={results.length ? optionId(active) : undefined} aria-label={t`Search the documentation`}
          placeholder={t`Search pages, sections and API endpoints`} value={query} onChange={event => setQuery(event.target.value)}
          onKeyDown={event => {
            if (event.key === "ArrowDown") { event.preventDefault(); setActive(index => Math.min(index + 1, results.length - 1)); }
            if (event.key === "ArrowUp") { event.preventDefault(); setActive(index => Math.max(index - 1, 0)); }
            if (event.key === "Enter") { event.preventDefault(); go(results[active]); }
          }} />
        <kbd className="sw-doc-kbd">{t`Esc`}</kbd>
      </div>
      {query.trim() ? results.length
        ? <ul id={listId} role="listbox" aria-label={t`Results`} className="sw-doc-palette-list sw-search-pop">
          {results.map((hit, index) => {
            const Icon = ICONS[hit.kind];
            return <li key={`${hit.kind}-${hit.id}`} id={optionId(index)} role="option" aria-selected={index === active}
              className="sw-doc-palette-option sw-search-item" style={searchItemStyle(index)} onMouseMove={() => setActive(index)} onClick={() => go(hit)}>
              <Icon size={18} aria-hidden="true" className="mt-0.5 shrink-0 text-muted" />
              <span className="grid min-w-0"><span className="truncate font-semibold text-ink">{hit.title}</span>
                <span className={`truncate text-sm text-muted ${hit.kind === "operation" ? "code-text" : ""}`}>{hit.context}</span></span>
              {index === active ? <CornerDownLeft size={16} aria-hidden="true" className="ml-auto shrink-0 text-muted" /> : null}
            </li>;
          })}
        </ul>
        : <p role="status" className="sw-search-empty px-5 py-8 text-center text-muted">{t`Nothing matches “${query.trim()}”. Try a shorter word.`}</p>
        : <p className="px-5 py-8 text-center text-muted">{t`Type to search every page, section and API endpoint.`}</p>}
      <p className="sw-doc-palette-foot"><span><kbd className="sw-doc-kbd">↑</kbd> <kbd className="sw-doc-kbd">↓</kbd> {t`to move`}</span>
        <span><kbd className="sw-doc-kbd">↵</kbd> {t`to open`}</span></p>
    </div>
  </div>;
}

/** Opens the palette on Ctrl+K / ⌘+K anywhere, and on "/" outside text fields. */
export function usePaletteShortcut(openPalette: () => void) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing = target && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName));
      if ((event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey)) || (event.key === "/" && !typing)) {
        event.preventDefault();
        openPalette();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [openPalette]);
}
