export type SettingsActionsProps = { onDiscard: () => void; onSave?: () => void; pending?: boolean; disabled?: boolean };
export function SettingsActions({ onDiscard, onSave, pending, disabled }: SettingsActionsProps) {
  return <div className="sticky bottom-0 z-10 flex flex-wrap justify-end gap-2 border-t border-line bg-panel p-4">
    <button type="button" className="desk-button" disabled={pending} onClick={onDiscard}>Discard</button>
    <button type={onSave ? "button" : "submit"} className="desk-button-primary" aria-busy={pending || undefined}
      disabled={disabled || pending} onClick={onSave}>{pending ? "Saving…" : "Save changes"}</button>
  </div>;
}
