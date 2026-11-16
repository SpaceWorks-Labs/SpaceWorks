import { t } from "@lingui/core/macro";
import { useEffect } from "react";

export function DirtySaveBar({ dirty, pending, error, onSave, onDiscard, blocked = false }: {
  dirty: boolean; pending: boolean; error?: string; onSave: () => void; onDiscard: () => void; blocked?: boolean;
}) {
  useEffect(() => {
    if (!dirty) return;
    const unload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    const navigate = (event: MouseEvent) => {
      const anchor = (event.target as Element)?.closest?.("a[href]");
      if (anchor && !window.confirm(t`You have unsaved changes. Leave this page?`)) { event.preventDefault(); event.stopPropagation(); }
    };
    window.addEventListener("beforeunload", unload); document.addEventListener("click", navigate, true);
    return () => { window.removeEventListener("beforeunload", unload); document.removeEventListener("click", navigate, true); };
  }, [dirty]);
  if (!dirty && !pending && !error) return null;
  return <div className="sticky bottom-[var(--shell-bottom-offset,0px)] z-10 grid gap-2 rounded-2xl border border-line bg-panel p-4" aria-label={t`Unsaved changes`}>
    {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}<div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm">{pending ? t`Saving changes…` : t`You have unsaved changes.`}</p><div className="flex gap-2"><button type="button" className="desk-button" disabled={pending} onClick={onDiscard}>{t`Discard`}</button><button type="button" className="desk-button-primary" disabled={pending || blocked} onClick={onSave}>{t`Save changes`}</button></div></div>
  </div>;
}
