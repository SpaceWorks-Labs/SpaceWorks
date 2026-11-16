import { useRef } from "react";

/**
 * Keeps a query-key array referentially stable while its elements are unchanged. Keys are rebuilt
 * on every render (`[...base, page]`), so using one directly as an effect dependency re-runs the
 * effect each render; this returns the first array until an element actually changes.
 */
export function useStableKey<T extends readonly unknown[]>(key: T): T {
  const ref = useRef(key);
  const previous = ref.current;
  if (previous.length !== key.length || previous.some((value, index) => !Object.is(value, key[index]))) ref.current = key;
  return ref.current;
}
