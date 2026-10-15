import { useId, type ReactNode } from "react";
export type SettingsRowProps = { label: string; helper?: string; children: ReactNode; htmlFor?: string };
export function SettingsRow({ label, helper, children, htmlFor }: SettingsRowProps) {
  const id = useId();
  return <div role="group" aria-labelledby={id} className="grid min-w-0 gap-4 py-5 md:grid-cols-2">
    <div><label id={id} htmlFor={htmlFor} className="title-section">{label}</label>
      {helper ? <p className="mt-1 text-sm text-muted">{helper}</p> : null}</div>
    <div className="min-w-0">{children}</div>
  </div>;
}
