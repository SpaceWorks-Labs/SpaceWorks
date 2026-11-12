import { t } from "@lingui/core/macro";
import { Menu, X } from "lucide-react";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { AnimatedLogoMark } from "../../components/brand/AnimatedLogoMark";
import { ThemeToggle } from "../../components/ThemeToggle";
import { ExternalLink } from "./ExternalLink";
import { GITHUB_URL } from "./hubLinks";

type NavItem = { label: string; to: string; match: (path: string) => boolean };

function navItems(): NavItem[] {
  return [
    { label: t`Home`, to: "/", match: path => path === "/" },
    { label: t`Features`, to: "/features", match: path => path.startsWith("/features") },
    { label: t`Spaces`, to: "/spaces", match: path => path.startsWith("/spaces") },
    { label: t`Docs`, to: "/docs", match: path => path === "/docs" || path.startsWith("/docs/") },
  ];
}

/**
 * The hub's own bar for the landing page and /docs: the Space Works lockup, Home · Spaces · Docs ·
 * GitHub, the theme switch and Sign in. `tools` slots page controls (the docs search) before them.
 */
export function HubHeader({ tools }: { tools?: ReactNode }) {
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => { setOpen(false); }, [pathname]);
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape); };
  }, [open]);
  const items = navItems();
  const links = (stacked: boolean) => <>
    {items.map(item => {
      const current = item.match(pathname);
      return <Link key={item.to} to={item.to} aria-current={current ? "page" : undefined}
        className={`sw-hub-nav-link ${stacked ? "w-full" : ""}`}>{item.label}</Link>;
    })}
    <ExternalLink href={GITHUB_URL} label={t`GitHub: the Space Works repository (opens in a new tab)`}
      className={`sw-hub-nav-link ${stacked ? "w-full" : ""}`}>{t`GitHub`}</ExternalLink>
  </>;
  return <header className="sw-hub-header">
    <div ref={root} className="sw-hub-bar">
      <Link to="/" className="sw-hub-logo" data-sw-logo-target aria-label={t`Space Works home`}>
        <span className="inline-flex sm:hidden"><AnimatedLogoMark variant="symbol" size={48} decorative /></span>
        <span className="hidden sm:inline-flex"><AnimatedLogoMark variant="horizontal" size={240} decorative /></span>
      </Link>
      <nav aria-label={t`Main`} className="hidden items-center gap-1 lg:flex">{links(false)}</nav>
      <div className="ml-auto flex items-center gap-2">
        {tools}
        {/* Below lg the nav folds into the menu; Docs stays one tap away (on /docs the search takes its place). */}
        {tools ? null : <span className="lg:hidden"><Link to="/docs" className="sw-hub-nav-link">{t`Docs`}</Link></span>}
        <span className="hidden lg:inline-flex"><ThemeToggle variant="icon" /></span>
        <Link to="/member" className="desk-button whitespace-nowrap">{t`Sign in`}</Link>
        <button type="button" className="desk-button min-w-11 px-3 lg:hidden" aria-expanded={open} aria-controls={panelId}
          onClick={() => setOpen(value => !value)}>
          {open ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}<span className="sr-only">{t`Menu`}</span>
        </button>
      </div>
      {open ? <div id={panelId} className="sw-hub-menu lg:hidden">
        <nav aria-label={t`Main`} className="grid gap-1">{links(true)}</nav>
        <div className="flex items-center justify-between gap-3 border-t border-line pt-3">
          <span className="text-sm text-muted">{t`Appearance`}</span><ThemeToggle variant="icon" />
        </div>
      </div> : null}
    </div>
  </header>;
}
