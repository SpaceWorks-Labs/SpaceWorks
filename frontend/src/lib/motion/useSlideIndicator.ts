import { useLayoutEffect, type RefObject } from "react";

/**
 * Positions `indicator` (absolutely placed inside `container`, which must be `position: relative`)
 * over the element matching `selector`. Only `transform` is transitioned (the box size is set
 * directly), and updates caused by resizing skip the transition so a collapsing section cannot
 * make the indicator lag behind its item. The indicator hides when nothing matches, and the
 * container gets `data-slide` once placed so CSS can drop the item's own highlight.
 */
export function useSlideIndicator(container: RefObject<HTMLElement | null>, indicator: RefObject<HTMLElement | null>, selector: string, key: unknown) {
  useLayoutEffect(() => {
    const host = container.current;
    const bar = indicator.current;
    if (!host || !bar) return;
    let placed = false;
    const place = (animate: boolean) => {
      const target = host.querySelector<HTMLElement>(selector);
      if (!target || !target.offsetWidth) { bar.style.opacity = "0"; host.removeAttribute("data-slide"); placed = false; return; }
      const box = target.getBoundingClientRect();
      const frame = host.getBoundingClientRect();
      const x = box.left - frame.left + host.scrollLeft - host.clientLeft;
      const y = box.top - frame.top + host.scrollTop - host.clientTop;
      bar.style.transition = animate && placed ? "" : "none";
      bar.style.width = `${box.width}px`;
      bar.style.height = `${box.height}px`;
      bar.style.transform = `translate(${x}px, ${y}px)`;
      bar.style.opacity = "1";
      host.setAttribute("data-slide", "");
      placed = true;
    };
    place(true);
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => place(false));
    observer.observe(host);
    Array.from(host.children).forEach(child => observer.observe(child));
    return () => observer.disconnect();
  }, [container, indicator, selector, key]);
}
