import { Link } from "react-router-dom";
import { focusRing, type ShellItem } from "./types";

export function SidebarItem({ item, activeKey, onNavigate }: { item: ShellItem; activeKey: string; onNavigate?: () => void }) {
  const Glyph = item.icon;
  const current = activeKey === item.key;
  const badge = item.badge ?? 0;
  return <li>
    <Link to={item.href} aria-current={current ? "page" : undefined}
      aria-label={badge > 0 ? `${item.label}, ${badge} ${item.badgeLabel ?? "needs action"}` : item.label}
      onFocus={event => event.currentTarget.scrollIntoView?.({ block: "nearest" })}
      onClick={() => { item.onSelect?.(); onNavigate?.(); }}
      className={`flex min-h-11 items-center gap-2.5 rounded-lg border px-2.5 py-2 text-[15px] ${focusRing} ${current ? "border-accent-ink bg-sidebar-active font-semibold text-on-accent" : "border-transparent text-ink hover:bg-sidebar-hover"}`}>
      <Glyph aria-hidden="true" size={24} strokeWidth={2} className="shrink-0" />
      <span className="min-w-0 flex-1 break-words">{item.label}</span>
      {badge > 0 ? <span aria-hidden="true" className={`rounded-full px-2 text-xs tabular-nums ${current ? "bg-panel text-ink" : "bg-accent-soft text-accent-ink"}`}>{badge > 99 ? "99+" : badge}</span> : null}
    </Link>
    {item.children?.length ? <ul className="ml-6 space-y-1 border-l border-line pl-2">
      {item.children.map(child => <SidebarItem key={child.key} item={child} activeKey={activeKey} onNavigate={onNavigate} />)}
    </ul> : null}
  </li>;
}
