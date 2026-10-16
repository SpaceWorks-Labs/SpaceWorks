import type { ReactNode } from "react";

// Later lanes supply their separately authorized tab components through this slot.
export type BookingDrawerTab = { id: string; label: string; content: ReactNode };
export function BookingDrawerTabs({ tabs, selected, onSelect }: {
  tabs: BookingDrawerTab[]; selected: string; onSelect: (id: string) => void;
}) {
  return <nav aria-label="Resource sections" className="flex flex-wrap gap-2">
    {tabs.map((tab) => <button key={tab.id} className="desk-button" type="button" aria-pressed={selected === tab.id} onClick={() => onSelect(tab.id)}>{tab.label}</button>)}
  </nav>;
}
