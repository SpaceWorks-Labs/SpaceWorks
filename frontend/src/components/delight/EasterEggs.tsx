import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { eggsAllowed, useDelight } from "./DelightProvider";
import { clearMakerModePending, countLogoClick, makerModePending } from "./logoClicks";
import "./delight.css";

const sequence = ["ArrowUp", "ArrowUp", "ArrowDown", "ArrowDown", "ArrowLeft", "ArrowRight", "ArrowLeft", "ArrowRight", "b", "a"];
const ignoreTarget = (target: EventTarget | null) => target instanceof Element && Boolean(target.closest("input,textarea,select,[contenteditable]:not([contenteditable='false']),[role='textbox'],[role='combobox'],[role='slider'],[role='menu'],[role='dialog']"));
let greeted = false;
const MakerModeContext = createContext<ReturnType<typeof useMakerMode> | null>(null);
export const useShellMakerMode = () => useContext(MakerModeContext);

export function MakerModeHost({ pathname, version, children, sensitiveSurface = false }: { pathname: string; version: string; children: ReactNode; sensitiveSurface?: boolean }) {
  const mode = useMakerMode(pathname, sensitiveSurface);
  return <MakerModeContext.Provider value={mode}>
    <div className={mode.active ? "sw-blueprint-decoration" : undefined}>{children}</div>
    <MakerModePanel mode={mode} version={version} />
  </MakerModeContext.Provider>;
}

/** Mount once in G's shell; pass the current route, actual build version and existing logo handler. */
export function useMakerMode(pathname: string, sensitiveSurface = false) {
  const { enabled, eggsEnabled } = useDelight();
  const allowed = enabled && eggsEnabled && !sensitiveSurface && eggsAllowed(pathname);
  const [active, setActive] = useState(false);
  const index = useRef(0), lastKey = useRef(0);
  const dismiss = useCallback(() => setActive(false), []);
  // A route change closes Maker mode, unless a seventh logo click just led here (logoClicks.ts).
  useEffect(() => { dismiss(); index.current = 0; if (allowed && makerModePending()) setActive(true); }, [pathname, allowed, dismiss]);
  useEffect(() => {
    if (!allowed) return;
    const keydown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.repeat || event.isComposing || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey || ignoreTarget(event.target)) { index.current = 0; return; }
      if (Date.now() - lastKey.current > 2500) index.current = 0;
      lastKey.current = Date.now();
      const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
      if (key === sequence[index.current]) index.current += 1;
      else index.current = key === sequence[0] ? 1 : 0;
      if (index.current === sequence.length) { setActive(value => !value); index.current = 0; }
      if (event.key === "Escape") { clearMakerModePending(); dismiss(); }
    };
    window.addEventListener("keydown", keydown);
    return () => window.removeEventListener("keydown", keydown);
  }, [allowed, dismiss]);
  useEffect(() => {
    if (!active || !allowed) return;
    const timeout = window.setTimeout(() => setActive(false), 12000);
    return () => window.clearTimeout(timeout);
  }, [active, allowed]);
  useEffect(() => {
    if (allowed && !greeted) {
      console.info("Space Works · Built by makers. Explore the API documentation at /docs/.");
      greeted = true;
    }
  }, [allowed]);
  // Seven logo clicks in a rolling 4 s window open Maker mode, here or on the page the logo leads to.
  const activateLogo = useCallback(() => { if (allowed && countLogoClick()) setActive(true); }, [allowed]);
  return { allowed, active: allowed && active, dismiss: () => { clearMakerModePending(); dismiss(); }, activateLogo,
    toggle: () => { if (allowed) setActive(value => !value); } };
}

export function MakerModePanel({ mode, version }: { mode: ReturnType<typeof useMakerMode>; version: string }) {
  if (!mode.allowed) return null;
  return <>
    {mode.active ? <div aria-hidden="true" className="sw-blueprint-decoration pointer-events-none fixed inset-0 -z-10" /> : null}
    <div className="sr-only" role="status">{mode.active ? "Maker mode on. Workshop grid enabled for 12 seconds." : "Maker mode off."}</div>
    {mode.active ? <aside aria-label="Built by makers" className="fixed bottom-4 right-4 z-40 max-w-xs rounded-2xl border border-line bg-panel p-5 text-ink shadow-overlay">
      <p className="font-medium">Built by makers</p><p className="text-sm text-muted">Space Works {version}</p>
      <p className="text-sm text-muted">Workshop grid enabled for 12 seconds.</p>
      <button type="button" className="desk-button mt-3" onClick={mode.dismiss}>Dismiss maker mode</button>
    </aside> : null}
  </>;
}

export function MakerModeToggle({ mode }: { mode: ReturnType<typeof useMakerMode> }) {
  if (!mode.allowed) return null;
  return <button type="button" className="desk-button" aria-pressed={mode.active} onClick={mode.toggle}>Maker mode: {mode.active ? "on" : "off"}</button>;
}
