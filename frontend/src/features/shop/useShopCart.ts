import { useCallback, useEffect, useState } from "react";

import { readStorage, removeStorage, writeStorage } from "../../lib/safeStorage";

/** One basket line. Price and label are display hints only; the server quote is what is charged. */
export type CartLine = { variantId: number; quantity: number; label: string; price: string; productSlug: string; max?: number | null };

const key = (slug: string) => `spaceworks.shop.cart:${slug}`;

function read(slug: string): CartLine[] {
  try {
    const parsed: unknown = JSON.parse(readStorage(key(slug), "[]"));
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((line): line is CartLine => Boolean(line) && typeof line === "object"
      && Number.isInteger((line as CartLine).variantId) && Number.isInteger((line as CartLine).quantity)
      && (line as CartLine).quantity > 0);
  } catch {
    return [];
  }
}

function clamp(quantity: number, max?: number | null) {
  const floor = Math.max(0, Math.floor(quantity));
  return max ? Math.min(floor, max) : floor;
}

/**
 * The basket is kept per space in this browser only. Storage can be missing (private mode,
 * blocked site data), so every read and write is guarded and the basket still works in memory.
 */
export function useShopCart(slug: string) {
  const [lines, setLines] = useState<CartLine[]>(() => read(slug));
  useEffect(() => { setLines(read(slug)); }, [slug]);
  const save = useCallback((next: CartLine[]) => {
    setLines(next);
    try {
      if (next.length) writeStorage(key(slug), JSON.stringify(next));
      else removeStorage(key(slug));
    } catch { /* the basket stays in memory */ }
  }, [slug]);
  const add = useCallback((line: Omit<CartLine, "quantity">, quantity = 1) => {
    const existing = lines.find(row => row.variantId === line.variantId);
    const next = existing
      ? lines.map(row => row.variantId === line.variantId ? { ...row, ...line, quantity: clamp(row.quantity + quantity, line.max) } : row)
      : [...lines, { ...line, quantity: clamp(quantity, line.max) }];
    save(next.filter(row => row.quantity > 0));
  }, [lines, save]);
  const setQuantity = useCallback((variantId: number, quantity: number) => {
    save(lines.map(row => row.variantId === variantId ? { ...row, quantity: clamp(quantity, row.max) } : row).filter(row => row.quantity > 0));
  }, [lines, save]);
  const remove = useCallback((variantId: number) => save(lines.filter(row => row.variantId !== variantId)), [lines, save]);
  const clear = useCallback(() => save([]), [save]);
  const count = lines.reduce((sum, row) => sum + row.quantity, 0);
  return { lines, count, add, setQuantity, remove, clear };
}

export const cartRequest = (lines: CartLine[]) => lines.map(line => ({ variant_id: line.variantId, quantity: line.quantity }));
