import { Menu, Search } from "lucide-react";
import { SpaceWorksLogo } from "../SpaceWorksLogo";
import { UserMenu } from "./UserMenu";
import { focusRing, type AppShellProps } from "./types";

export function MobileTopBar({ workspace, user, search, unread, onMenu }: Pick<AppShellProps, "workspace" | "user" | "search"> & { unread: number; onMenu: () => void }) {
  return <header className="flex min-h-14 items-center gap-2 border-b border-line bg-sidebar px-3 lg:hidden">
    <button type="button" aria-label={`Open navigation${unread > 0 ? `, ${unread} unread` : ""}`} aria-haspopup="dialog"
      className={`flex min-h-11 min-w-11 items-center justify-center rounded-lg hover:bg-sidebar-hover ${focusRing}`} onClick={onMenu}><Menu aria-hidden="true" size={24} /></button>
    <SpaceWorksLogo variant="symbol" size={48} />
    <span className="min-w-0 flex-1 truncate text-sm font-semibold">{workspace?.name ?? "Choose a space"}</span>
    {search ? <button type="button" aria-label={search.label} onClick={search.onOpen}
      className={`flex min-h-11 min-w-11 items-center justify-center rounded-lg hover:bg-sidebar-hover ${focusRing}`}><Search aria-hidden="true" size={24} /></button> : null}
    <div className="w-12 shrink-0"><UserMenu user={user} above={false} compact /></div>
  </header>;
}
