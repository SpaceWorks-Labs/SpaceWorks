import { t } from "@lingui/core/macro";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { RouteLink } from "./RouteLink";
import { rove } from "./useRovingFocus";
import type { Tab } from "./types";
export type TabsProps = { tabs: Tab[]; activeKey: string; label?: string;
  onChange?: (key: string) => void; children?: ReactNode };
const barClass = "sw-tab-scroll relative flex min-w-0 overflow-x-auto overscroll-x-contain border-b border-line px-1";
type Fade = "none" | "start" | "end" | "both";

/** On a narrow screen the row scrolls sideways: edges fade where more tabs wait, and the active tab is kept in view. */
function useScrollAffordance(active: string | undefined, count: number) {
  const bar = useRef<HTMLDivElement>(null);
  const [fade, setFade] = useState<Fade>("none");
  useEffect(() => {
    const element = bar.current;
    if (!element) return;
    const update = () => {
      const start = element.scrollLeft > 1;
      const end = element.scrollLeft + element.clientWidth < element.scrollWidth - 1;
      setFade(start && end ? "both" : start ? "start" : end ? "end" : "none");
    };
    update();
    element.addEventListener("scroll", update, { passive: true });
    const observer = typeof ResizeObserver === "undefined" ? undefined : new ResizeObserver(update);
    observer?.observe(element);
    return () => { element.removeEventListener("scroll", update); observer?.disconnect(); };
  }, [count]);
  useEffect(() => {
    const element = bar.current;
    const current = element?.querySelector<HTMLElement>('[aria-selected="true"], [aria-current="page"]');
    if (!element || !current) return;
    const left = current.offsetLeft - 24;
    const right = current.offsetLeft + current.offsetWidth + 24 - element.clientWidth;
    if (left < element.scrollLeft) element.scrollLeft = Math.max(0, left);
    else if (right > element.scrollLeft) element.scrollLeft = right;
  }, [active]);
  return { bar, fade };
}

export function Tabs({ tabs, activeKey, label = t`Page sections`, onChange, children }: TabsProps) {
  const id = useId();
  const active = tabs.some(tab => tab.key === activeKey) ? activeKey : tabs[0]?.key;
  const { bar, fade } = useScrollAffordance(active, tabs.length);
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
    <div ref={bar} role="tablist" aria-label={label} className={barClass} data-fade={fade}
      onKeyDown={event => rove(event, '[role="tab"]', true)}>{content}</div>
    <div id={`${id}-panel`} role="tabpanel" aria-labelledby={`${id}-tab-${tabs.findIndex(tab => tab.key === active)}`}
      tabIndex={0} className="grid min-w-0 gap-6">{children}</div>
  </> : <><nav ref={bar} aria-label={label} className={barClass} data-fade={fade}
    onKeyDown={event => rove(event, "a")}>{content}</nav>{children}</>;
}
