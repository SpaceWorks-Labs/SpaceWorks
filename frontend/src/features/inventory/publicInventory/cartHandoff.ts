import type { RequestCartItem } from "../../../types/inventory";

/**
 * "Sign in to borrow" leaves the public inventory page for the member sign-in, and the cart
 * lives only in React state (0.12.0 row 29). The panel stashes it here for the trip; the cart
 * hook reads it back when the visitor returns to the same page. sessionStorage: one tab only,
 * gone with the tab, and the stash is removed as soon as it is restored.
 */
const PREFIX = "spaceworks.publicCart.handoff:";

const key = (path: string) => `${PREFIX}${path}`;

export function stashCartForSignIn(items: readonly RequestCartItem[], path = window.location.pathname) {
  try {
    if (items.length) window.sessionStorage.setItem(key(path), JSON.stringify(items));
  } catch {
    // Storage can be unavailable in private or locked-down browser contexts: the visitor refills the cart.
  }
}

/** The stashed cart for this page, keyed by product id; empty when there is none or it is malformed. */
export function readStashedCart(path = window.location.pathname): Record<number, RequestCartItem> {
  try {
    const parsed: unknown = JSON.parse(window.sessionStorage.getItem(key(path)) ?? "[]");
    if (!Array.isArray(parsed)) return {};
    const cart: Record<number, RequestCartItem> = {};
    for (const row of parsed) {
      if (row && Number.isInteger(row.productId) && Number.isInteger(row.quantity) && row.quantity > 0 && typeof row.name === "string") {
        cart[row.productId] = { productId: row.productId, name: row.name, quantity: Math.min(row.quantity, 99) };
      }
    }
    return cart;
  } catch {
    return {};
  }
}

export function clearStashedCart(path = window.location.pathname) {
  try {
    window.sessionStorage.removeItem(key(path));
  } catch {
    // Nothing to clear when storage is unavailable.
  }
}

/** True for a path a browser would read as another host: `//host` or `/\host`. */
const looksProtocolRelative = (path: string) => path.startsWith("//") || path.startsWith("/\\");

/**
 * A same-origin path to return to after sign-in, or undefined (never another origin).
 * The FINAL normalized target is checked too: `/.//evil.test`, `/%2e//evil.test` and
 * `/a/..//evil.test` all pass a prefix check but normalize to `//evil.test`, which
 * `location.replace()` would follow off-site.
 */
export function safeReturnPath(value: string | null | undefined): string | undefined {
  if (!value || !value.startsWith("/") || looksProtocolRelative(value)) return undefined;
  try {
    const url = new URL(value, window.location.origin);
    if (url.origin !== window.location.origin || looksProtocolRelative(url.pathname)) return undefined;
    return url.pathname + url.search + url.hash;
  } catch {
    return undefined;
  }
}
