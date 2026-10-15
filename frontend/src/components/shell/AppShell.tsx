import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
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
  return <div className="min-h-dvh bg-bg text-ink" data-app-shell={props.variant}>
    <SkipLink />
    <div className="fixed inset-y-0 left-0 z-30 hidden w-[264px] border-r border-line lg:flex"><Sidebar {...shellProps} /></div>
    <div className="min-w-0 lg:ml-[264px]">
      <MobileTopBar {...shellProps} unread={unread} onMenu={openNavigation} />
      <main id="main-content" tabIndex={-1} className={`min-w-0 p-5 lg:p-9 ${focusRing} ${compactNav === "bottom-tabs" ? "pb-24" : ""}`}>{children}</main>
    </div>
    <SidebarDrawer open={drawer} onClose={() => setDrawer(false)}><Sidebar {...shellProps} onNavigate={() => setDrawer(false)} /></SidebarDrawer>
    {compactNav === "bottom-tabs" ? <BottomTabs items={items} activeKey={activeKey} label={props.variant === "staff" ? "Staff quick navigation" : "Member quick navigation"} onMore={openNavigation} /> : null}
  </div>;
}
