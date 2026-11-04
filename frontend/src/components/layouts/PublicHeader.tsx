import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { Menu, X } from "lucide-react";
import { MakerspaceBrand } from "../MakerspaceBrand";
import { SpaceWorksLogo } from "../SpaceWorksLogo";
import { RouteLink } from "../ui/RouteLink";
import { ActionControl } from "../ui";
import type { Action } from "../ui";
import { useLayoutMedia } from "./useLayoutMedia";

export type PublicHeaderProps = {
  makerspace: { name: string; logo?: string; slug: string; homeHref?: string };
  nav: { label: string; href: string }[];
  account: Action;
  liveStatus?: ReactNode;
  /** canvas: no bar, for pages that open with a brand field (landing, About). */
  chrome?: "bar" | "canvas";
};

/** Collapses the inline links into the menu as soon as they no longer fit beside the name. */
function useNavFits(enabled: boolean, navKey: string) {
  const slot = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const natural = useRef(0);
  const measuredKey = useRef(navKey);
  const [collapsed, setCollapsed] = useState(false);
  useLayoutEffect(() => {
    const room = slot.current;
    if (!enabled || !room || typeof ResizeObserver === "undefined") return;
    if (measuredKey.current !== navKey) { measuredKey.current = navKey; natural.current = 0; }
    const check = () => {
      const links = list.current;
      if (links) {
        natural.current = links.offsetWidth;
        if (links.offsetWidth > room.clientWidth + 1) setCollapsed(true);
      } else if (!natural.current || room.clientWidth >= natural.current) setCollapsed(false);
    };
    check();
    const observer = new ResizeObserver(check);
    observer.observe(room);
    if (list.current) observer.observe(list.current);
    return () => observer.disconnect();
  }, [enabled, collapsed, navKey]);
  return { slot, list, collapsed };
}

/** Name first, links next, then status and the account action at the end. Phones and tablets get a menu. */
export function PublicHeader({ makerspace, nav, account, liveStatus, chrome = "bar" }: PublicHeaderProps) {
  const compact = useLayoutMedia("(max-width: 1023px)");
  const { slot, list, collapsed } = useNavFits(!compact && nav.length > 0, nav.map(link => link.href).join("|"));
  const [open, setOpen] = useState(false);
  const menuRoot = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const inlineNav = !compact && !collapsed && nav.length > 0;
  const menuNav = !inlineNav && nav.length > 0;
  const menuStatus = compact && Boolean(liveStatus);
  const hasMenu = menuNav || menuStatus;
  useEffect(() => { if (!hasMenu) setOpen(false); }, [hasMenu]);
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => { if (!menuRoot.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);
  const centralIdentity = !makerspace.slug && makerspace.name === "Space Works" && !makerspace.logo;
  const links = (stacked: boolean) => <nav aria-label="Public navigation">
    <ul ref={stacked ? undefined : list} className={stacked ? "grid gap-1" : "flex w-max items-center gap-1"}>
      {nav.map(link => <li key={link.href}><ActionControl action={link}
        className={`border-transparent ${stacked ? "w-full justify-start" : "whitespace-nowrap"}`} /></li>)}
    </ul>
  </nav>;
  return <header className={chrome === "canvas" ? "bg-bg" : "border-b border-line bg-panel"}>
    <div className="sw-layout sw-layout-wide sw-public-chrome flex min-w-0 items-center gap-3 md:gap-4">
      <RouteLink href={makerspace.homeHref ?? `/m/${makerspace.slug}`}
        className="min-w-0 shrink rounded-control focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
        {centralIdentity ? <><span className="inline-flex sm:hidden"><SpaceWorksLogo variant="symbol" size={48} /></span>
          <span className="hidden sm:inline-flex"><SpaceWorksLogo variant="horizontal" size={288} /></span></>
          : <MakerspaceBrand name={makerspace.name} logoUrl={makerspace.logo} fallback="logo" wrap />}
      </RouteLink>
      <div ref={slot} className="flex min-w-0 flex-1 justify-end overflow-hidden">{inlineNav ? links(false) : null}</div>
      <div ref={menuRoot} className="relative flex shrink-0 items-center gap-2" onKeyDown={event => {
        if (event.key === "Escape" && open) { event.stopPropagation(); setOpen(false); trigger.current?.focus(); }
      }}>
        {liveStatus && !compact ? <div className="flex min-w-0 items-center gap-2">{liveStatus}</div> : null}
        {hasMenu ? <button ref={trigger} type="button" className="desk-button min-w-11 gap-2 px-3" aria-expanded={open}
          aria-controls={open ? menuId : undefined} onClick={() => setOpen(!open)}>
          {open ? <X aria-hidden="true" size={20} /> : <Menu aria-hidden="true" size={20} />}<span className={menuNav ? "max-sm:sr-only" : "sr-only"}>Menu</span>
        </button> : null}
        <ActionControl action={account} className="whitespace-nowrap" />
        {open && hasMenu ? <div id={menuId} className="absolute right-0 top-full z-40 mt-2 grid w-72 max-w-[calc(100vw-2rem)] gap-3 rounded-xl border border-line bg-panel p-2 shadow-overlay"
          onClick={event => { if ((event.target as HTMLElement).closest("a")) setOpen(false); }}>
          {menuNav ? links(true) : null}
          {menuStatus ? <div className={`flex flex-wrap items-center gap-2 px-1 ${menuNav ? "border-t border-line pt-3" : ""}`}>{liveStatus}</div> : null}
        </div> : null}
      </div>
    </div>
  </header>;
}
