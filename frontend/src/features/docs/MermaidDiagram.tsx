import { t } from "@lingui/core/macro";
import { useEffect, useId, useState, useSyncExternalStore } from "react";
import { currentTheme, subscribeTheme } from "../../lib/theme";

// Mermaid is ~1 MB of JavaScript: it loads only when a page actually contains a diagram, from its
// own chunk, and re-renders when the theme flips. `securityLevel: "strict"` keeps diagram labels as
// text (no HTML, no click handlers); Mermaid sanitises its SVG output before it reaches the page.

const LIGHT = { background: "#FFFFFF", primaryColor: "#E0EEEC", primaryTextColor: "#142C2A", primaryBorderColor: "#006E63",
  lineColor: "#5B6863", secondaryColor: "#FFFAE9", tertiaryColor: "#F6ECE0", noteBkgColor: "#FFFAE9", noteTextColor: "#142C2A" };
const DARK = { background: "#0F201E", primaryColor: "#0D2C29", primaryTextColor: "#FFF4E8", primaryBorderColor: "#ABC8BC",
  lineColor: "#C7C4BA", secondaryColor: "#202D21", tertiaryColor: "#172E2B", noteBkgColor: "#202D21", noteTextColor: "#FFF4E8" };

export function MermaidDiagram({ code }: { code: string }) {
  const theme = useSyncExternalStore(subscribeTheme, currentTheme, () => "light");
  const id = `sw-mermaid-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const [state, setState] = useState<{ svg?: string; failed?: boolean }>({});
  useEffect(() => {
    let live = true;
    void import("mermaid").then(async ({ default: mermaid }) => {
      mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "base",
        fontFamily: "Outfit, ui-sans-serif, system-ui, sans-serif", themeVariables: theme === "dark" ? DARK : LIGHT });
      const { svg } = await mermaid.render(`${id}-${theme}`, code);
      if (live) setState({ svg });
    }).catch(() => { if (live) setState({ failed: true }); });
    return () => { live = false; };
  }, [code, id, theme]);
  if (state.failed) {
    return <figure className="sw-doc-code"><figcaption className="sw-doc-code-bar"><span className="sw-doc-code-lang">{t`Diagram source (could not draw it)`}</span></figcaption>
      <pre className="sw-doc-pre" tabIndex={0}><code>{code}</code></pre></figure>;
  }
  if (!state.svg) return <div role="status" className="sw-doc-diagram text-sm text-muted">{t`Drawing diagram…`}</div>;
  return <figure className="sw-doc-diagram" role="img" aria-label={t`Diagram`}
    // Mermaid's own sanitised SVG output under securityLevel "strict".
    dangerouslySetInnerHTML={{ __html: state.svg }} />;
}
