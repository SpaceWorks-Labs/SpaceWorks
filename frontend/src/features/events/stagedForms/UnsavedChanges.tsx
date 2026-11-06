import { t } from "@lingui/core/macro";
import { useEffect } from "react";

const dirtyEditors = new Set<symbol>();
const unload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
const navigate = (event: MouseEvent) => {
  const link = event.target instanceof Element ? event.target.closest("a[href]") : null;
  if (link && !window.confirm(t`You have unsaved changes. Leave this page?`)) { event.preventDefault(); event.stopPropagation(); }
};

/** Exported for G's route guard as well as unload and ordinary link navigation. */
export function useUnsavedChanges(dirty: boolean, onDirtyChange?: (dirty: boolean) => void) {
  useEffect(() => { onDirtyChange?.(dirty); return () => onDirtyChange?.(false); }, [dirty, onDirtyChange]);
  useEffect(() => {
    if (!dirty) return;
    const editor = Symbol("dirty-editor");
    if (!dirtyEditors.size) { window.addEventListener("beforeunload", unload); document.addEventListener("click", navigate, true); }
    dirtyEditors.add(editor);
    return () => {
      dirtyEditors.delete(editor);
      if (!dirtyEditors.size) { window.removeEventListener("beforeunload", unload); document.removeEventListener("click", navigate, true); }
    };
  }, [dirty]);
}
