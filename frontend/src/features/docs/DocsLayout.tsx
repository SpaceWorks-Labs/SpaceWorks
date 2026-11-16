import { t } from "@lingui/core/macro";
import { PanelLeft, Search, X } from "lucide-react";
import { usePresence } from "../../lib/motion";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import { HubFooter } from "../hub/HubFooter";
import { HubHeader } from "../hub/HubHeader";
import { DocsSearchPalette, usePaletteShortcut } from "./DocsSearchPalette";
import { DocsSidebar } from "./DocsSidebar";
import "../hub/hub.css";
import "./docs.css";

const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

/** Header with the search trigger, a sticky sidebar on desktop and a drawer on phones, then the page. */
export function DocsLayout({ currentId, children }: { currentId: string; children: (openPalette: () => void) => ReactNode }) {
  const [params, setParams] = useSearchParams();
  const queryParam = params.get("q") ?? "";
  const [palette, setPalette] = useState(Boolean(queryParam));
  const [drawer, setDrawer] = useState(false);
  const drawerButton = useRef<HTMLButtonElement>(null);
  const drawerPanel = useRef<HTMLDivElement>(null);
  const { pathname } = useLocation();
  const drawerPresence = usePresence(drawer, 180);
  const openPalette = useCallback(() => setPalette(true), []);
  usePaletteShortcut(openPalette);
  useEffect(() => { if (queryParam) setPalette(true); }, [queryParam]);
  useEffect(() => { setDrawer(false); }, [pathname]);
  useEffect(() => {
    if (!drawer) return;
    drawerPanel.current?.querySelector<HTMLElement>("a,button")?.focus();
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") { setDrawer(false); drawerButton.current?.focus(); } };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [drawer]);
  const closePalette = () => {
    setPalette(false);
    if (queryParam) { const next = new URLSearchParams(params); next.delete("q"); setParams(next, { replace: true }); }
  };
  const searchButton = <button type="button" className="sw-doc-search-trigger" onClick={openPalette} aria-label={t`Search the documentation`}>
    <Search size={18} aria-hidden="true" /><span className="hidden md:inline">{t`Search docs`}</span>
    <kbd className="sw-doc-kbd">{isMac ? t`⌘K` : t`Ctrl K`}</kbd>
  </button>;
  return <div className="sw-hub sw-doc-root">
    <a href="#docs-main" className="skip-link">{t`Skip to content`}</a>
    <HubHeader tools={searchButton} />
    <div className="sw-doc-shell">
      <aside className="sw-doc-sidebar" aria-label={t`Documentation sections`}><DocsSidebar currentId={currentId} /></aside>
      <div className="min-w-0">
        <div className="sw-doc-mobilebar">
          <button ref={drawerButton} type="button" className="desk-button gap-2" aria-expanded={drawer} aria-controls="docs-drawer" onClick={() => setDrawer(true)}>
            <PanelLeft size={18} aria-hidden="true" />{t`Browse docs`}</button>
        </div>
        <main id="docs-main" data-sw-main tabIndex={-1} className="sw-doc-main">{children(openPalette)}</main>
      </div>
    </div>
    {drawerPresence.present ? <div className="sw-doc-drawer-scrim" data-state={drawerPresence.state} inert={drawerPresence.closing} onMouseDown={event => { if (event.target === event.currentTarget) setDrawer(false); }}>
      <div id="docs-drawer" ref={drawerPanel} role="dialog" aria-modal="true" aria-label={t`Documentation sections`} data-state={drawerPresence.state} data-edge="left" onAnimationEnd={drawerPresence.onAnimationEnd} className="sw-doc-drawer sw-fx-drawer">
        <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
          <span className="font-extrabold">{t`Documentation`}</span>
          <button type="button" className="desk-button min-w-11 px-2" onClick={() => { setDrawer(false); drawerButton.current?.focus(); }}>
            <X size={20} aria-hidden="true" /><span className="sr-only">{t`Close`}</span></button>
        </div>
        <div className="overflow-y-auto p-3"><DocsSidebar currentId={currentId} onNavigate={() => setDrawer(false)} /></div>
      </div>
    </div> : null}
    <DocsSearchPalette open={palette} initialQuery={queryParam} onClose={closePalette} />
    <HubFooter />
  </div>;
}
