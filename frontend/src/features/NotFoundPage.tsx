import { t } from "@lingui/core/macro";
import { useLocation } from "react-router-dom";
import { CenteredCardLayout } from "../components/layouts";
import { useRef, useState } from "react";
import { NotFoundPatch } from "../components/delight/NotFoundPatch";
import { eggsAllowed, useDelight, useReducedMotion } from "../components/delight/DelightProvider";

/** The one not-found page. Unknown routes and unpublished profiles render it identically. */
export function NotFoundPage() {
  const { pathname } = useLocation();
  const { enabled } = useDelight();
  const reduced = useReducedMotion();
  const [torn, setTorn] = useState(false);
  const dragStart = useRef<number | null>(null);
  const match = pathname.match(/^\/m\/([^/]+)/);
  const inventory = match ? `/m/${encodeURIComponent(match[1])}` : "/";
  // Patch is the 404's one bold moment; kiosk, scanner and payment paths stay plain.
  const patch = enabled && eggsAllowed(pathname);
  return <><CenteredCardLayout state={{ status: "ready" }} media={{ icon: "Compass", tone: "accent" }}
    eyebrow="404" title={enabled ? t`Loan slip not found` : t`We couldn't find that page`} body="The link may be old, or the page moved."
    content={enabled ? <div className="grid gap-4">
      {!torn ? <div className="rounded-2xl border border-dashed border-line bg-panel p-5"
        onPointerDown={event => { dragStart.current = event.clientY; }}
        onPointerUp={event => { if (dragStart.current !== null && Math.abs(event.clientY - dragStart.current) >= 40) setTorn(true); dragStart.current = null; }}
        onPointerCancel={() => { dragStart.current = null; }}>
        <dl className="grid gap-2 text-sm"><div><dt className="font-medium">{t`Item`}</dt><dd className="break-all">{pathname}</dd></div>
          <div><dt className="font-medium">{t`Status`}</dt><dd>{t`Not on the shelf`}</dd></div></dl>
      </div> : <div aria-hidden="true" className={`h-4 rounded-control border-t border-dashed border-line ${reduced ? "" : "sw-delight-pass"}`} />}
      <button type="button" className="desk-button" onClick={() => setTorn(true)} disabled={torn}>{t`Tear off the tag`}</button>
      <p role="status">{torn ? t`Tag removed. Browse the inventory to find your next tool.` : t`Drag the tag or use the button to tear it off.`}</p>
    </div> : undefined}
    primary={{ label: t`Browse the inventory`, href: inventory }}
    escape={pathname.startsWith("/admin") ? { label: t`Staff sign-in`, href: "/admin" } : undefined} />
    {/* The spacer lets the card scroll clear of Patch's fixed strip on short screens. */}
    {patch ? <><div aria-hidden="true" className="h-28" /><NotFoundPatch /></> : null}</>;
}
