import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ConfirmDialog, DangerZone } from "../../components/ui";

/** Saved secrets cannot be recovered, so each reset names its consequence first. */
export function SettingsResetAction({ label, consequence, pending, disabled, onConfirm }: {
  label: string; consequence: string; pending: boolean; disabled?: boolean;
  onConfirm: () => Promise<unknown>;
}) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const confirm = async () => {
    setError("");
    try { await onConfirm(); setOpen(false); }
    catch (failure) { setError(failure instanceof Error ? failure.message : t`Couldn't clear these settings. Try again.`); }
  };
  return <>
    <DangerZone title={label} consequence={consequence} action={{ label,
      onClick: () => { setError(""); setOpen(true); }, pending, disabled,
      disabledReason: disabled ? "No saved configuration is available to clear, or another update is in progress." : undefined }} />
    <ConfirmDialog open={open} title={`${label}?`} message={error ? `${consequence} ${error}` : consequence}
      confirmLabel={label} tone="danger" pending={pending} onConfirm={() => { void confirm(); }}
      onCancel={() => { if (!pending) setOpen(false); }} />
  </>;
}
