import { Menu, Search } from "lucide-react";
import { SpaceWorksLogo } from "../SpaceWorksLogo";
import { UserMenu } from "./UserMenu";
import { focusRing, type AppShellProps } from "./types";

export function MobileTopBar({ workspace, user, search, unread, onMenu }: Pick<AppShellProps, "workspace" | "user" | "search"> & { unread: number; onMenu: () => void }) {
  // Sticky so navigation and search stay one tap away; pads for the notch/status bar under viewport-fit=cover.
  return <header className="sticky top-0 z-20 flex min-h-[calc(3.5rem+env(safe-area-inset-top))] items-center gap-2 border-b border-line bg-sidebar pt-[env(safe-area-inset-top)] pr-[max(0.75rem,env(safe-area-inset-right))] pl-[max(0.75rem,env(safe-area-inset-left))] lg:hidden">
    <button type="button" aria-label={`Open navigation${unread > 0 ? `, ${unread} unread` : ""}`} aria-haspopup="dialog"
      className={`flex min-h-11 min-w-11 items-center justify-center rounded-lg hover:bg-sidebar-hover ${focusRing}`} onClick={onMenu}><Menu aria-hidden="true" size={24} /></button>
    <SpaceWorksLogo variant="symbol" size={48} />
    <span className="min-w-0 flex-1 truncate text-sm font-semibold" title={workspace?.name}>{workspace?.name ?? "Choose a space"}</span>
    {search ? <button type="button" aria-label={search.label} onClick={search.onOpen}
      className={`flex min-h-11 min-w-11 items-center justify-center rounded-lg hover:bg-sidebar-hover ${focusRing}`}><Search aria-hidden="true" size={24} /></button> : null}
    <div className="w-12 shrink-0"><UserMenu user={user} above={false} compact /></div>
  </header>;
}
