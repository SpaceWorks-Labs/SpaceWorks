import { t } from "@lingui/core/macro";
import { useId, useState } from "react";
import { ChevronDown } from "lucide-react";
import { Collapse } from "../ui/Collapse";
import { readStorage, writeStorage } from "../../lib/safeStorage";
import { SidebarItem } from "./SidebarItem";
import { focusRing, type ShellSection } from "./types";

export function SidebarSection({ section, activeKey, owner, onNavigate }: {
  section: ShellSection; activeKey: string; owner: string; onNavigate?: () => void;
}) {
  const id = useId();
  const storageKey = `sidebar:${owner}:${section.key}`;
  const [expanded, setExpanded] = useState(() => readStorage(storageKey) === "open");
  const all = [...section.items, ...section.more ?? []];
  const flat = all.length <= 4;
  const containsActive = all.some(item => item.key === activeKey || item.children?.some(child => child.key === activeKey));
  const open = expanded || containsActive;
  if (!all.length) return null;
  return <section className="space-y-1">
    {section.label ? <p className="px-2.5 pt-5 pb-1 text-xs font-semibold uppercase tracking-widest text-muted">{section.label}</p> : null}
    {section.caption ? <p className="px-2.5 pb-2 text-xs text-muted">{section.caption}</p> : null}
    <ul className="space-y-1">{(flat ? all : section.items).map(item => <SidebarItem key={item.key} item={item} activeKey={activeKey} onNavigate={onNavigate} />)}</ul>
    {!flat && section.more?.length ? <>
      <button type="button" aria-expanded={open} aria-controls={id}
        className={`flex min-h-11 w-full items-center gap-2 rounded-lg px-2.5 text-sm text-muted hover:bg-sidebar-hover ${focusRing}`}
        onClick={() => { setExpanded(!open); writeStorage(storageKey, open ? "closed" : "open"); }}>
        <ChevronDown aria-hidden="true" size={24} className={`transition-transform duration-[var(--sw-dur-base)] ${open ? "rotate-180" : ""}`} />{t`More (${section.more.length})`}<span className="sr-only">{" "}{t`in ${section.label ?? ""}`}</span>
      </button>
      <Collapse open={open} id={id}><ul className="space-y-1">{section.more.map(item => <SidebarItem key={item.key} item={item} activeKey={activeKey} onNavigate={onNavigate} />)}</ul></Collapse>
    </> : null}
  </section>;
}
