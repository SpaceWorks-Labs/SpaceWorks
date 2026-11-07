import { t } from "@lingui/core/macro";
import { Lock, LockOpen } from "lucide-react";

import { useSetLock } from "./settingsAuthorityApi";

/**
 * A setting's lock (#101): the Space Manager toggles it, everyone else sees a notice while it
 * is locked. A lock blocks delegated edits only -- it never binds the Space Manager.
 */
export function SettingLock({ makerspaceId, settingKey, label, locked, canLock }: {
  makerspaceId: number; settingKey: string; label: string; locked: boolean; canLock: boolean;
}) {
  const toggle = useSetLock(makerspaceId);
  if (!canLock) {
    return locked ? <span className="flex min-w-0 items-center gap-1.5 text-sm text-muted">
      <Lock aria-hidden="true" size={16} className="shrink-0" />{t`Locked by the Space Manager`}</span> : null;
  }
  const Icon = locked ? Lock : LockOpen;
  return <span className="grid min-w-0 gap-1">
    <button type="button" className="desk-button-ghost flex min-h-11 w-fit items-center gap-1.5"
      aria-pressed={locked} disabled={toggle.isPending}
      aria-label={t`${locked ? "Unlock" : "Lock"} ${label} for managers`}
      onClick={() => toggle.mutate({ setting_key: settingKey, locked: !locked })}>
      <Icon aria-hidden="true" size={16} className="shrink-0" />
      {locked ? t`Locked for managers` : t`Lock for managers`}
    </button>
    {toggle.error ? <span role="alert" className="text-sm text-danger">{toggle.error.message}</span> : null}
  </span>;
}
