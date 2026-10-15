import { useId, type ReactNode } from "react";
export type TicketCardProps = { organisation: string; title: string; fields: { label: string; value: ReactNode }[];
  qr: ReactNode; caption: string };
export function TicketCard({ organisation, title, fields, qr, caption }: TicketCardProps) {
  const id = useId();
  return <article aria-labelledby={id} className="min-w-0 overflow-hidden rounded-xl border border-line bg-panel">
    <header className="bg-brand p-5 text-on-brand">
      <p className="text-sm">{organisation}</p><h2 id={id} className="mt-2 font-display text-xl font-extrabold">{title}</h2>
    </header>
    <dl className="grid grid-cols-2 gap-4 p-5">
      {fields.map(field => <div key={field.label} className="min-w-0"><dt className="eyebrow">{field.label}</dt>
        <dd className="mt-1 break-words text-sm font-semibold text-ink">{field.value}</dd></div>)}
    </dl>
    <div aria-hidden="true" className="relative border-t border-dashed border-line">
      <span className="absolute -left-2 -top-2 h-4 w-4 rounded-full border border-line bg-bg" />
      <span className="absolute -right-2 -top-2 h-4 w-4 rounded-full border border-line bg-bg" />
    </div>
    <div className="flex flex-col items-center gap-4 p-5">
      <div className="h-[172px] w-[172px] [&>svg]:h-full [&>svg]:w-full [&>img]:h-full [&>img]:w-full">{qr}</div>
      <p className="text-center text-sm text-muted">{caption}</p>
    </div>
  </article>;
}
