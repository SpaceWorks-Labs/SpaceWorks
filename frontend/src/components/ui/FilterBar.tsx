import type { ReactNode } from "react";
import { useId } from "react";
import { Search } from "lucide-react";

export type FilterBarProps = {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  searchLabel?: string;
  children?: ReactNode;
  actions?: ReactNode;
  /** hero: the p.16 Citron search in both modes, for a teal field. console: Citron in light; in dark a
   * surface field with a Citron boundary and icon, so the brand cue survives without a bright slab. */
  variant?: "console" | "hero";
};

export function FilterBar({
  value,
  onChange,
  placeholder = "Search",
  searchLabel = "Search table",
  children,
  actions,
  variant = "console",
}: FilterBarProps) {
  const searchId = useId();
  const hero = variant === "hero";

  return (
    <div className="flex min-w-0 flex-wrap items-center gap-3">
      <div className="relative min-w-0 flex-1 basis-full sm:basis-48">
      <label className="sr-only" htmlFor={searchId}>
        {searchLabel}
      </label>
      <input
        id={searchId}
        className={`desk-input w-full min-w-0 bg-success pl-11 text-on-success placeholder:text-on-success ${hero
          ? "h-12 border-transparent hover:border-transparent xl:h-14"
          : "h-11 border-outline dark:border-success dark:bg-surface dark:text-ink dark:placeholder:text-muted"}`}
        type="search"
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
      <Search aria-hidden="true" className={`pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-on-success ${hero ? "" : "dark:text-success-ink"}`} />
      </div>
      {children ? <div className="flex flex-wrap items-center gap-2">{children}</div> : null}
      {actions ? <div className="flex flex-wrap items-center gap-2 sm:ml-auto">{actions}</div> : null}
    </div>
  );
}
