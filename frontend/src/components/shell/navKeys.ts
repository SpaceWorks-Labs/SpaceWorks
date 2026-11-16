import type { KeyboardEvent } from "react";
import { rovingItems } from "../ui/useRovingFocus";

/** Arrow/Home/End focus movement across nav links. Unlike `rove`, it leaves every tabIndex alone so Tab order is unchanged. */
export function navKeys(event: KeyboardEvent<HTMLElement>, axis: "vertical" | "horizontal") {
  const [prev, next] = axis === "vertical" ? ["ArrowUp", "ArrowDown"] : ["ArrowLeft", "ArrowRight"];
  if (![prev, next, "Home", "End"].includes(event.key) || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
  const items = rovingItems(event.currentTarget, "a[href], button");
  const current = items.indexOf(event.target as HTMLElement);
  if (current < 0) return;
  event.preventDefault();
  const index = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1 : (current + (event.key === prev ? -1 : 1) + items.length) % items.length;
  items[index].focus();
}
