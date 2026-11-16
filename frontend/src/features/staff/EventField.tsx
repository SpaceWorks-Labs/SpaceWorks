import { cloneElement, useId, type ReactElement } from "react";
import { Field, SettingsRow } from "../../components/ui";

/** The same event controls appear in creation forms and in settings rows. */
export function EventField({ label, helper, settings, wide, children }: {
  label: string; helper?: string; settings: boolean; wide?: boolean;
  children: ReactElement<{ id?: string }>;
}) {
  const id = useId();
  return settings ? <SettingsRow label={label} helper={helper} htmlFor={id}>{cloneElement(children, { id })}</SettingsRow>
    : <Field label={label} hint={helper} className={wide ? "sm:col-span-2" : undefined}>{children}</Field>;
}
