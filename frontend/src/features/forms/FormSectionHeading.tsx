import type { FormSection } from "./types";

/** A form section heading (parity O-B2): plain text the form author wrote, never an answer. */
export function FormSectionHeading({ section }: { section: FormSection }) {
  return <div className="grid gap-1 border-b border-line pb-2 pt-2 first:pt-0">
    <h3 className="title-section text-ink">{section.heading}</h3>
    {section.help ? <p className="max-w-prose text-sm text-muted">{section.help}</p> : null}
  </div>;
}
