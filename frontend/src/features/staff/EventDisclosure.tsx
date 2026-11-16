import type { ReactNode } from "react";

/**
 * A collapsed sub-section for occasional event tools (badges, check-in stations, certificates).
 * The contents stay mounted while closed, exactly as before they were tucked away, so an
 * in-progress draft survives closing it and nothing refetches when it reopens.
 */
export function EventDisclosure({ title, children }: { title: string; children: ReactNode }) {
  return <details className="min-w-0 overflow-hidden rounded-xl border border-line bg-panel">
    <summary className="flex min-h-11 cursor-pointer items-center bg-surface px-4 py-3 text-sm font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">{title}</summary>
    <div className="grid min-w-0 gap-4 p-4">{children}</div>
  </details>;
}
