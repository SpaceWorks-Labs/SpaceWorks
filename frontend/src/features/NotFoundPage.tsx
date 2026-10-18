import { useLocation } from "react-router-dom";
import { CenteredCardLayout } from "../components/layouts";
import { useRef, useState } from "react";
import { Companion } from "../components/delight/Companion";
import { DelightArt } from "../components/delight/Artwork";
import { useDelight, useReducedMotion } from "../components/delight/DelightProvider";

/** The one not-found page. Unknown routes and unpublished profiles render it identically. */
export function NotFoundPage() {
  const { pathname } = useLocation();
  const { enabled } = useDelight();
  const reduced = useReducedMotion();
  const [torn, setTorn] = useState(false);
  const dragStart = useRef<number | null>(null);
  const match = pathname.match(/^\/m\/([^/]+)/);
  const inventory = match ? `/m/${encodeURIComponent(match[1])}` : "/";
  return <CenteredCardLayout state={{ status: "ready" }} media={{ icon: "Compass", tone: "accent" }}
    eyebrow="404" title={enabled ? "Loan slip not found" : "We couldn't find that page"} body="The link may be old, or the page moved."
    content={enabled ? <div className="grid gap-4">
      {!torn ? <div className="rounded-2xl border border-dashed border-line bg-panel p-5"
        onPointerDown={event => { dragStart.current = event.clientY; }}
        onPointerUp={event => { if (dragStart.current !== null && Math.abs(event.clientY - dragStart.current) >= 40) setTorn(true); dragStart.current = null; }}
        onPointerCancel={() => { dragStart.current = null; }}>
        <DelightArt name="tag" className="h-24 w-full" />
        <dl className="grid gap-2 text-sm"><div><dt className="font-medium">Item</dt><dd className="break-all">{pathname}</dd></div>
          <div><dt className="font-medium">Status</dt><dd>Not on the shelf</dd></div></dl>
      </div> : <div aria-hidden="true" className={`h-4 rounded-control border-t border-dashed border-line ${reduced ? "" : "sw-delight-pass"}`} />}
      <button type="button" className="desk-button" onClick={() => setTorn(true)} disabled={torn}>Tear off the tag</button>
      <p role="status">{torn ? "Tag removed. Browse the inventory to find your next tool." : "Drag the tag or use the button to tear it off."}</p>
      <Companion />
    </div> : undefined}
    primary={{ label: "Browse the inventory", href: inventory }}
    escape={pathname.startsWith("/admin") ? { label: "Staff sign-in", href: "/admin" } : undefined} />;
}
