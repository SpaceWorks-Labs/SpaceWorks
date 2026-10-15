type Tab = "details" | "analytics";
const TABS = [["details", "Details and bookings"], ["analytics", "Analytics and exports"]] as const;

export function BookingResourceTabs({ active, onChange }: { active: Tab; onChange: (tab: Tab) => void }) {
  return <div role="tablist" aria-label="Resource views" className="flex gap-2">{TABS.map(([key, label], index) =>
    <button key={key} className="desk-button" role="tab" type="button" id={`resource-${key}-tab`}
      aria-controls={`resource-${key}`} aria-selected={active === key} tabIndex={active === key ? 0 : -1}
      onClick={() => onChange(key)} onKeyDown={(event) => {
        const next = event.key === "Home" ? 0 : event.key === "End" ? 1
          : ["ArrowRight", "ArrowLeft"].includes(event.key) ? 1 - index : null;
        if (next !== null) {
          event.preventDefault(); onChange(TABS[next][0]);
          document.getElementById(`resource-${TABS[next][0]}-tab`)?.focus();
        }
      }}>{label}</button>)}</div>;
}
