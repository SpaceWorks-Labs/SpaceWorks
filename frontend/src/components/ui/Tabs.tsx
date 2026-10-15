import { useId, type ReactNode } from "react";
import { RouteLink } from "./RouteLink";
import { rove } from "./useRovingFocus";
import type { Tab } from "./types";
export type TabsProps = { tabs: Tab[]; activeKey: string; label?: string;
  onChange?: (key: string) => void; children?: ReactNode };
const barClass = "flex min-w-0 overflow-x-auto border-b border-line px-1 [mask-image:linear-gradient(to_right,transparent,rgb(var(--color-ink))_8px,rgb(var(--color-ink))_calc(100%_-_8px),transparent)] focus-within:[mask-image:none]";
export function Tabs({ tabs, activeKey, label = "Page sections", onChange, children }: TabsProps) {
  const id = useId();
  const active = tabs.some(tab => tab.key === activeKey) ? activeKey : tabs[0]?.key;
  const content = tabs.map((tab, index) => {
    const selected = active === tab.key;
    const accessibleLabel = tab.count === undefined ? tab.label : `${tab.label} ${tab.count}`;
    const classes = `desk-tab min-w-11 inline-flex shrink-0 flex-none items-center gap-2 whitespace-nowrap ${selected ? "desk-tab-active" : ""}`;
    const body = <>{tab.label}{tab.count !== undefined ? <span className="font-normal tabular-nums text-muted">{` ${tab.count}`}</span> : null}</>;
    return onChange ? <button key={tab.key} id={`${id}-tab-${index}`} aria-controls={`${id}-panel`}
      role="tab" type="button" aria-label={accessibleLabel} aria-selected={selected}
      tabIndex={selected ? 0 : -1} className={classes} onClick={() => onChange(tab.key)}>{body}</button>
      : <RouteLink key={tab.key} href={tab.href} aria-label={accessibleLabel} aria-current={selected ? "page" : undefined}
        tabIndex={selected ? 0 : -1} className={classes}>{body}</RouteLink>;
  });
  return onChange ? <>
    <div role="tablist" aria-label={label} className={barClass}
      onKeyDown={event => rove(event, '[role="tab"]', true)}>{content}</div>
    <div id={`${id}-panel`} role="tabpanel" aria-labelledby={`${id}-tab-${tabs.findIndex(tab => tab.key === active)}`}
      tabIndex={0} className="grid min-w-0 gap-6">{children}</div>
  </> : <><nav aria-label={label} className={barClass}
    onKeyDown={event => rove(event, "a")}>{content}</nav>{children}</>;
}
