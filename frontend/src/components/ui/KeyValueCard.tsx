import { t } from "@lingui/core/macro";
import { useId, type ReactNode } from "react";
export type KeyValueCardProps = { title?: string; items: { label: string; value: ReactNode }[] };
export function KeyValueCard({ title = t`At a glance`, items }: KeyValueCardProps) {
  const id = useId();
  return <section aria-labelledby={id} className="min-w-0 rounded-xl border border-line bg-panel p-4">
    <h2 id={id} className="title-panel">{title}</h2>
    <dl className="mt-3 divide-y divide-line">
      {items.map(item => <div key={item.label} className="flex min-h-11 items-center justify-between gap-4 py-2 text-sm">
        <dt className="text-muted">{item.label}</dt><dd className="min-w-0 break-words text-right text-ink">{item.value}</dd>
      </div>)}
    </dl>
  </section>;
}
