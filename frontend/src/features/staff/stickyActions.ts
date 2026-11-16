/** Sticky save/discard bar for a long form on a console PAGE (not inside a drawer overlay).
 *
 * Below `lg` the shell's fixed bottom tabs and the device's home indicator cover the last ~64px
 * of the viewport, so a plain `bottom-0` bar parks its buttons underneath them. Offsetting by
 * `--shell-bottom-tabs` (set by AppShell, 0px when the tabs are absent) plus the safe-area inset
 * keeps the actions visible; the row wraps so two buttons never overflow a 320px screen. */
export const pageStickyActions =
  "sticky bottom-[calc(var(--shell-bottom-tabs,0px)+env(safe-area-inset-bottom))] z-10 flex flex-wrap justify-end gap-3 border-t border-line bg-panel py-4 lg:bottom-0";
