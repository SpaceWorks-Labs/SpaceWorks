import { SettingsActions } from "../../components/ui";

/** Keep each editor's transaction and discard boundary independent. */
export function SettingsEditorActions({ dirty, onDiscard, onSave, pending, disabled }: {
  dirty: boolean; onDiscard: () => void; onSave?: () => void; pending?: boolean; disabled?: boolean;
}) {
  return dirty || pending ? <SettingsActions onDiscard={onDiscard} onSave={onSave}
    pending={pending} disabled={disabled} /> : null;
}
