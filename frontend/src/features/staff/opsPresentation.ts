import type { MouseEvent } from "react";
import { useSearchParams } from "react-router-dom";
import type { QueryState, Tab } from "../../components/ui";

/** The layout owns tab rendering; callers retain URL state and client navigation. */
export function useOpsTabs(key: string, choices: { key: string; label: string; count?: number }[], fallback: string) {
  const [params, setParams] = useSearchParams();
  const active = choices.some(choice => choice.key === params.get(key)) ? params.get(key)! : fallback;
  const href = (value: string) => {
    const next = new URLSearchParams(params);
    next.set(key, value);
    return `?${next}`;
  };
  const select = (value: string) => setParams(current => {
    const next = new URLSearchParams(current);
    next.set(key, value);
    return next;
  });
  const onClickCapture = (event: MouseEvent<HTMLElement>) => {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const anchor = (event.target as HTMLElement).closest<HTMLAnchorElement>('a[href^="?"]');
    if (!anchor) return;
    const value = new URLSearchParams(anchor.getAttribute("href")!.slice(1)).get(key);
    if (!choices.some(choice => choice.key === value)) return;
    event.preventDefault();
    select(value!);
  };
  const tabs: Tab[] = choices.map(choice => ({ ...choice, href: href(choice.key) }));
  return { active, tabs, select, href, onClickCapture };
}

/** Use the same query status/error contract in each ops layout without moving its hooks. */
export function opsQueryState(query: { isLoading: boolean; error: unknown; refetch: () => unknown }, resource: string): QueryState {
  return query.isLoading ? { status: "loading" } : query.error
    ? { status: "error", error: `Couldn't load ${resource}. Try again.`, onRetry: () => { void query.refetch(); } }
    : { status: "ready" };
}


/** Keep canonical API status values unchanged while presenting sentence-case words. */
export function opsStatusLabel(status: string) {
  return status.replace(/_/g, " ").replace(/^\w/, letter => letter.toUpperCase());
}
