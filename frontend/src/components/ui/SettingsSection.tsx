import { useId, type ReactNode } from "react";
export type SettingsSectionProps = { title: string; description?: string; children: ReactNode };
export function SettingsSection({ title, description, children }: SettingsSectionProps) {
  const id = useId();
  return <section aria-labelledby={title ? id : undefined} className="min-w-0 rounded-xl border border-line bg-panel p-5 sm:p-6">
    {title ? <h2 id={id} className="title-panel">{title}</h2> : null}
    {description ? <p className="mt-2 text-sm text-muted">{description}</p> : null}
    <div className="mt-4 divide-y divide-line">{children}</div>
  </section>;
}
