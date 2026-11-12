import { t } from "@lingui/core/macro";
import { TransitionLink } from "../../lib/motion";
import { focusRing, type ShellItem } from "./types";

export function SidebarItem({ item, activeKey, onNavigate }: { item: ShellItem; activeKey: string; onNavigate?: () => void }) {
  const Glyph = item.icon;
  const current = activeKey === item.key;
  const badge = item.badge ?? 0;
  const badgeText = item.badgeLabel ?? t`needs action`;
  return <li>
    <TransitionLink to={item.href} aria-current={current ? "page" : undefined}
      onFocus={event => event.currentTarget.scrollIntoView?.({ block: "nearest" })}
      onClick={() => { item.onSelect?.(); onNavigate?.(); }}
      className={`sw-slide-item relative flex min-h-11 items-center gap-2.5 rounded-lg border transition-colors duration-[var(--sw-dur-fast)] motion-safe:active:scale-[0.98] px-2.5 py-2 text-[15px] ${focusRing} ${current ? "border-accent-ink bg-sidebar-active font-semibold text-on-accent" : "border-transparent text-ink hover:bg-sidebar-hover"}`}>
      <Glyph aria-hidden="true" size={24} strokeWidth={2} className="shrink-0" />
      <span className="min-w-0 flex-1 break-words">{item.label}</span>
      {badge > 0 ? <>{" "}<span className={`rounded-full px-2 text-xs tabular-nums ${current ? "bg-panel text-ink" : "bg-accent-soft text-accent-ink"}`}>{badge > 99 ? "99+" : badge}</span>{" "}
        <span className="sr-only">{badge > 99 ? t`(${badge} ${badgeText})` : badgeText}</span></> : null}
    </TransitionLink>
    {item.children?.length ? <ul className="ml-6 space-y-1 border-l border-line pl-2">
      {item.children.map(child => <SidebarItem key={child.key} item={child} activeKey={activeKey} onNavigate={onNavigate} />)}
    </ul> : null}
  </li>;
}
