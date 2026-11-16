import { t } from "@lingui/core/macro";
import { Maximize2, X } from "lucide-react";
import { useEffect, useId, useRef, useState, useSyncExternalStore } from "react";
import { currentTheme, subscribeTheme } from "../../lib/theme";

// Mermaid is ~1 MB of JavaScript: it loads only when a page actually contains a diagram, from its
// own chunk, and re-renders when the theme flips. `securityLevel: "strict"` keeps diagram labels as
// text (no HTML, no click handlers); Mermaid sanitises its SVG output before it reaches the page.

const LIGHT = { background: "#FFFFFF", primaryColor: "#E0EEEC", primaryTextColor: "#142C2A", primaryBorderColor: "#006E63",
  lineColor: "#5B6863", secondaryColor: "#FFFAE9", tertiaryColor: "#F6ECE0", noteBkgColor: "#FFFAE9", noteTextColor: "#142C2A" };
const DARK = { background: "#0F201E", primaryColor: "#0D2C29", primaryTextColor: "#FFF4E8", primaryBorderColor: "#ABC8BC",
  lineColor: "#C7C4BA", secondaryColor: "#202D21", tertiaryColor: "#172E2B", noteBkgColor: "#202D21", noteTextColor: "#FFF4E8" };

/** Natural size from the SVG viewBox, so inline diagrams can refuse to shrink below readable labels. */
export function naturalSize(svg: string): { width: number; height: number } | null {
  const box = /viewBox="[-\d.]+\s+[-\d.]+\s+([\d.]+)\s+([\d.]+)"/.exec(svg);
  return box ? { width: Number(box[1]), height: Number(box[2]) } : null;
}
// Mermaid labels are 16px at natural size; 0.75 keeps them at 12px or larger.
const MIN_SCALE = 0.75;

function EnlargedDiagram({ svg, width, onClose }: { svg: string; width?: number; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const node = dialog.current;
    if (node && !node.open) { if (typeof node.showModal === "function") node.showModal(); else node.setAttribute("open", ""); }
  }, []);
  // close() restores focus to the opening button; its "close" event then unmounts the dialog.
  const dismiss = () => { const node = dialog.current; if (node && typeof node.close === "function") node.close(); else onClose(); };
  // A native modal dialog traps focus, closes on Esc and returns focus to the opening button.
  return <dialog ref={dialog} className="sw-doc-dialog" aria-label={t`Diagram, full size`} onClose={onClose}>
    <button type="button" className="sw-doc-dialog-close" onClick={dismiss} aria-label={t`Close full-size diagram`}><X aria-hidden size={18} /></button>
    <div className="sw-doc-dialog-scroll" tabIndex={0} role="group" aria-label={t`Diagram, scroll to pan`}>
      <div className="sw-doc-dialog-svg" style={width ? { width } : undefined}
        // Mermaid's own sanitised SVG output under securityLevel "strict".
        dangerouslySetInnerHTML={{ __html: svg }} />
    </div>
  </dialog>;
}

// Mermaid keeps one scratch element per render id and shares global state, so overlapping renders
// (several diagrams on a page, or a development double-effect) can come back empty. Render one at a
// time, each under its own id.
let queue: Promise<unknown> = Promise.resolve();
let renderCount = 0;
function renderQueued(draw: () => Promise<string>): Promise<string> {
  const next = queue.then(draw, draw);
  queue = next.catch(() => undefined);
  return next;
}

export function MermaidDiagram({ code }: { code: string }) {
  const theme = useSyncExternalStore(subscribeTheme, currentTheme, () => "light");
  const id = `sw-mermaid-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const [enlarged, setEnlarged] = useState(false);
  const [state, setState] = useState<{ svg?: string; failed?: boolean }>({});
  useEffect(() => {
    let live = true;
    void import("mermaid").then(async ({ default: mermaid }) => {
      const svg = await renderQueued(async () => {
        mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "base",
          fontFamily: "Outfit, ui-sans-serif, system-ui, sans-serif", themeVariables: theme === "dark" ? DARK : LIGHT });
        return (await mermaid.render(`${id}-${theme}-${++renderCount}`, code)).svg;
      });
      if (live && svg) setState({ svg });
    }).catch(() => { if (live) setState({ failed: true }); });
    return () => { live = false; };
  }, [code, id, theme]);
  if (state.failed) {
    return <figure className="sw-doc-code"><figcaption className="sw-doc-code-bar"><span className="sw-doc-code-lang">{t`Diagram source (could not draw it)`}</span></figcaption>
      <pre className="sw-doc-pre" tabIndex={0}><code>{code}</code></pre></figure>;
  }
  if (!state.svg) return <div role="status" className="sw-doc-diagram text-sm text-muted">{t`Drawing diagram…`}</div>;
  const size = naturalSize(state.svg);
  return <figure className="sw-doc-diagram">
    <button type="button" className="sw-doc-diagram-enlarge" onClick={() => setEnlarged(true)} aria-label={t`View diagram full size`}>
      <Maximize2 aria-hidden size={16} /><span>{t`Enlarge`}</span>
    </button>
    <div className="sw-doc-diagram-inline" role="img" aria-label={t`Diagram`}
      style={size ? { ["--diagram-min" as string]: `${Math.round(size.width * MIN_SCALE)}px` } : undefined}
      // Mermaid's own sanitised SVG output under securityLevel "strict".
      dangerouslySetInnerHTML={{ __html: state.svg }} />
    {enlarged && <EnlargedDiagram svg={state.svg} width={size?.width} onClose={() => setEnlarged(false)} />}
  </figure>;
}
