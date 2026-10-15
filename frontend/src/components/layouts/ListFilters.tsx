import { useEffect, useState, type ReactNode } from "react";
import { ActionControl, FilterBar, Modal } from "../ui";
import { useLayoutMedia } from "./useLayoutMedia";

export type ListFiltersProps = {
  search?: { label: string; value: string; onChange: (value: string) => void };
  controls?: ReactNode;
  chips?: { key: string; label: string; onRemove: () => void }[];
  onClear?: () => void;
};

export function ListFilters({ search, controls, chips = [], onClear }: ListFiltersProps) {
  const [open, setOpen] = useState(false);
  const tablet = useLayoutMedia("(min-width: 768px)");
  useEffect(() => { if (tablet) setOpen(false); }, [tablet]);
  return <div className="grid min-w-0 gap-3">
    <div className="flex min-w-0 flex-wrap items-center gap-3">
      {search ? <div className="min-w-0 flex-1 basis-48"><FilterBar value={search.value} onChange={search.onChange}
        searchLabel={search.label} placeholder={search.label} /></div> : null}
      {controls ? tablet ? <div className="flex min-w-0 flex-wrap gap-3">{controls}</div>
        : <button type="button" className="desk-button" onClick={() => setOpen(true)}>Filters</button> : null}
    </div>
    {chips.length ? <div className="flex flex-wrap items-center gap-2">
      {chips.map(chip => <ActionControl key={chip.key} action={{ label: `Remove ${chip.label}`, onClick: chip.onRemove }} />)}
      {onClear ? <ActionControl action={{ label: "Clear filters", onClick: onClear }} /> : null}
    </div> : null}
    <Modal open={open && !tablet} onClose={() => setOpen(false)} title="Filters"
      footer={<button type="button" className="desk-button-primary" onClick={() => setOpen(false)}>Show results</button>}>
      {controls}
    </Modal>
  </div>;
}
