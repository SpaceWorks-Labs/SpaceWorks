import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";
import { useId } from "react";
import { SearchField } from "./SearchField";

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
  placeholder = t`Search`,
  searchLabel = t`Search table`,
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
      <SearchField
        id={searchId}
        fixedIcon
        clearLabel={t`Clear the search box`}
        adornmentClassName={`text-on-success ${hero ? "" : "dark:text-success-ink"}`}
        className={`desk-input w-full min-w-0 bg-success text-on-success placeholder:text-on-success/70 ${hero
          ? "h-12 border-transparent hover:border-transparent xl:h-14"
          : "h-11 border-outline dark:border-success dark:bg-surface dark:text-ink dark:placeholder:text-muted"}`}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
      </div>
      {children ? <div className="flex flex-wrap items-center gap-2">{children}</div> : null}
      {actions ? <div className="flex flex-wrap items-center gap-2 sm:ml-auto">{actions}</div> : null}
    </div>
  );
}
