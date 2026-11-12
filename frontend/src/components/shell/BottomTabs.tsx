import { t } from "@lingui/core/macro";
import { Ellipsis } from "lucide-react";
import { TransitionLink as Link } from "../../lib/motion";
import { navKeys } from "./navKeys";
import { focusRing, type ShellItem } from "./types";

export function BottomTabs({ items, activeKey, label, onMore, more = false, moreOpen = false }: { moreOpen?: boolean; items: ShellItem[]; activeKey: string; label: string; onMore: () => void;
  /** The caller picked a short list: always offer "More" for the rest of the menu. */ more?: boolean }) {
  const active = items.find(item => item.key === activeKey);
  const showMore = more || items.length > 5;
  const visible = !showMore ? items : active && items.indexOf(active) > 3 ? [...items.slice(0, 3), active] : items.slice(0, 4);
  return <nav aria-label={label} onKeyDown={event => navKeys(event, "horizontal")} className="sw-bottom-tabs fixed inset-x-0 bottom-0 z-30 flex min-h-16 border-t border-line bg-sidebar pr-[env(safe-area-inset-right)] pb-[env(safe-area-inset-bottom)] pl-[env(safe-area-inset-left)] lg:hidden">
    {visible.map(item => { const Glyph = item.icon; return <Link key={item.key} to={item.href} aria-current={item.key === activeKey ? "page" : undefined}
      onClick={item.onSelect} className={`flex min-h-16 min-w-0 flex-1 flex-col items-center justify-center gap-1 px-1 text-center text-xs ${focusRing} ${item.key === activeKey ? "bg-sidebar-active text-on-accent" : "text-ink hover:bg-sidebar-hover"}`}>
      <Glyph aria-hidden="true" size={24} strokeWidth={2} /><span className="line-clamp-2 max-w-full break-words">{item.label}{item.badge ? <>{" "}<span>{item.badge > 99 ? "99+" : item.badge}</span>{" "}<span className="sr-only">{item.badge > 99 ? `(${item.badge} ${item.badgeLabel ?? t`needs action`})` : item.badgeLabel ?? t`needs action`}</span></> : null}</span>
    </Link>; })}
    {showMore ? <button type="button" onClick={onMore} aria-haspopup="dialog" aria-expanded={moreOpen} className={`flex min-h-16 flex-1 flex-col items-center justify-center text-xs ${focusRing}`}><Ellipsis aria-hidden="true" size={24} />{t`More`}</button> : null}
  </nav>;
}
