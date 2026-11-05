// "Keyboard shortcuts": every designer shortcut in one list (also opened with ?).
import { Modal } from "../ui/Modal";
import { SHORTCUT_GROUPS } from "./shortcuts";

export function ShortcutsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  return <Modal open={open} onClose={onClose} title="Keyboard shortcuts"
    footer={<div className="flex justify-end"><button type="button" className="desk-button min-h-11" onClick={onClose}>Close</button></div>}>
    <div className="grid gap-5">
      <p className="text-sm text-muted">Shortcuts work when the card or the designer has focus, never while you type in a field.</p>
      {SHORTCUT_GROUPS.map((group, index) => <section key={group.title} aria-labelledby={`card-shortcuts-${index}`} className="grid gap-2">
        <h3 id={`card-shortcuts-${index}`} className="text-sm font-semibold text-ink">{group.title}</h3>
        <dl className="grid gap-2">
          {group.rows.map((row) => <div key={row.action} className="grid gap-1 sm:grid-cols-[12rem_minmax(0,1fr)] sm:items-center">
            <dt className="flex flex-wrap items-center gap-1">
              {row.keys.map((key, index) => <span key={key} className="flex items-center gap-1">
                {index ? <span aria-hidden="true" className="text-xs text-muted">+</span> : null}
                <kbd className="rounded-control border border-line bg-surface px-1.5 py-0.5 font-sans text-xs font-semibold text-ink">{key}</kbd>
              </span>)}
            </dt>
            <dd className="text-sm text-ink">{row.action}</dd>
          </div>)}
        </dl>
      </section>)}
    </div>
  </Modal>;
}
