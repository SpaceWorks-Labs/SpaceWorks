import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { ContentTarget } from "../layouts/LayoutFrame";
import { SkipLink } from "../SkipLink";
import { Sidebar } from "./Sidebar";
import { MobileTopBar } from "./MobileTopBar";
import { SidebarDrawer } from "./SidebarDrawer";
import { BottomTabs } from "./BottomTabs";
import { focusRing, type AppShellProps } from "./types";

export function AppShell(props: AppShellProps) {
  const { nav, activeKey, compactNav, children } = props;
  const [drawer, setDrawer] = useState(false);
  const location = useLocation();
  const route = `${location.pathname}${location.search}${location.hash}`;
  const previousRoute = useRef(route);
  useEffect(() => {
    if (previousRoute.current === route) return;
    previousRoute.current = route;
    setDrawer(false);
    // Run after the drawer's dialog cleanup restores its trigger.
    const frame = requestAnimationFrame(() => document.getElementById("main-content")?.focus());
    return () => cancelAnimationFrame(frame);
  }, [route]);
  const openSearch = () => {
    if (drawer) {
      setDrawer(false);
      requestAnimationFrame(() => props.search?.onOpen());
    } else props.search?.onOpen();
  };
  useEffect(() => {
    if (!drawer || !props.search) return;
    const keydown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k" && document.querySelectorAll('[role="dialog"]').length === 1) {
        event.preventDefault(); event.stopImmediatePropagation(); openSearch();
      }
    };
    document.addEventListener("keydown", keydown, true);
    return () => document.removeEventListener("keydown", keydown, true);
  });
  const shellProps = { ...props, search: props.search ? { ...props.search, onOpen: openSearch } : undefined };
  const items = nav.flatMap(section => [...section.items, ...section.more ?? []]);
  const unread = items.find(item => item.badgeLabel === "unread")?.badge ?? 0;
  const openNavigation = () => setDrawer(true);
  // Phone and tablet: top bar + drawer (+ bottom tabs for the member portal). Desktop: fixed sidebar.
  // Content is capped so 1920/2560 monitors keep readable line lengths; the safe-area insets
  // (viewport-fit=cover) keep landscape notches and the home indicator off the content.
  return <div className="min-h-dvh bg-bg text-ink" data-app-shell={props.variant} data-bottom-tabs={compactNav === "bottom-tabs" ? "" : undefined}>
    <SkipLink />
    <div className="fixed inset-y-0 left-0 z-30 hidden w-[264px] border-r border-line lg:flex"><Sidebar {...shellProps} /></div>
    <div className="min-w-0 lg:ml-[264px]">
      <MobileTopBar {...shellProps} unread={unread} onMenu={openNavigation} />
      <main id="main-content" tabIndex={-1} className={`min-w-0 pt-5 pr-[max(1.25rem,env(safe-area-inset-right))] pb-[calc(2rem+var(--shell-bottom-tabs,0px))] pl-[max(1.25rem,env(safe-area-inset-left))] md:pt-7 lg:p-9 ${focusRing}`}>
        <div className="mx-auto w-full min-w-0 max-w-[1600px]"><ContentTarget.Provider value={true}>{children}</ContentTarget.Provider></div>
      </main>
    </div>
    <SidebarDrawer open={drawer} onClose={() => setDrawer(false)}><Sidebar {...shellProps} onNavigate={() => setDrawer(false)} /></SidebarDrawer>
    {compactNav === "bottom-tabs" ? <BottomTabs items={items} activeKey={activeKey} label={props.variant === "staff" ? "Staff quick navigation" : "Member quick navigation"} onMore={openNavigation} /> : null}
  </div>;
}
