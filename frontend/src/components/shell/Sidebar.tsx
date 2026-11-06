import { t } from "@lingui/core/macro";
import { useEffect, useRef } from "react";
import { Search } from "lucide-react";
import { SpaceWorksLogo } from "../SpaceWorksLogo";
import { ActionControl } from "../ui";
import { SidebarSection } from "./SidebarSection";
import { WorkspaceSwitcher } from "./WorkspaceSwitcher";
import { UserMenu } from "./UserMenu";
import { navKeys } from "./navKeys";
import { focusRing, type AppShellProps } from "./types";

export function Sidebar({ variant, workspace, search, nav, activeKey, footerLinks = [], user, status, onNavigate }: Omit<AppShellProps, "children" | "compactNav"> & { onNavigate?: () => void }) {
  const root = useRef<HTMLElement>(null);
  useEffect(() => { root.current?.querySelector('[aria-current="page"]')?.scrollIntoView?.({ block: "nearest" }); }, [activeKey]);
  return <aside ref={root} className="flex h-full min-h-0 w-full flex-col bg-sidebar pl-[env(safe-area-inset-left)] text-ink dark:border-r dark:border-line">
    <div className="shrink-0 space-y-2 px-3.5 pb-3">
      <div className="flex items-center justify-center"><SpaceWorksLogo variant="stacked" size={180} /></div>
      <WorkspaceSwitcher workspace={workspace} />
      {search ? <button type="button" aria-label={search.label} aria-haspopup="dialog" onClick={search.onOpen}
        className={`flex min-h-11 w-full items-center gap-2 rounded-lg bg-sidebar px-2.5 text-sm hover:bg-sidebar-hover dark:bg-panel dark:hover:bg-hover ${focusRing}`}>
        <Search aria-hidden="true" size={24} /><span className="flex-1 text-left">{t`Search or jump to…`}</span><kbd className="text-xs">{t`Ctrl/⌘ K`}</kbd>
      </button> : null}
    </div>
    <nav aria-label={variant === "staff" ? t`Staff sections` : t`Member portal`}
      data-sidebar-scroll onKeyDown={event => navKeys(event, "vertical")} className="min-h-0 flex-1 space-y-2 overflow-y-auto overscroll-contain px-3.5 pb-4">
      {nav.map(section => <SidebarSection key={`${user.name}:${section.key}`} section={section} activeKey={activeKey} owner={user.name} onNavigate={onNavigate} />)}
      {footerLinks.map(action => <ActionControl key={action.label} action={action} className="w-full justify-start" />)}
    </nav>
    <div className="shrink-0 space-y-2 border-t border-line p-3.5 pb-[max(0.875rem,env(safe-area-inset-bottom))]">{status}<UserMenu user={user} /></div>
  </aside>;
}
