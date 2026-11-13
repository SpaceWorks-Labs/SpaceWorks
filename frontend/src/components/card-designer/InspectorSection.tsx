// A collapsible group of inspector controls (Position, Text, Effects ...). Native <details>, so it is keyboard
// operable and announced by screen readers; the open state is remembered for the session per title.
import type { ReactNode } from "react";

const remembered = new Map<string, boolean>();

export function InspectorSection({ title, children, defaultOpen = true }: { title: string; children: ReactNode; defaultOpen?: boolean }) {
  return <details open={remembered.get(title) ?? defaultOpen} className="group border-b border-line pb-3 last:border-b-0"
    onToggle={(event) => remembered.set(title, event.currentTarget.open)}>
    <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between rounded-control text-xs font-bold uppercase tracking-wide text-muted focus-visible:outline-2 focus-visible:outline-focus [&::-webkit-details-marker]:hidden">
      <span>{title}</span>
      <span aria-hidden="true" className="text-base transition-transform group-open:rotate-90">›</span>
    </summary>
    <div className="grid gap-3 pt-1">{children}</div>
  </details>;
}
