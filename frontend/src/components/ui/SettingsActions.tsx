import { t } from "@lingui/core/macro";
import { BoxArt } from "../BoxSpinner";
export type SettingsActionsProps = { onDiscard: () => void; onSave?: () => void; pending?: boolean; disabled?: boolean };
// Rendered only while an editor holds unsaved input; `data-settings-unsaved` lets a routed
// settings page ask "is anything dirty here?" before it leaves (SettingsSectionNav).
export function SettingsActions({ onDiscard, onSave, pending, disabled }: SettingsActionsProps) {
  return <div data-settings-unsaved="" className="sw-sticky-footer flex flex-wrap justify-end gap-2 border-t border-line bg-panel px-4 pt-4">
    <button type="button" className="desk-button" disabled={pending} onClick={onDiscard}>{t`Discard`}</button>
    <button type={onSave ? "button" : "submit"} className="desk-button-primary" aria-busy={pending || undefined}
      disabled={disabled || pending} onClick={onSave}>{pending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save changes`}</button>
  </div>;
}
