import type { KeyboardEvent } from "react";
export function rovingItems(container: HTMLElement, selector: string): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(selector)).filter(item => {
    if (item.hasAttribute("disabled")) return false;
    for (let parent: HTMLElement | null = item; parent && parent !== container; parent = parent.parentElement) {
      if (parent.hidden || getComputedStyle(parent).display === "none") return false;
    }
    return true;
  });
}
/** Shared arrow/Home/End traversal for single-choice controls. */
export function rove(event: KeyboardEvent<HTMLElement>, selector: string, activate = false) {
  const keys = ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"];
  if (!keys.includes(event.key)) return;
  const items = rovingItems(event.currentTarget, selector);
  if (!items.length) return;
  event.preventDefault();
  const current = items.indexOf(document.activeElement as HTMLElement);
  const index = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1
    : (current + (["ArrowLeft", "ArrowUp"].includes(event.key) ? -1 : 1) + items.length) % items.length;
  items.forEach((item, i) => { item.tabIndex = i === index ? 0 : -1; });
  items[index].focus();
  if (activate) items[index].click();
}
