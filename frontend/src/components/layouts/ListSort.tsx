import { t } from "@lingui/core/macro";
import type { ChangeEventHandler } from "react";

export function ListSort({ value, onChange, options, label = t`Sort` }: {
  value: string; onChange: ChangeEventHandler<HTMLSelectElement>;
  options: readonly (readonly [string, string])[]; label?: string;
}) {
  return <label className="relative flex h-11 min-w-0 items-center">
    <span aria-hidden="true" className="pointer-events-none absolute left-3 text-sm text-muted">{t`Sort:`}</span>
    <span className="sr-only">{label}</span>
    <select className="desk-input h-11 w-full min-w-0 pl-12" value={value} onChange={onChange}>
      {options.map(([key, text]) => <option value={key} key={key}>{text}</option>)}
    </select>
  </label>;
}
