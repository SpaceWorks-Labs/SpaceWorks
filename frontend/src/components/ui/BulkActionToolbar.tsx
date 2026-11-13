import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";

export type BulkActionToolbarProps = {
  selectedCount: number;
  onClear: () => void;
  actions?: ReactNode;
  clearLabel?: string;
};

export function BulkActionToolbar({
  selectedCount,
  onClear,
  actions,
  clearLabel,
}: BulkActionToolbarProps) {
  if (selectedCount <= 0) return null;

  return (
    <div className="sticky top-2 z-10 flex min-w-0 flex-wrap items-center gap-2 rounded-xl border border-line bg-accent-soft px-3 py-2 text-sm text-accent-ink">
      <span role="status" className="font-semibold">{t`${selectedCount} selected`}</span>
      {actions ? <div className="desk-actions flex min-w-0 flex-wrap items-center gap-2">{actions}</div> : null}
      <button className="desk-button ml-0 w-full sm:ml-auto sm:w-auto" type="button" onClick={onClear}>
        {clearLabel ?? t`Clear selection`}
      </button>
    </div>
  );
}
