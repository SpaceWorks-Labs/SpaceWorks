import type { ReactNode } from "react";
import { SettingsRow } from "../../../components/ui";
export function Field({ id, label, hint, children }: { id: string; label: string; hint?: string; children: ReactNode }) {
  return <SettingsRow label={label} helper={hint} htmlFor={id}>{children}</SettingsRow>;
}
