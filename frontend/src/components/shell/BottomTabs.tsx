import { Ellipsis } from "lucide-react";
import { Link } from "react-router-dom";
import { navKeys } from "./navKeys";
import { focusRing, type ShellItem } from "./types";

export function BottomTabs({ items, activeKey, label, onMore }: { items: ShellItem[]; activeKey: string; label: string; onMore: () => void }) {
  const active = items.find(item => item.key === activeKey);
  const visible = items.length <= 5 ? items : active && items.indexOf(active) > 3 ? [...items.slice(0, 3), active] : items.slice(0, 4);
  return <nav aria-label={label} onKeyDown={event => navKeys(event, "horizontal")} className="sw-bottom-tabs fixed inset-x-0 bottom-0 z-30 flex min-h-16 border-t border-line bg-sidebar pr-[env(safe-area-inset-right)] pb-[env(safe-area-inset-bottom)] pl-[env(safe-area-inset-left)] lg:hidden">
    {visible.map(item => { const Glyph = item.icon; return <Link key={item.key} to={item.href} aria-current={item.key === activeKey ? "page" : undefined}
      aria-label={item.badge ? `${item.label}, ${item.badge} ${item.badgeLabel ?? "needs action"}` : undefined}
      onClick={item.onSelect} className={`flex min-h-16 min-w-0 flex-1 flex-col items-center justify-center gap-1 px-1 text-center text-xs ${focusRing} ${item.key === activeKey ? "bg-sidebar-active text-on-accent" : "text-ink hover:bg-sidebar-hover"}`}>
      <Glyph aria-hidden="true" size={24} strokeWidth={2} /><span className="line-clamp-2 max-w-full break-words">{item.label}{item.badge ? <span aria-hidden="true"> {item.badge > 99 ? "99+" : item.badge}</span> : null}</span>
    </Link>; })}
    {items.length > 5 ? <button type="button" onClick={onMore} className={`flex min-h-16 flex-1 flex-col items-center justify-center text-xs ${focusRing}`}><Ellipsis aria-hidden="true" size={24} />More</button> : null}
  </nav>;
}
